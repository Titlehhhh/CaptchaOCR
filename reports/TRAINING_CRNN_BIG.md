# CRNN-BIG — our own CRNN on the regenerated 500-per-type dataset, type-held-out

**Date:** 2026-10-22 · **Machine:** NVIDIA GeForce GTX 1080 Ti (11.8 GB, sm_61), torch 2.14.1+cu126 in
`.venv-gpu/` · **Code:** `train/captcha_crnn.py`, `train/train.py` · **Run:** `train/run/crnn_big/`
**Dataset:** the 2026-10-22 regeneration, **500 PNGs per type** (46 types, 23 000 images).

Every number below comes from `train/run/crnn_big/` — the trainer's `val_report.json`, the checkpoint
evaluation in `eval_train_types.json` / `eval_heldout_types.json`, and `train.log`. Nothing is a
projection or an estimate.

---

## 1. The short version

| | |
|---|---|
| Model | CRNN (CNN + BiLSTM) + CTC, **4 623 615** parameters, 63 classes, from scratch |
| Split | **type-held-out** — 7 training types (3 500 images) / 4 held-out types (1 999 images) |
| Run | 45 epochs × 110 steps = **4 950 steps**, batch 32, lr 1e-3, **18.3 min** wall clock, ~148 img/s |
| **Held-out exact match** | median over the 4 held-out types **37.20 %**, micro over 1 999 images **38.07 %** |
| **Held-out CER** | median **32.19 %**, micro **40.98 %** |
| Training types | exact match **100.00 %**, CER **0.00 %** on all 7 types (3 500 images) — memorised |
| Verdict | **Yes, it generalises — but unevenly.** Two unseen plugins are read well (69.8 %, 77.8 %), two are not (4.6 %, 0.0 %) |

**The headline question — "does our own model generalise to an unseen plugin style?" — is now
answered *yes, for some styles*:** 38.07 % exact match / 40.98 % CER micro over the held-out images,
against 100 % / 0 % on the types it was trained on. The previous experiment
(`reports/TRAINING_MINIMAL_LATIN.md`) measured **0.000** exact match on unseen types; this run measures
**0.381**. The gap is real but it is *not* closed: the memorisation is still total on the training
types (training loss 0.008), and two of the four unseen plugins are still not solved at all.

---

## 2. The run

```powershell
.venv-gpu\Scripts\python.exe train\train.py --charset latin --trees both --epochs 45 --batch-size 32 `
  --workers 4 --lr 1e-3 --out train\run\crnn_big --save-every 100 --log-every 50 `
  --types "Archy-X/Krypton/map" "GalleryCaptcha/ru-web" "JSH32/Minecaptcha/map" "LagBug/XProtect/reverse" `
          "just-captcha/ProstoCaptcha/map" "n1zamu/NCaptcha/anvil" "ringoame196-s-mcPlugin/ReproductionCAPTCHA/map" `
          "CaptchaVerifyZ/map" "haq/mapcha/map" "jSdCool/minecaptcha/text" "laforetbrut/are-you-sure/code" `
  --val-types "CaptchaVerifyZ/map" "haq/mapcha/map" "jSdCool/minecaptcha/text" "laforetbrut/are-you-sure/code" `
  --exclude-types "Joey61021/captcha/colorgui"
```

| | |
|---|---|
| Optimiser | AdamW, lr 1e-3 (head 1e-4), OneCycleLR, 5 % warmup, weight decay 1e-2 |
| Batch / steps | 32 → 110 steps/epoch; **45 epochs = 4 950 steps** |
| Augmentation | JPEG (p 0.40) / WebP (p 0.15) / brightness / contrast — **on**; `--augment-affine` **off** |
| Precision | AMP on, device cuda, seed 1234, `--workers 4` |
| Wall clock | **18.3 min** (1 100 s; the trainer's own counter says 18.1 min) |
| Throughput | **~148 img/s** (median over the logged steps after step 200); steady state **29–31 s/epoch** (train 19–27 s + eval 4–6 s) |
| Checkpoints | `train/run/crnn_big/ckpt/step_0004950.pt` (final), `step_0004900.pt` |

The last two epochs slowed to ~40 s of training time each — the GPU was shared with the PP-OCRv6 job
in the last two minutes of the run. The number above is therefore the *uncontended* rate.

**The trainer's own output (the split is the proof that it is a split):**

```
samples without a text band, dropped: haq/mapcha/map (1)
train types 7  samples 3500
val   types 4  samples 1999
  held out: CaptchaVerifyZ/map, haq/mapcha/map, jSdCool/minecaptcha/text, laforetbrut/are-you-sure/code
model: 63 classes, 4,623,615 parameters
```

3 500 = 7 × 500 and 1 999 = 500 + 499 + 500 + 500: the four held-out types are in the validation set
**and not** in the training set. No image of a held-out type was ever trained on.

---

## 3. The scope — what the trainer keeps, and what it drops

The trainer's filters, applied to all 46 types with `--charset latin --trees both` (this is the
trainer's own output, from a 1-step run with `--limit-per-type 1`):

**Types with no text band — dropped (13):**
`Archy-X/Krypton/menu`, `BotFilter/map`, `InstantlyMoist/Captcha/textcaptcha`, `LagBug/XProtect/code`,
`LagBug/XProtect/color`, `LagBug/XProtect/map`, `LagBug/XProtect/picture`, `LimboFilter/framed2x2`,
`LimboFilter/framed3x3`, `irootdev/AnBot/captcha`, `jonesdevelopment/sonar/complex`,
`jonesdevelopment/sonar/legacy`, `jonesdevelopment/sonar/standard`

**Types whose labels do not fit the latin charset — dropped (8):**
`FeelingAlive0/AdvancedCaptcha/math` (500 rows), `GalleryCaptcha/ru-symbols` (495),
`LagBug/XProtect/equation` (500), `LagBug/XProtect/gui` (309), `LimboFilter/symbols` (496),
`Mrbysco/Captcha/math` (500), `Yukun99/Captchas/itemslot` (344), `Z4OLLIEZ4/reCaptcha/captchasx` (38)

**Samples without a band inside a banded type — dropped (1):**
`haq/mapcha/map` (1 of 500)

**Types removed by the trainer's built-in exclusion list (13):**
`LagBug/XProtect/{drop,jump,sneak,different}`, `China2B2T/Captcha/wool`, `jSdCool/minecaptcha/image`,
`GalleryCaptcha/ru-object-swatch`, `CaptchaGUI/clickblock`, `LagBug/XProtect/slot`,
`FeelingAlive0/AdvancedCaptcha/button`, `LimboFilter/map`,
`GalleryCaptcha/ru-numberword`, `GalleryCaptcha/ru-numberword-caption`

**Left: 12 types.** One of them, `Joey61021/captcha/colorgui`, was excluded by this run
(`--exclude-types`): its 500 samples carry only **6 distinct answers** (`Red`, `Pink`, …) — a
closed-vocabulary colour-picking task, not glyph recognition (the same rule R6 as
`reports/TRAINING_MINIMAL_LATIN.md` §2). That leaves **11 types = 5 499 usable images**, split 7 / 4.

> Note on the "14 500 band-carrying images" figure in the brief: that is the number of band-carrying
> rows over **all 46 types** (29 types × 500). For Model A (latin charset) only 12 of them survive the
> trainer's filters, so the training set is **3 500 images / 110 steps per epoch**, not 450 steps.

### The split — by whole plugin, never by image

| role | type | plugin | images | answer length |
|---|---|---|---|---|
| train | `Archy-X/Krypton/map` | Archy-X / Krypton | 500 | 5 |
| train | `GalleryCaptcha/ru-web` | GalleryCaptcha | 500 | 5 |
| train | `JSH32/Minecaptcha/map` | JSH32 / Minecaptcha | 500 | 4 |
| train | `LagBug/XProtect/reverse` | LagBug / XProtect | 500 | 6 |
| train | `just-captcha/ProstoCaptcha/map` | just-captcha / ProstoCaptcha | 500 | 6 |
| train | `n1zamu/NCaptcha/anvil` | n1zamu / NCaptcha | 500 | 3–5 |
| train | `ringoame196-s-mcPlugin/ReproductionCAPTCHA/map` | ringoame196-s-mcPlugin | 500 | 5 |
| **held out** | `CaptchaVerifyZ/map` | CaptchaVerifyZ | 500 | 5 |
| **held out** | `haq/mapcha/map` | haq / mapcha | 499 | 4 |
| **held out** | `jSdCool/minecaptcha/text` | jSdCool / minecaptcha | 500 | 8 |
| **held out** | `laforetbrut/are-you-sure/code` | laforetbrut / are-you-sure | 500 | 6 |

Every held-out type is a **plugin the model has never seen**, and each of the four is a different
plugin from the seven training plugins. The four held-out types are **the same four** the previous
experiment held out (`reports/TRAINING_MINIMAL_LATIN.md` §4), so the two runs are comparable *on the
split* — see §8 for why they are still not like-for-like.

Both dataset bugs fixed on 2026-10-22 are confirmed in the data this run used:
`LagBug/XProtect/reverse` has `text != answer` in **500 of 500** rows (the `text()` override is in
place — `text` is the drawn code, `answer` is the reversed string), and `Archy-X/Krypton/map` bands
are now 21–29 px wide instead of a fixed 21 px (the `code.length() - 1` fix).

---

## 4. The loss timeline — the all-blank plateau, and where it broke

`ln 63 = 4.143`. The CTC model sits in the all-blank state for the first ~1 000 steps, **and that is
not a bug**. This run (45 epochs × 110 steps = 4 950 steps):

| step | epoch | train loss | val acc | val CER | what is happening |
|---|---|---|---|---|---|
| 50 | 1 | 34.11 | — | — | the first steps, all-blank, loss far above the floor |
| 100 | 1 | 4.630 | 0.000 | 1.000 | the all-blank plateau (floor 4.143) |
| 300 | 3 | 3.987 | 0.000 | 0.970 | still descending the plateau |
| 500 | 5 | 3.661 | 0.000 | 0.964 | plateau |
| 700 | 7 | 3.166 | 0.000 | 0.942 | plateau |
| 800 | 8 | 2.907 | 0.000 | 0.869 | **the plateau breaks** |
| 900 | 9 | 2.140 | 0.006 | 0.710 | the first held-out samples are read |
| 1 000 | 10 | 1.348 | 0.068 | 0.582 | |
| **1 100** | 10 | **0.949** | 0.178 | 0.297 | **first step below 1.0** |
| 1 650 | 15 | 0.205 | 0.283 | 0.470 | |
| **1 900** | 18 | **0.093** | 0.307 | 0.441 | **first step below 0.1** |
| 2 750 | 25 | 0.026 | 0.362 | 0.442 | |
| 3 300 | 30 | 0.016 | 0.388 | 0.416 | |
| **3 650** | 34 | **0.0096** | 0.370 | 0.410 | **first step below 0.01** |
| 4 400 | 40 | 0.010 | 0.395 | 0.412 | best held-out accuracy of the run |
| **4 950** | 45 | **0.0078** | **0.381** | **0.410** | final |

* The plateau was left between **step 800 and step 1 100** — the same place as the previous run
  (800 → 1 100), and it cost about **5 minutes** of the 18.3.
* The held-out accuracy rises in the same window: 0.000 until epoch 8, 0.006 at epoch 9, 0.182 at
  epoch 11. **A flat loss for the first ten epochs is the expected behaviour of CTC, not a defect.**
* The held-out number **plateaus from epoch 21 onwards** (0.330 – 0.395) while the training loss
  keeps falling to 0.0078: the last 25 epochs buy memorisation, not generalisation.

---

## 5. The results — in percent

### 5.1 The four held-out types (never trained on)

Source: `train/run/crnn_big/val_report.json` (the trainer's own output, final epoch).

| held-out type | plugin | n | **exact match %** | **CER %** | mean char. confidence |
|---|---|---|---|---|---|
| `CaptchaVerifyZ/map` | CaptchaVerifyZ | 500 | **69.80** | **7.76** | 0.931 |
| `haq/mapcha/map` | haq / mapcha | 499 | **4.61** | **56.61** | 0.688 |
| `jSdCool/minecaptcha/text` | jSdCool / minecaptcha | 500 | **77.80** | **3.08** | 0.969 |
| `laforetbrut/are-you-sure/code` | laforetbrut / are-you-sure | 500 | **0.00** | **96.50** | 0.515 |
| **median over the 4 held-out types** | | | **37.20** | **32.19** | |
| **micro over all 1 999 held-out images** | | 1 999 | **38.07** | **40.98** | |
| *mean over the 4 types (reference only)* | | | *38.05* | *40.99* | |

The **median** is the number to quote: the four types are spread over the whole range from 0 % to
77.8 %, and one type moves the mean hard.

Cross-check with `train/eval_ckpt.py` on the final checkpoint
(`train/run/crnn_big/eval_heldout_types.json`) — it also scores the one `haq/mapcha/map` sample
that has no band, on the whole frame, hence n = 500 instead of 499:

```
CaptchaVerifyZ/map          acc 0.700  cer 0.077  n=500
haq/mapcha/map              acc 0.046  cer 0.568  n=500
jSdCool/minecaptcha/text    acc 0.774  cer 0.032  n=500
laforetbrut/are-you-sure/code acc 0.000  cer 0.965 n=500
OVERALL                     acc 0.380  cer 0.410  n=2000
```

### 5.2 The seven training types (the memorisation gap)

Source: `train/run/crnn_big/eval_train_types.json`, the same checkpoint, the same pipeline.

| training type | n | **exact match %** | **CER %** |
|---|---|---|---|
| `Archy-X/Krypton/map` | 500 | **100.00** | **0.00** |
| `GalleryCaptcha/ru-web` | 500 | **100.00** | **0.00** |
| `JSH32/Minecaptcha/map` | 500 | **100.00** | **0.00** |
| `LagBug/XProtect/reverse` | 500 | **100.00** | **0.00** |
| `just-captcha/ProstoCaptcha/map` | 500 | **100.00** | **0.00** |
| `n1zamu/NCaptcha/anvil` | 500 | **100.00** | **0.00** |
| `ringoame196-s-mcPlugin/ReproductionCAPTCHA/map` | 500 | **100.00** | **0.00** |
| **median over the 7 training types** | | **100.00** | **0.00** |
| **micro over all 3 500 training images** | 3 500 | **100.00** | **0.00** |

### 5.3 The gap

| | exact match % | CER % |
|---|---|---|
| training types (median over 7) | **100.00** | **0.00** |
| held-out types (median over 4) | **37.20** | **32.19** |
| **gap** | **62.80 points** | **32.19 points** |

The model still memorises completely — 100 % on every training type, training loss 0.0078. What
changed against the previous experiment is that memorisation is **no longer the whole story**: on two
of the four unseen plugins the model reads 7–8 character codes it has never seen before.

---

## 6. What the model gets wrong on an unseen type

`train/run/crnn_big/eval_heldout_types.json`, the final checkpoint:

```
== jSdCool/minecaptcha/text  (77.8 % exact, CER 3.1 %)
   gold BhagzUQJ     pred BhagzUQJ     conf 0.991
   gold 03YGJWrb    pred 03YGJWrb    conf 0.881

== CaptchaVerifyZ/map  (69.8 % exact, CER 7.8 %)
   gold NR6PI        pred NR8PI        cer 0.200 conf 0.912
   gold BLROT        pred BLROT        cer 0.000 conf 0.993

== haq/mapcha/map  (4.6 % exact, CER 56.6 %)
   gold zPyf         pred ZPy7         cer 0.500 conf 0.588
   gold YQm2         pred YQDj2        cer 0.500 conf 0.722
   gold eDHG         pred GDIG         cer 0.500 conf 0.824

== laforetbrut/are-you-sure/code  (0.0 % exact, CER 96.5 %)
   gold MPFFM5       pred 4xpFx        cer 0.833 conf 0.471
   gold WCSVTJ       pred 47           cer 1.000 conf 0.702
   gold BCHNTK       pred mwy          cer 1.000 conf 0.366
```

Two different failure modes, and they are not the same failure:

| | prediction has the right length | prediction differs from the gold only by case | mean confidence |
|---|---|---|---|
| `CaptchaVerifyZ/map` | 94.8 % | 0.0 % | 0.931 |
| `haq/mapcha/map` | 69.2 % | **7.0 %** | 0.688 |
| `jSdCool/minecaptcha/text` | 97.8 % | 0.4 % | 0.969 |
| `laforetbrut/are-you-sure/code` | **0.2 %** | 0.0 % | 0.515 |

* **`haq/mapcha/map` — a glyph-level failure.** The model finds the four characters and mis-reads
  one: `zPyf → ZPy7` is two edits out of four. The band of this type is much taller than the glyph
  and carries the plugin's interference lines, so the model reads the right string with the wrong
  case and one confusion. 7 % of its answers differ from the gold **only** in case.
* **`laforetbrut/are-you-sure/code` — a localisation failure.** Only 0.2 % of its predictions have
  the right length: the gold is always 6 characters and the prediction is shorter in **499 of 500**
  cases (87 one character long, 144 two, 141 three, 92 four, 33 five, and **one** with all six).
  The model does not find the code at all. The characters are dark grey on light grey with the
  plugin's decoy dots between them (measured in `reports/TRAINING_MINIMAL_LATIN.md` §7.4), so the
  band is a **low-contrast, cluttered** crop. This is the "wrong band / unreadable band" failure,
  not a recogniser failure — the fix belongs to the band and to the input, not to the model.
* The model's confidence separates the two: 0.93 / 0.97 where it is right, 0.69 where it is half
  right, 0.52 where it is guessing. **The per-character posterior is usable for a human-in-the-loop
  solver**: below ~0.6 the answer should not be trusted.

---

## 7. The honest conclusion

**Does our own model generalise to an unseen plugin style? — Yes, for some styles; no, for others.**

* **Median over the held-out types: 37.20 % exact match, 32.19 % CER.**
  **Micro over the 1 999 held-out images: 38.07 % exact match, 40.98 % CER.**
* Against the **100.00 % / 0.00 %** on the types it was trained on, the memorisation gap is
  **62.8 points** — the model still memorises completely, and the transfer is partial, not total.
* The per-type picture is the real answer: **69.8 %** (`CaptchaVerifyZ/map`) and **77.8 %**
  (`jSdCool/minecaptcha/text`) are genuine generalisation to a plugin the model has never seen;
  **4.6 %** (`haq/mapcha/map`) is a near-miss with a readable answer; **0.0 %**
  (`laforetbrut/are-you-sure/code`) is a total failure caused by the input, not by the recogniser.
* **Two caveats that bound the claim.** (a) The held-out set is **four plugins** — one of them can
  move the median by a third, and one more fold would change the headline number. (b) "Unseen
  plugin" is not "unseen scene": several held-out types share a *scene family* with training types
  (`CaptchaVerifyZ/map` is a map captcha and the training set contains four map captchas), so this
  measures transfer to a new **plugin style**, not to a new **picture genre**.
* So the model's own capability, stated plainly: **it reads a code out of a band it has not been
  trained on about two times out of five, and it reads it perfectly when the band is clean and
  high-contrast.**

---

## 8. Discrepancies against `reports/TRAINING_MINIMAL_LATIN.md`

The two runs are **not** like-for-like. The previous numbers are not comparable to these, and this
report does not claim they are.

| | previous (`TRAINING_MINIMAL_LATIN.md`, 2026-10-21) | this run | why it differs |
|---|---|---|---|
| Dataset | the previous render, **100 PNGs per type** | the 2026-10-22 regeneration, **500 PNGs per type** | the generators are **not seeded**: the pixels *and the random codes* are new. The old report's §7.1/§7.2 band bugs were also fixed in between |
| Scope | 10 types, 999 usable images | 12 usable types, 5 499 images (11 used) | more types survive the filters now; 5× the images per type |
| Training set | 6 types, 600 images | 7 types, **3 500 images** | `LagBug/XProtect/reverse` became usable (its label bug was fixed) and `Archy-X/Krypton/map`'s band was fixed |
| Held-out set | the same **4 types** | the same **4 types** | identical split — this is the one thing that *is* comparable |
| Steps | 300 epochs × 19 = **5 700** steps, 12.4 min | 45 epochs × 110 = **4 950** steps, 18.3 min | 5.8× more data per step, but slightly fewer steps |
| Learning rate | **3e-3** | **1e-3** | the value in the brief for this run — a real confound |
| Augmentation | JPEG/WebP/brightness/contrast | the same | `--augment-affine` was off in both |
| **Held-out exact match** | **0.000** (0 % on all four types) | **0.381** (38.07 % micro) | 5× data per type + 5.8× data overall + 1 more style + a different lr |
| **Held-out CER** | 0.912 – 1.058, median **0.954** | 0.031 – 0.965, median **0.322** | as above |
| Training types | 1.000 exact / 0.000 CER | 1.000 exact / 0.000 CER | unchanged — the memorisation is the same |

**The change from 0.000 to 0.381 cannot be attributed to a single factor.** Four things changed at
once (data volume, number of styles, learning rate, the pixels themselves), and this run has no arm
that isolates any one of them. The most plausible mechanism is the data: 3 500 images over 7 styles
is enough for the model to learn *glyphs* instead of "style → answer", and the two plugins that fail
are exactly the two whose bands are hard (interference lines; low-contrast decoys) — failures of the
input, not of the style transfer.

**What is *not* claimed:** that our model is now better than the ready-made baselines. The measured
baselines in `reports/bench_models/` were scored on a different item set with a different protocol;
they were **not** re-run on this dataset and this split, so no comparison is made here.

---

## 9. What was changed in `train/`

| file | change | why |
|---|---|---|
| `train/train.py` | `select()` — an **empty** id list now selects **nothing** | the old code mapped an empty list to "take everything", so a run whose `--val-types` matched no discovered type silently **validated on the training set** and wrote it to `val_report.json` as a held-out measurement. This was hit for real during this task: the first launch printed `val types 0 samples 3500` and was killed |
| `train/train.py` | the `--types` filter is applied **after** discovery, and a `--val-types` string that matches no discovered type id is now a **hard error** (`exit 2`) with an explanation | `--types` is a *substring* filter on the type id applied at discovery time, so a held-out type that is not also listed in `--types` is never discovered. The run then trains on everything and validates on nothing. The check makes that mistake loud |
| `train/run/crnn_big/make_report.py` | **new** (in the run directory, gitignored) | collects `val_report.json` + `eval_*.json` + `train.log` into `reports/TRAINING_CRNN_BIG.json`. It detects the UTF-16 encoding that Windows PowerShell 5.1's `Tee-Object` writes |

`train/captcha_crnn.py` was **not** changed.

---

## 10. What was not verified, and what is still broken

**Not verified**

* **No second run.** No arm isolates "more data" from "more styles" from "lr 1e-3". §8 therefore
  cannot attribute the improvement to a cause, only report it.
* **Only 4 held-out types / 11 types in total.** One type is a third of the median. The 4-fold
  type-held-out CV of the previous report was **not** repeated (it did not finish there either).
* **No baseline was re-measured** on this dataset and this split, so this report says nothing about
  how our model compares with PP-OCRv6, Graf-J, EasyOCR or the ONNX models here.
* **The Cyrillic model (Model B) was not touched.** The 34-class charset problem of
  `train/AGENTS.md` §5 is still open; with the strict charset check a Cyrillic run now *drops*
  `LimboFilter/symbols` and `GalleryCaptcha/ru-symbols` loudly instead of poisoning 496 and 495 rows.
* **The dataset was still being written while this run started.** `dataset/out_ru/LimboFilter/*` was
  at 100–175 images when the run began and reached 500 later. All three are dropped for Model A
  (no band / cyrillic), so the run is unaffected — but the counts in §3 were re-measured after the
  regeneration finished, and all 46 types now hold exactly 500 PNGs.

**Broken / open**

1. **`laforetbrut/are-you-sure/code` is unreadable (0.0 %).** Its band is a low-contrast crop with
   the plugin's decoy dots between the characters; the model finds 1–4 of the 6 characters. The
   previous report's band table (`TRAINING_MINIMAL_LATIN.md` §7.4) already flags it as "correct but
   low contrast". The input has to change, or the type has to be declared out of scope.
2. **`haq/mapcha/map` is 4.6 % with 7 % case-only errors.** The band carries the interference lines,
   and the model confuses case and one character. A per-line crop inside the band, or a
   case-insensitive score for this type, would separate "the model cannot read it" from "the model
   reads it with the wrong case".
3. **The model still memorises 100 % of the training types.** More data per type did not stop the
   memorisation; it only added transfer on top of it. The obvious next lever is still the one the
   previous report named: `--augment-affine` (the flag exists and was **not** used here) and a
   public captcha corpus for pretraining.
4. **`train/train.py` warns `lr_scheduler.step()` before `optimizer.step()`.** This is pre-existing
   and harmless in the steady state, but it means that on a step where the AMP loss is not finite
   the optimiser step is skipped while the schedule still advances — the schedule is then one step
   ahead of the optimiser. It was not changed here (it is not a measurable effect in this run).
5. **A `--quick` run exits with `-1073740791` after printing `done`.** Verified to be **pre-existing**:
   the same code on the unmodified `train/train.py` (via `git stash`) exits with the same code. The
   run itself completes and writes `val_report.json` and the checkpoints; it is a Windows
   interpreter-teardown crash (persistent dataloader workers), not a training failure.

---

## 11. Reproducing this

```powershell
$env:PYTHONIOENCODING="utf-8"
# the run (§2), then:
.venv-gpu\Scripts\python.exe train\eval_ckpt.py --ckpt train\run\crnn_big\ckpt\step_0004950.pt `
  --types "Archy-X/Krypton/map" "GalleryCaptcha/ru-web" "JSH32/Minecaptcha/map" "LagBug/XProtect/reverse" `
          "just-captcha/ProstoCaptcha/map" "n1zamu/NCaptcha/anvil" "ringoame196-s-mcPlugin/ReproductionCAPTCHA/map" `
  --out train\run\crnn_big\eval_train_types.json
.venv-gpu\Scripts\python.exe train\eval_ckpt.py --ckpt train\run\crnn_big\ckpt\step_0004950.pt `
  --types "CaptchaVerifyZ/map" "haq/mapcha/map" "jSdCool/minecaptcha/text" "laforetbrut/are-you-sure/code" `
  --out train\run\crnn_big\eval_heldout_types.json
.venv-gpu\Scripts\python.exe train\run\crnn_big\make_report.py     # -> reports/TRAINING_CRNN_BIG.json
```

Artefacts: `train/run/crnn_big/train.log`, `val_report.json`, `ckpt/step_0004950.pt`,
`eval_train_types.json`, `eval_heldout_types.json`; the machine-readable summary is
`reports/TRAINING_CRNN_BIG.json`.
