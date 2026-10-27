"""The TrOCR dataset, its collator and its evaluation.

The crop and the augmentation are the ones of `train/ppocr_data.py` (re-used, not
re-implemented). Only the last step - the resize to 384x384 and the normalisation -
is TrOCR's. The evaluation decodes with `model.generate` in sub-batches, because on
an OOM the sub-batch is halved rather than the run being killed.
"""

import statistics

import torch

from finetune_common import accumulate_type, finalise_per_type, norm
from ppocr_data import PPOCRDataset, cer, read_labels


def charset_report(types, tokenizer):
    """How much of the dataset the model's own vocabulary can actually spell.

    A character the tokenizer cannot represent is silently dropped by the tokenizer, so
    the model would be taught to emit nothing for it. The number is reported, not hidden.
    """
    rows = []
    ok_chars, bad_chars = 0, 0
    for tid, directory in types:
        rowsl = read_labels(directory)
        texts = [(r.get("text") or "") for r in rowsl]
        bad = set()
        n_bad_labels = 0
        for t in texts:
            if not t:
                continue
            # round-trip: does the tokenizer spell the string back exactly?
            ids = tokenizer(t)["input_ids"]
            if tokenizer.decode(ids, skip_special_tokens=True) != t:
                n_bad_labels += 1
                bad.update(c for c in t if ord(c) >= 128)
        for t in texts:
            for c in t:
                ok_chars += 1
                bad_chars += int(ord(c) >= 128)
        rows.append({"type": tid, "n": len(texts), "labels_not_roundtripping": n_bad_labels,
                     "non_latin_chars": "".join(sorted(bad))})
    return {
        "per_type": rows,
        "chars_total": ok_chars,
        "chars_non_latin": bad_chars,
        "fraction_latin": round((ok_chars - bad_chars) / max(ok_chars, 1), 6),
        "note": ("TrOCR's tokenizer is the checkpoint's own XLMRobertaTokenizer (64 002 "
                 "sentencepiece pieces); it can spell Cyrillic as well, but the four "
                 "Cyrillic types are excluded to keep the training set identical to the "
                 "PP-OCRv6 run, whose dictionary has no Cyrillic at all."),
    }


# --------------------------------------------------------------------------- #
# the dataset
# --------------------------------------------------------------------------- #
class TrOCRDataset(torch.utils.data.Dataset):
    """Band crop -> (optional augmentation) -> the processor's own image processor.

    The crop and the augmentation are the ones of `train/ppocr_data.py` (re-used, not
    re-implemented): crop by `roi`; for a sample without a band crop to the ink bounding
    box; JPEG / WEBP recompression and brightness / contrast jitter on the training set.
    Only the last step - the resize to 384x384 and the normalisation - is TrOCR's.
    """

    def __init__(self, items, processor, augment=False, seed=0, strip_bos=True):
        self.items = items
        self.processor = processor
        self.augment = augment
        self.helpers = PPOCRDataset(items, vocab=None, augment=augment, seed=seed)
        self.seed = seed
        self.strip_bos = strip_bos

    def __len__(self):
        return len(self.items)

    def __getitem__(self, i):
        item = self.items[i]
        img = PPOCRDataset._load(item["path"], item["roi"])
        if item.get("roi") is None:
            x, y, w, h = PPOCRDataset.ink_bbox(img)
            img = img.crop((x, y, x + w, y + h))
        if self.augment:
            img = self.helpers._augment(img)
        # The image processor runs on the whole batch in the collate (one call instead
        # of one call per image): it is 4x faster that way and it is the same processor.
        return {"image": img, "type": item["type"], "index": i, "text": item["text"]}


def collate(batch, pad_token_id):
    """Deprecated helper kept for reference; the live path is `Collator` below."""
    px = torch.stack([b["pixel_values"] for b in batch])
    n = max(len(b["input_ids"]) for b in batch)
    ids = torch.full((len(batch), n), pad_token_id, dtype=torch.long)
    for i, b in enumerate(batch):
        ids[i, :len(b["input_ids"])] = b["input_ids"]
    labels = ids.masked_fill(ids == pad_token_id, -100)
    return {
        "pixel_values": px,
        "input_ids": ids,
        "labels": labels,
        "types": [b["type"] for b in batch],
        "indices": [b["index"] for b in batch],
    }


class Collator:
    """A picklable `collate_fn` (a lambda cannot be pickled by the DataLoader workers).

    The image processor and the tokenizer both run here, on the whole batch at once.
    """

    def __init__(self, pad_token_id, image_processor, tokenizer, strip_bos=True):
        self.pad_token_id = pad_token_id
        self.image_processor = image_processor
        self.tokenizer = tokenizer
        self.strip_bos = strip_bos
        self.bos_id = tokenizer.bos_token_id

    def __call__(self, batch):
        px = self.image_processor(images=[b["image"] for b in batch],
                                  return_tensors="pt")["pixel_values"]
        texts = [b["text"] for b in batch]
        enc = self.tokenizer(texts, padding=True, return_tensors="pt")["input_ids"]
        ids = enc.tolist()
        if self.strip_bos:
            # The pretrained TrOCR decoder starts with `decoder_start_token_id` and then
            # produces the text tokens directly - the measured zero-step generation of
            # this checkpoint is `[2, <text>, 2]`, i.e. no <s> in the label sequence.
            # The tokenizer adds one, so it is stripped: the fine-tuning target then
            # matches the convention the checkpoint was pretrained with.
            for i, row in enumerate(ids):
                if len(row) > 1 and row[0] == self.bos_id:
                    ids[i] = row[1:]
        n = max(len(r) for r in ids)
        padded = torch.full((len(batch), n), self.pad_token_id, dtype=torch.long)
        for i, row in enumerate(ids):
            padded[i, :len(row)] = torch.tensor(row, dtype=torch.long)
        labels = padded.masked_fill(padded == self.pad_token_id, -100)
        return {
            "pixel_values": px,
            "input_ids": padded,
            "labels": labels,
            "types": [b["type"] for b in batch],
            "indices": [b["index"] for b in batch],
        }


def shift_tokens_right(input_ids, decoder_start_token_id, pad_token_id):
    """Label tokens shifted right for the decoder; -100 becomes the pad token."""
    shifted = input_ids.new_zeros(input_ids.shape)
    shifted[:, 1:] = input_ids[:, :-1].clone()
    shifted[:, 0] = decoder_start_token_id
    shifted[shifted == -100] = pad_token_id
    return shifted


# --------------------------------------------------------------------------- #
# evaluation
# --------------------------------------------------------------------------- #
@torch.no_grad()
def _generate(model, px, device, amp, max_new_tokens, tokenizer, sub_bs=8):
    """`model.generate` in sub-batches; on OOM the sub-batch is halved.

    The card is shared with other trainings, so an OOM here must never take somebody
    else's run down. The sub-batches are decoded one by one: the generated sequences
    have different lengths, so they cannot be concatenated into one tensor.
    """
    texts = []
    i = 0
    while i < px.shape[0]:
        chunk = px[i:i + sub_bs]
        while True:
            try:
                with torch.autocast("cuda", dtype=torch.float16,
                                    enabled=amp and device.type == "cuda"):
                    g = model.generate(pixel_values=chunk, max_new_tokens=max_new_tokens,
                                       do_sample=False, num_beams=1)
                break
            except torch.cuda.OutOfMemoryError:
                torch.cuda.empty_cache()
                if chunk.shape[0] == 1:
                    raise
                chunk = chunk[:max(1, chunk.shape[0] // 2)]
                sub_bs = chunk.shape[0]
        texts.extend(tokenizer.batch_decode(g, skip_special_tokens=True))
        i += chunk.shape[0]
    return texts


@torch.no_grad()
def evaluate(model, loader, tokenizer, device, amp=True, max_new_tokens=24, sub_bs=8):
    """Per type: exact match and CER (both on the normalised strings)."""
    model.eval()
    per_type = {}
    for batch in loader:
        px = batch["pixel_values"].to(device, non_blocking=True)
        preds = _generate(model, px, device, amp, max_new_tokens, tokenizer, sub_bs=sub_bs)
        for i, t in enumerate(batch["types"]):
            gold = loader.dataset.items[batch["indices"][i]]["text"]
            accumulate_type(per_type, t, preds[i], gold)
    out = finalise_per_type(per_type)
    model.train()
    return out
