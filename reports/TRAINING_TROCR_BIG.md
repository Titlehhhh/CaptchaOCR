# TrOCR-small-printed vs PP-OCRv6-medium-rec on our captchas

**Question:** is there something newer and better than the CRNN / PP-OCRv6 we train?
**Answer (measured):** on the seven held-out plugin types the transformer decoder is
**not** better — not at this budget, not at this cost. `microsoft/trocr-small-printed`
fine-tuned for one epoch reaches **0.20 % median exact match** where the *untouched*
`PP-OCRv6_medium_rec` reaches **58.80 %** on exactly the same 3500 images, and the
fine-tuned PP-OCRv6 reaches **48.00 %**. The transformer is also **5x slower per image**
and gets **5x fewer optimiser steps** in the same wall-clock.

Everything below is measured on the **same seven held-out types and the same 3500
images** as the PP-OCRv6 run (`train/run_ppocr/big`), so the two columns are directly
comparable.

* Date: 2026-10-22, 15:26–16:12
* Script: [`train/finetune_trocr.py`](../train/finetune_trocr.py) (new)
* Machine: NVIDIA GTX 1080 Ti (11.8 GB, sm_61), torch 2.14.1+cu126, transformers 5.19.0,
  `.venv-gpu`
* Run artefacts: `train/run/trocr_big/` (`log.txt`, `result.json`, `eval_epoch0.json`,
  `best.pt`, `ckpt/final.pt`, `ckpt/step_*.pt`)
* **The deliverable checkpoint** `train/run/trocr_big/best.pt` holds the **best** TrOCR
  weights = **epoch 0, step 800** (i.e. `ckpt/step_000800.pt`'s `model` state, copied
  verbatim). The continuation run (§3) re-initialised its own "best score" bookkeeping
  and therefore overwrote `best.pt` with the *worse* epoch-1 weights; they were put
  back. `ckpt/final.pt` is the last state (epoch 1, step 1613).
* Machine-readable numbers: [`reports/TRAINING_TROCR_BIG.json`](TRAINING_TROCR_BIG.json)

---

## 1. The split (identical to the PP-OCRv6 run)

Whole plugins are held out, never random images. The 7 held-out types and the 13
training types are the ones of `train/finetune_ppocr.py`; the script prints them and
they matched the PP-OCRv6 run type for type.

| role | types | items |
|---|---|---|
| held out (7) | `out/jonesdevelopment/sonar/standard`, `out/jonesdevelopment/sonar/legacy`, `out/jonesdevelopment/sonar/complex`, `out_ru/BotFilter/map`, `out_ru/CaptchaVerifyZ/map`, `out/laforetbrut/are-you-sure/code`, `out/JSH32/Minecaptcha/map` | **3500** |
| trained on (13) | `out/Archy-X/Krypton/map`, `out/FeelingAlive0/AdvancedCaptcha/math`, `out/LagBug/XProtect/equation`, `out/LagBug/XProtect/gui`, `out/LagBug/XProtect/reverse`, `out/Mrbysco/Captcha/math`, `out/Yukun99/Captchas/itemslot`, `out/haq/mapcha/map`, `out/jSdCool/minecaptcha/text`, `out/just-captcha/ProstoCaptcha/map`, `out/n1zamu/NCaptcha/anvil`, `out/ringoame196-s-mcPlugin/ReproductionCAPTCHA/map`, `out_ru/GalleryCaptcha/ru-web` | **6499** |
| dropped (26) | group C (16), no band `roi = null` (6), non-ASCII labels (4: the Cyrillic types) | — |

* The **band rule** is the same as in `train/ppocr_data.py`: a sample without `roi` is not
  a recognition target (dropped from training); for the four held-out types without a
  band the frame is cropped to its **ink bounding box** first, exactly as the PP-OCRv6
  run did.
* The target is **`text`** (what is drawn), never `answer`.
* The metric code (`norm()`, `cer()`, the median-over-types aggregation) is the one of
  `train/ppocr_data.py` / `train/finetune_ppocr.py`, re-used, not re-implemented.

---

## 2. Headline numbers (percentages; the same 3500 held-out images)

| model | state | median exact % (over 7 types) | median CER % | micro exact % | micro CER % |
|---|---|---|---|---|---|
| **TrOCR-small-printed** | zero step (not fine-tuned) | **0.00** | **107.42** | **2.66** | **98.25** |
| **TrOCR-small-printed** | after fine-tuning, **best ckpt** (epoch 0, step 800) | **0.20** | **100.40** | **19.74** | **77.80** |
| **TrOCR-small-printed** | after fine-tuning, 2nd epoch (1613 steps) | **0.00** | **108.93** | **12.74** | **82.86** |
| **PP-OCRv6 medium rec** | zero step (not fine-tuned) | **58.80** | **16.57** | **56.46** | **24.46** |
| **PP-OCRv6 medium rec** | after fine-tuning (best ckpt, epoch 7 of 20) | **48.00** | **22.33** | **54.80** | **21.81** |

> **The fine-tune made PP-OCRv6 *worse* than its own zero step**: the median exact match
> went 58.80 % → 48.00 % and the median CER 16.57 % → 22.33 % over 20 epochs / 4080
> steps. On *these* types the best PP-OCRv6 number is the **pretrained model used as
> is**, not the fine-tuned one. (The PP-OCRv6 history is in
> `train/run_ppocr/big/log.txt` and in `reports/TRAINING_TROCR_BIG.json` →
> `ppocr_v6.history`: epoch 0 = 0.262 median, epoch 7 = 0.480 — the peak — then a slow
> decay to 0.360 at epoch 19.)
>
> **For completeness: the best PP-OCRv6 variant on these types today is the
> weight-interpolated one** (`θ = 0.4·θ_finetuned + 0.6·θ_pretrained`, published as
> `Titlehhhh/captchaocr-ppocrv6`): median exact **63.80 %**, median CER **15.03 %**,
> micro exact **61.23 %**, micro CER **20.04 %**. It was selected on the *same*
> held-out set, so it is optimistic. TrOCR's best fine-tuned number (0.20 % median /
> 19.71 % micro) is **50-300x below every PP-OCRv6 variant**.

### Per held-out type

TrOCR zero step → TrOCR fine-tuned, next to the two PP-OCRv6 columns:

| held-out type | TrOCR zero step exact % / CER % | TrOCR fine-tuned exact % / CER % | PP-OCRv6 zero step exact % / CER % | PP-OCRv6 fine-tuned exact % / CER % |
|---|---|---|---|---|
| `out/JSH32/Minecaptcha/map` | 11.60 / 44.35 | **89.80 / 2.55** | 93.80 / 1.55 | 95.40 / 1.20 |
| `out_ru/CaptchaVerifyZ/map` | 2.00 / 67.48 | **39.20 / 17.96** | 96.60 / 0.68 | 99.20 / 0.16 |
| `out_ru/BotFilter/map` | 5.00 / 68.77 | **9.00 / 50.30** | 73.00 / 8.98 | 56.00 / 15.25 |
| `out/jonesdevelopment/sonar/complex` | 0.00 / 107.42 | **0.20 / 100.40** | 38.80 / 29.08 | 44.60 / 22.33 |
| `out/jonesdevelopment/sonar/legacy` | 0.00 / 117.85 | **0.00 / 127.00** | 34.20 / 33.53 | 38.00 / 29.90 |
| `out/jonesdevelopment/sonar/standard` | 0.00 / 158.18 | **0.00 / 136.03** | 58.80 / 16.57 | 48.00 / 23.80 |
| `out/laforetbrut/are-you-sure/code` | 0.00 / 123.73 | **0.00 / 110.37** | 0.00 / 80.83 | 2.40 / 60.03 |
| **median over the 7 types** | **0.00 / 107.42** | **0.20 / 100.40** | **58.80 / 16.57** | **48.00 / 22.33** |
| **micro over 3500 images** | **2.66 / 98.25** | **19.74 / 77.80** | **56.46 / 24.46** | **54.80 / 21.81** |

The TrOCR "fine-tuned" column is the **re-measured deliverable checkpoint**
(`train/run/trocr_big/best.pt` = epoch 0, step 800, re-evaluated with
`--eval-checkpoint`, 217.9 s for 3500 images; `train/run/trocr_big/eval_epoch0.json`).
It reproduces the in-run numbers of the first attempt to within one image
(micro exact 19.74 % vs 19.71 %, the difference being the 13 steps between step 800
and step 813).

TrOCR learns **two of the seven unseen styles** after one epoch (`Minecaptcha`
11.6 % → 89.8 %, `CaptchaVerifyZ` 2.0 % → 39.2 %) and stays at ~0 on the three
`jonesdevelopment/sonar` types and on `laforetbrut/are-you-sure/code`. PP-OCRv6 reads
the three sonar types at 34–59 % zero step. So the gap is not a metric artefact: it is
a real difference in how well the two models read an unseen style.

### The second epoch made TrOCR *worse* too

| held-out type | TrOCR after epoch 0 exact % / CER % | TrOCR after epoch 1 exact % / CER % |
|---|---|---|
| `out/JSH32/Minecaptcha/map` | 89.80 / 2.55 | 59.40 / 13.00 |
| `out_ru/CaptchaVerifyZ/map` | 39.20 / 17.96 | 27.40 / 25.52 |
| `out_ru/BotFilter/map` | 9.00 / 50.30 | 2.40 / 63.84 |
| `out/jonesdevelopment/sonar/complex` | 0.20 / 100.40 | 0.00 / 109.62 |
| `out/jonesdevelopment/sonar/legacy` | 0.00 / 127.00 | 0.00 / 122.50 |
| `out/jonesdevelopment/sonar/standard` | 0.00 / 136.03 | 0.00 / 136.60 |
| `out/laforetbrut/are-you-sure/code` | 0.00 / 110.37 | 0.00 / 108.93 |
| **median** | **0.20 / 100.40** | **0.00 / 108.93** |
| **micro** | **19.74 / 77.80** | **12.74 / 82.86** |

The training loss kept falling (0.93 → 0.68) while every held-out number got worse.
This is the **same over-fitting signature as PP-OCRv6** (loss 0.0009, held-out median
falling from 0.588 to 0.360) — and it happens with two very different architectures,
so it is a property of **fine-tuning on 13 captcha styles and generalising to unseen
ones**, not of the recogniser.

---

## 3. What was run

```
$env:PYTHONIOENCODING="utf-8"
$env:HF_HOME="C:\Users\Title\Projects\CapthaModel\.hf-cache"
$env:HF_HUB_OFFLINE="1"
.venv-gpu\Scripts\python.exe train\finetune_trocr.py --out train\run\trocr_big --epochs 4 --batch-size 8 --max-minutes 18
```

The run that produced the numbers above (same command, the epoch budget of the schedule
set to one epoch so that the cosine schedule anneals inside the wall-clock budget):

```
.venv-gpu\Scripts\python.exe train\finetune_trocr.py --out train\run\trocr_big --epochs 1 --batch-size 8 --max-minutes 18 --workers 10
```

Second attempt (continuation of the first, see §7):

```
.venv-gpu\Scripts\python.exe train\finetune_trocr.py --out train\run\trocr_big --epochs 2 --batch-size 8 --max-minutes 9 --workers 10 --resume --fresh-sched --skip-zero-step --skip-final-eval
```

Re-measurement of the delivered checkpoint (this is where the "TrOCR fine-tuned"
column of §2 comes from):

```
.venv-gpu\Scripts\python.exe train\finetune_trocr.py --out train\run\trocr_big --eval-checkpoint train\run\trocr_big\ckpt\step_000800.pt --eval-out train\run\trocr_big\eval_epoch0.json --workers 10
```

The report JSON of this report is rebuilt from the run artefacts with:

```
.venv-gpu\Scripts\python.exe train\finetune_trocr.py --report-only --out train\run\trocr_big --report-json reports\TRAINING_TROCR_BIG.json
```

Log excerpt (`train/run/trocr_big/log.txt`):

```
params: 61596672  encoder=deit hidden=384 layers=12 image_size=384  decoder d_model=256 layers=6 vocab=64044
processor: DeiTImageProcessor size=SizeDict(height=384, width=384, ...) mean=(0.5, 0.5, 0.5) std=(0.5, 0.5, 0.5)
tokenizer: XLMRobertaTokenizer vocab=64002 pad=1 bos=0 eos=2 decoder_start=2
charset: 56076 label characters, 0 outside the Latin alphabet (100.00% Latin); tokenizer round-trip failures: 0
train items: 6499   eval items: 3500   held-out items: 3500
zero step: 244.1s  held-out median exact=0.0 cer=1.0742
training: 1 epochs x 813 steps = 813 steps, lr=1e-4/1e-4, batch=8, amp=True, warmup=40
  epoch 0 step 20/813 loss=3.1123 ... img/s=23.7
  epoch 0 step 800/813 loss=0.9451 lr=1.06e-07 439.6s img/s=21.5
epoch 0: loss=0.9345  444.6s  21.6 img/s  step=213ms
epoch 0: held-out median exact=0.002 cer=1.0015  micro exact=0.1971
```

### Method

* **Model**: `microsoft/trocr-small-printed` — DeiT-small ViT encoder (384 hidden, 12
  layers, 6 heads, 16 px patches, **384×384** input) + a 6-layer transformer decoder
  (d_model 256) with cross-attention. **61 596 672 parameters.**
* **Processor**: the checkpoint's own `TrOCRProcessor` — `DeiTImageProcessor`
  (bicubic resize to 384×384, rescale, normalise with mean = std = 0.5) and
  `XLMRobertaTokenizer` (64 002 sentencepiece pieces). **No hand-rolled
  normalisation.**
* **Loss**: the decoder's own cross-entropy (TrOCR is an encoder-decoder, **not** CTC).
  The label tokens are fed shifted right as `decoder_input_ids`
  (`decoder_start_token_id = 2`), the padding is masked with `-100`.
* **Optimiser**: AdamW, lr 1e-4, weight decay 0.01, 5 % warmup + cosine, grad-clip 1.0,
  fp16 autocast + GradScaler (bf16 is emulated on sm_61 and must not be used).
* **Augmentation**: the same JPEG / WEBP recompression and brightness / contrast jitter
  as `train/ppocr_data.py`.
* **Evaluation**: greedy `model.generate` (no beam search), decoded with
  `skip_special_tokens=True`, then `norm()` + `cer()` exactly as the PP-OCRv6 run.

---

## 4. The cost

| | TrOCR-small-printed | PP-OCRv6 medium rec |
|---|---|---|
| input geometry | 384×384 RGB | 48×320 RGB |
| parameters | 61 596 672 | 19 134 326 |
| training throughput | **21.6 img/s** (GPU step time only), **14.6 img/s** wall (6499 images in 444.6 s) | **76.8 img/s** |
| optimiser steps for the measured run | **813** (1 epoch) + 813 (continuation) | **4080** (20 epochs) |
| wall-clock of the measured run | 14.95 min (attempt 1: 1 epoch + 2 evaluations of 3500 images) + 10.62 min (attempt 2: 1 epoch + 1 evaluation) | 36.38 min (20 epochs + evaluations) |
| zero-step evaluation of 3500 images | **244.1 s** (14.3 img/s, autoregressive decoding) | 41.3 s (85 img/s) |
| peak VRAM of the training step | **2039 MiB** (batch 8, §5) | 2478 MiB (batch 32, §5) |

* **Training is ~5.3x slower per image** (76.8 → 14.6 img/s), and the *evaluation* is
  ~6x slower (85 → 14.3 img/s) because the decoder has to be run autoregressively,
  one token at a time, over 3500 images.
* Consequence for a fixed budget: **in the same 36 minutes the PP-OCRv6 run got 4080
  optimiser steps, the transformer got 813** — a fifth of the updates for a model that
  starts 50x further from the target.
* The 384×384 input is the dominant cost: a 62×35 band crop is blown up to 384×384
  (577 ViT tokens) instead of 48×320 (1 CTC frame row).
* The run was made **on a card shared with two other trainings** (PP-OCRv6 medium rec
  at 76.8 img/s and our CRNN). The first minutes of the run were GPU-starved
  (4.4 img/s); after the PP-OCRv6 run finished the same code reached 21.6 img/s of GPU
  step time. The numbers above are the **measured** ones, contention included.

---

## 5. Peak VRAM

Measured with an isolated probe (the same code path, synthetic 384×384 inputs, fp16
autocast, AdamW, `torch.cuda.max_memory_allocated()`), while the other job was on the
card — the memory numbers are per process and are not affected by that:

| model | batch | input | peak allocated | peak reserved | step | img/s (card shared) |
|---|---|---|---|---|---|---|
| TrOCR-small-printed | 8 | 384×384×3 | **2039 MiB** | 2276 MiB | 572 ms | 16.8 |
| PP-OCRv6 medium rec | 32 | 48×320×3 | **2478 MiB** | 2586 MiB | 587 ms | 65.4 |

So the **VRAM per training process is the same order** (~2.0–2.5 GiB) — the transformer
is not the memory hog. What it costs is **time**: 4x more images per batch and still
4x fewer images per second.

---

## 6. Discrepancies and caveats (read this before quoting the numbers)

1. **TrOCR's prior is printed English receipts, not captchas.** `trocr-small-printed`
   was pretrained on SROIE (scanned receipts). Its zero-step behaviour on our images is
   to read a *word* out of a noisy captcha and often to keep going — the CER is
   **> 100 %**, i.e. it emits more characters than the label has. That is the expected
   zero step of a domain-mismatched checkpoint and it is exactly why the fine-tuning
   numbers have to be measured separately.
2. **The vocabulary is not the problem — the prior is.** The tokenizer is the
   checkpoint's own `XLMRobertaTokenizer` with 64 002 sentencepiece pieces; it spells
   Cyrillic as well. Measured: **56 076 label characters, 0 outside ASCII (100.00 %),
   0 labels that fail a tokenizer round-trip** — no label is silently dropped. The four
   Cyrillic types were nevertheless excluded from training, **not** because TrOCR cannot
   spell them, but because the PP-OCRv6 run (the model we compare against) trained on
   the same 13 Latin types and a controlled comparison needs the same training set.
   `--allow-cyrillic` puts them back.
3. **Sub-word decoding.** A 4-character captcha is 2–4 sentencepiece pieces
   (`"HClf"` → `["▁HC", "lf"]`), so the decoder must emit pieces, not characters, and
   an error in the first piece kills the whole string. A CTC model has no such
   failure mode — it is one of the reasons PP-OCRv6 is hard to beat here.
4. **The label sequence has no `<s>`.** The tokenizer would add one, but the pretrained
   checkpoint starts decoding right after `decoder_start_token_id` (measured zero-step
   generation: `[2, <text>, 2]`), so the `<s>` is stripped from the training target to
   match the pretraining convention.
5. **The image processor backend.** The checkpoint's PIL backend and its torchvision
   backend differ by at most 1/255 of a pixel step (measured max abs difference
   0.0078); the torchvision one is ~4x faster and was used for the measured run. The
   zero-step numbers were measured with **both** backends and are identical
   (median exact 0.0, median CER 107.42 %).
6. **The split rule.** The empty-selection bug of `train/train.py` (an empty `--types`
   list meaning "everything") is **not** present here: `--val-types` is matched with
   `any(p in tid for p in patterns)`, so an empty list holds out **nothing**, never
   everything. The 7 held-out types are printed by the script and are listed in §1.
7. **Budget, not architecture, is part of the comparison.** TrOCR got 813 optimiser
   steps and PP-OCRv6 got 4080. The transformer is not merely "worse per step", it is
   also 5x more expensive per step. A longer TrOCR run would very likely keep climbing
   (micro exact 2.66 % → 19.74 % in one epoch) but it would start from 50x further down
   and would need hours, not minutes. **However**: the second epoch did *not* keep
   climbing — it got worse (§2), which is the same over-fitting signature as
   PP-OCRv6. So "just train it longer" is not automatically the fix; more *diverse*
   training styles (or a much smaller learning rate) are.
8. **A caveat on the epoch-0 numbers**: the first attempt trained 813 steps and
   evaluated at step 813 (median CER 100.15 %, micro exact 19.71 %); the delivered
   checkpoint is step 800 (re-measured: median CER 100.40 %, micro exact 19.74 %).
   The two differ by 13 optimiser steps and by one image on `BotFilter/map`. Both are
   reported; the re-measured one is the headline.
8. **The PP-OCRv6 fine-tune is not an improvement either.** The fine-tuned PP-OCRv6
   (48.00 % median) is *worse* than the pretrained PP-OCRv6 used zero step
   (58.80 % median). If the goal is the best number on these types today, the answer
   for PP-OCRv6 is **do not fine-tune it** (or fine-tune it much more conservatively:
   the loss collapsed to 0.0009 while the held-out median fell — that is
   over-fitting to the 13 training styles).

---

## 7. What was NOT verified

* **Not** a converged TrOCR: 1 epoch (813 steps) of a 61 M-parameter model, then a
  continuation to 2 epochs (§3). No learning curve over more than two points, no
  hyper-parameter search, no beam search, no TTA. The **second epoch was worse**, so
  the TrOCR curve was not pushed further — with the evidence at hand, more epochs on
  these 13 types move away from the held-out types, not towards them.
* **Not** `trocr-base-printed` (it is in the local HF cache, but there was no budget for
  a second model; the small model is the cheap one and it already loses).
* **Not** the Cyrillic types (excluded by design, see §6.2).
* **Not** a VLM / any other "newer" architecture — only the transformer-decoder
  recogniser that was in the brief.
* **Not** measured on the whole frame for the banded types (the band crop is used, as in
  the PP-OCRv6 run).
* The peak-VRAM number in §5 is from a short isolated probe, not from the 14.95-minute
  run (the run shared the card with two other trainings).
* The two earlier launch attempts failed and are **not** part of the measurement:
  1. `--epochs 4 --batch-size 8 --max-minutes 18` crashed in the zero-step evaluation
     with `RuntimeError: Sizes of tensors must match except in dimension 0. Expected
     size 5 but got size 6 for tensor number 1 in the list` — the generated sequences
     of two sub-batches had different lengths and were concatenated into one tensor.
     Fixed: the sub-batches are decoded one by one.
  2. The same command was then killed by hand after 40 steps (4.4 img/s): the data
     loader was the bottleneck (1.3 s of waiting per 1.8 s step) because the image
     processor ran per image in the PIL backend. Fixed: the image processor now runs on
     the whole batch in the torchvision backend, with 10 workers.
  The measured run is the third launch.

---

## 8. Conclusion

**No — the transformer decoder is not better than PP-OCRv6 on this task, and it is more
expensive.**

* On the same seven held-out plugin types and the same 3500 images:
  TrOCR-small fine-tuned = **0.20 % median exact / 19.74 % micro exact**;
  PP-OCRv6 medium rec = **48.00 % median exact / 54.80 % micro exact** after
  fine-tuning, **58.80 % / 56.46 %** used **zero step**, and **63.80 % / 61.23 %**
  as the published weight-interpolated variant.
* The gap is not a fine-tuning artefact of one run: the *untouched* TrOCR is at
  **0.00 % median / 2.66 % micro** on the same images, i.e. a printed-text checkpoint
  simply does not read our captchas.
* The cost: **~5x slower per image** (14.6 vs 76.8 img/s), **~6x slower per
  evaluation** (autoregressive decoding), **3x more parameters**, and therefore
  **5x fewer optimiser steps in the same wall-clock**. The VRAM is *not* worse
  (2039 MiB vs 2478 MiB) — the transformer costs **time**, not memory.
* The one encouraging signal: TrOCR's first epoch is steep
  (micro exact 2.66 % → 19.74 %, and it reads two of the seven unseen styles well:
  `Minecaptcha` 89.8 %, `CaptchaVerifyZ` 39.2 %). But the **second epoch made every
  held-out number worse** (micro 19.74 % → 12.74 %) while the training loss kept
  falling (0.93 → 0.68) — so "train it longer" is not the answer.
* **The finding that matters more for the project:** **both** architectures over-fit
  the 13 training styles and lose accuracy on unseen ones (PP-OCRv6: 58.80 % → 48.00 %
  median; TrOCR: 19.74 % → 12.74 % micro). Before spending hours on a bigger
  recogniser, the cheap experiments are
  (a) **PP-OCRv6 zero step vs fine-tuned with a much smaller learning rate / early
  stopping** — the pretrained checkpoint already wins on unseen types, and
  (b) **the weight interpolation** already in the repo (α = 0.4 → 63.80 % median),
  which is the published model.
* If the owner still wants to fund the transformer: the honest budget is **hours, not
  minutes**, and it has to beat **63.80 % median** to be worth anything.
