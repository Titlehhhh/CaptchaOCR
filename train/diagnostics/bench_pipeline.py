import os
import sys
import time

import torch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from captcha_crnn import (CaptchaDataset, CRNN, build_encoder, build_items, collate, CHARSET,
                          find_types)

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT_DIRS = [os.path.join(REPO, "dataset", "out"), os.path.join(REPO, "dataset", "out_ru")]

SCOPE = ["Archy-X/Krypton/map", "GalleryCaptcha/ru-web", "CaptchaVerifyZ/map", "JSH32/Minecaptcha/map",
         "haq/mapcha/map", "jSdCool/minecaptcha/text", "just-captcha/ProstoCaptcha/map",
         "laforetbrut/are-you-sure/code", "n1zamu/NCaptcha/anvil",
         "ringoame196-s-mcPlugin/ReproductionCAPTCHA/map"]


def data_rate(augment, workers, n=2000):
    cs = build_encoder(CHARSET)
    types = [(t, d) for t, d, _r in find_types(OUT_DIRS, wanted=SCOPE)]
    items = build_items(types)
    ds = CaptchaDataset(items, cs.encode, augment=augment)
    loader = torch.utils.data.DataLoader(ds, batch_size=32, shuffle=True, collate_fn=collate,
                                         num_workers=workers, persistent_workers=workers > 0)
    it = iter(loader)
    next(it)
    t0 = time.time()
    n_batches = 0
    for _ in range(n // 32):
        try:
            next(it)
        except StopIteration:
            it = iter(loader)
            next(it)
        n_batches += 1
    dt = time.time() - t0
    return n_batches * 32 / dt


def gpu_rate(workers, steps=60):
    cs = build_encoder(CHARSET)
    types = [(t, d) for t, d, _r in find_types(OUT_DIRS, wanted=SCOPE)]
    items = build_items(types)
    ds = CaptchaDataset(items, cs.encode, augment=True)
    loader = torch.utils.data.DataLoader(ds, batch_size=32, shuffle=True, collate_fn=collate,
                                         num_workers=workers, persistent_workers=workers > 0)
    model = CRNN(cs.num_classes).cuda()
    opt = torch.optim.AdamW(model.parameters(), lr=1e-3)
    ctc = torch.nn.CTCLoss(blank=0, zero_infinity=True)
    scaler = torch.amp.GradScaler("cuda")
    it = iter(loader)
    batch = next(it)
    images = batch["images"].cuda()
    labels = batch["labels"].cuda()
    lengths = batch["lengths"].cuda()
    for _ in range(10):
        with torch.amp.autocast("cuda"):
            logits, t = model(images)
            lp = logits.log_softmax(-1).permute(1, 0, 2)
            loss = ctc(lp, labels, torch.full((images.shape[0],), t, dtype=torch.long, device="cuda"),
                       lengths)
        opt.zero_grad(set_to_none=True)
        scaler.scale(loss).backward()
        scaler.step(opt)
        scaler.update()
    torch.cuda.synchronize()
    t0 = time.time()
    n = 0
    for _ in range(steps):
        with torch.amp.autocast("cuda"):
            logits, t = model(images)
            lp = logits.log_softmax(-1).permute(1, 0, 2)
            loss = ctc(lp, labels, torch.full((images.shape[0],), t, dtype=torch.long, device="cuda"),
                       lengths)
        opt.zero_grad(set_to_none=True)
        scaler.scale(loss).backward()
        scaler.step(opt)
        scaler.update()
        n += images.shape[0]
    torch.cuda.synchronize()
    return n / (time.time() - t0)


if __name__ == "__main__":
    print(f"items: {len(build_items([(t, d) for t, d, _r in find_types(OUT_DIRS, wanted=SCOPE)]))}")
    for aug in (False, True):
        for w in (0, 6, 12):
            print(f"data  augment={aug!s:5s} workers={w:2d}: {data_rate(aug, w):7.1f} img/s")
    for w in (6, 12):
        print(f"gpu   (fixed batch) workers={w:2d}: {gpu_rate(w):7.1f} img/s")
