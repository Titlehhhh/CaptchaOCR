---
name: captcha-train
description: Use when training, resuming or evaluating the CaptchaOCR CRNN+CTC recogniser — running train/train.py on the GPU, choosing the held-out types, reading a loss curve, or interpreting a per-type result. Carries the real flag list, the type-held-out rule, the all-blank CTC plateau warning, the band rule, and the machine's GPU facts.
---

# CaptchaOCR trainer — run it, and read it honestly

The model is a CRNN (CNN + BiLSTM) + CTC, **4 623 615 parameters, 63 classes** (Model A, latin) or
34/44 classes for the Cyrillic families (Model B). Code: `train/captcha_crnn.py`, `train/train.py`.

## Use the GPU venv, not the system python

The system Python carries `torch 2.14.1+cpu`; the CUDA build lives in its own venv, and the system
environment is untouched. The GPU is an **NVIDIA GeForce GTX 1080 Ti (11.8 GB, sm_61)**, driver 581.57;
`cu126` still ships the sm_61 kernels the 1080 Ti needs. Training runs at **920 img/s** on the GPU
against 99 img/s on the CPU. `--device auto` picks the GPU when it is available.

```powershell
.venv-gpu\Scripts\python.exe train\train.py --charset latin --trees both --epochs 80 --batch-size 32 `
    --workers 6 --lr 1e-3 --val-types "haq/mapcha/map" "LagBug/XProtect/sneak" "CaptchaVerifyZ/map" "jSdCool/minecaptcha/text"
```

## The flags, as implemented in `train/train.py`

| Flag | Default | Meaning |
|---|---|---|
| `--quick` | off | the six-type smoke run, two of them held out |
| `--epochs N` | 60 | |
| `--batch-size N` | 32 | |
| `--lr`, `--head-lr` | 3e-3, `lr/10` | OneCycleLR, 5 % warmup |
| `--glyph-height N` | 32 | the **glyph**, not the frame |
| `--charset latin\|cyrillic` | `latin` | Model A = 63 classes |
| `--types`, `--val-types` | — | substring filters on the type id |
| `--limit-per-type N` | — | |
| `--trees out\|out_ru\|both` | `both` | |
| `--allow-no-roi` | off | **also** train on types that have no band (an ill-posed task) |
| `--exclude-types` | — | on top of the built-in exclusion list |
| `--no-augment` | off | |
| `--save-every N`, `--log-every N` | 200, 50 | |
| `--out DIR` | `train/run` | checkpoints + `val_report.json` |
| `--resume` | off | picks up the newest `step_*.pt` in `<out>\ckpt` |
| `--device auto\|cuda\|cpu\|cuda:0` | `auto` | |
| `--amp` / `--no-amp` | amp on | mixed precision on the GPU |
| `--workers N` | 0 | dataloader workers — the image decoding is the bottleneck |
| `--threads N`, `--seed N` | 0, 1234 | |

**There is no `--require-roi` flag.** Types **without** a band are dropped **by default**; the trainer
prints what it dropped. `--allow-no-roi` is the opposite of what its name suggests to some: it *allows*
those ill-posed types in. Do not add it casually.

The trainer also drops, and prints, every type whose label does not survive the chosen charset — an
empty CTC target teaches the model nothing and costs the run its loss (the Cyrillic families against the
latin charset, for instance).

## The split is by type, never by image

`split_types()` holds the validation types out **by type**; a random split leaks, because several types
have only a handful of distinct answers. The unit of generalisation is the **plugin**. Report
**per-type + the median**, not the mean over a fold — one type moves the mean hard. Hold out whole
plugin families, report every held-out type separately, and never quote an accuracy that includes a type
the model was trained on.

## The all-blank plateau — a flat loss is NOT a bug

CTC sits in an all-blank plateau for thousands of steps: the loss sits at **ln 63 ≈ 4.14** (the model
emitting nothing but blanks) and creeps down very slowly. Measured:

| Run | Result |
|---|---|
| 4 samples, 300 steps | loss 12.76 → **0.001**, the argmax gives the right letters |
| 600 images, 152 steps | loss stuck at **4.12**, accuracy 0.000 — **not a bug** |
| 600 images, 2850 steps | loss **0.57** — the plateau is over |

**Do not read a flat loss as a bug before a few thousand steps.** Wait for CTC to leave the plateau before
"fixing" the model. A genuine bug looks different: the loss does not move *and* the labels are wrong
(a band pointing at the wrong line is unfittable by construction).

## The band rule, for the trainer

**A band that does not fit inside the frame is not a band** — `roi()` returns `null` rather than a
rectangle holding only part of the answer. 29 of the 46 types carry a band; the rest are `roi = null`.
A type with **no** band is the ill-posed "find the string somewhere in this picture" task — it teaches
the model to read the wrong line, so it is dropped by default.

`text` is what is **drawn**, `answer` is what the player types. They differ in 9 of the 46 types (the
Russian number words and the arithmetic types). A recogniser is trained on `text`; the conversion to
`answer` is the solver's step. Comparing a prediction with `answer` for those types scores zero by
construction.

## The dataset is an artefact

The generated pixels depend on this machine's fonts. **Train from the folder the run was started from**;
regenerating the dataset mid-project changes the pixels and invalidates the comparison. A resumed run
picks up the newest `<out>\ckpt\step_*.pt` (model + optimiser + scheduler + CPU/CUDA RNG + the
augmentation RNG) and writes `<out>\val_report.json`.

## Never

- **edit a measured result JSON** in `reports/` to make a model look better — re-run the measurement;
- quote a number that was not produced by a run you can point at;
- train on the system python (that is the CPU-only build);
- regenerate the dataset and then compare against an earlier run's numbers.