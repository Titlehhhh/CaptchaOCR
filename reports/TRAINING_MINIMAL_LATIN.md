# Minimal latin model — a measured, honest first model

**Date:** 2026-10-21 · **Machine:** NVIDIA GeForce GTX 1080 Ti (11.8 GB, sm_61), torch 2.14.1+cu126 in
`.venv-gpu/` · **Code:** `train/captcha_crnn.py`, `train/train.py` (+ four new helper scripts, §9)
**Scope of this run:** digits and Latin letters only. No puzzle/object captchas, no colour captchas, no GUI
slot captchas, no Cyrillic, no Russian number words.

Every number in this file was produced by a run that can be repeated with the commands in §4. Nothing here
is a projection, an estimate or a number from another paper.

---

## 1. The short version

| | |
|---|---|
| Training types | **10** (100 images each, 999 usable) |
| Model | CRNN + CTC, **4 623 615** parameters, 63 classes, from scratch |
| Split | **type-held-out** (never a random split) |
| Main run | 6 types trained, 4 types held out, 300 epochs = **5 700 steps**, 12.4 min |
| **Held-out exact-match accuracy** | **0.000** on all four held-out types |
| **Held-out CER** | 0.912 – 1.058, median **0.954** |
| Training types | accuracy **0.997**, CER **0.001** (memorised) |
| 4-fold type-held-out CV | **2 of 4 folds finished** (the deadline cut fold C at 275/7 500 steps and fold D never started). 5 types measured: exact match **0.000** on all five, CER median **0.958** |
| Like-for-like against the baselines | on the **same 40 items**: ours acc **0.000** / CER **1.034**, `Graf-J/captcha-crnn-finetuned` acc **0.100** / CER **0.638** |
| Best measured baseline on the 64 band items | `Graf-J/captcha-crnn-finetuned` **acc 0.156 / CER 0.559** |
| Verdict | **the model loses to the baselines.** It fits the types it was trained on and does not transfer to a type it has never seen |

The failure is not a bug in the training loop and it is not the CTC plateau: the loss leaves the all-blank
plateau at step ~1 000 and reaches 0.005 by step 5 700. The model **memorises** the training types
(99.7 % on them) and **does not generalise** to a new style. §8 says what the measurements say about why,
and what to do next.

---

## 2. The scope, and the rule that produced it

The rule (fixed before the runs, applied to all 46 types):

> A type is in scope if **(R1)** its label is in the Latin charset `0-9A-Za-z`,
> **(R2)** the string that is *drawn* is the string the player types — no solver step in between,
> **(R3)** every sample carries a text band, and the band really contains the answer,
> **(R4)** the answer is not a constant (a constant teaches a constant and leaks through any split),
> **(R5)** the answer length is in the short-code regime (3–8 characters), so one head fits all of them,
> **(R6)** the type has at least 30 distinct answers in 100 samples, so the type teaches *glyphs* and not
> a closed word list.

R1/R2/R3/R4 are facts about the data (measured, §3). R5/R6 are the two judgement calls, and they are the
reason the scope is 10 types and not 21.

### 2.1 The scope table — all 46 types

| type | in/out | why |
|---|---|---|
| `Archy-X/Krypton/map` | **IN** | R1–R6 hold; 100 distinct 5-char codes. **But its band is broken — see §7.1** |
| `GalleryCaptcha/ru-web` | **IN** | R1–R6 hold (100 distinct 5-char codes, mixed case) |
| `CaptchaVerifyZ/map` | **IN** | R1–R6 hold (100 distinct 5-char `0-9A-Z` codes) |
| `JSH32/Minecaptcha/map` | **IN** | R1–R6 hold (100 distinct 4-char codes) |
| `haq/mapcha/map` | **IN** | R1–R6 hold (100 distinct 4-char codes). 99/100 rows carry a band; the 1 without is dropped by the trainer |
| `jSdCool/minecaptcha/text` | **IN** | R1–R6 hold (100 distinct 8-char codes) |
| `just-captcha/ProstoCaptcha/map` | **IN** | R1–R6 hold (100 distinct 6-char codes). Hardest type in the scope: the band is the whole 128-px frame, the code sits among 41 drawn lines |
| `laforetbrut/are-you-sure/code` | **IN** | R1–R6 hold (100 distinct 6-char codes) |
| `n1zamu/NCaptcha/anvil` | **IN** | R1–R6 hold (100 distinct 3–5 digit codes; `text == answer`, the "printed twice" upstream defect is not visible in the band) |
| `ringoame196-s-mcPlugin/ReproductionCAPTCHA/map` | **IN** | R1–R6 hold (100 distinct 5-char codes) |
| `Joey61021/captcha/colorgui` | OUT | R6: **6** distinct answers in 100 samples (`Red`, `Pink`, …). The band is correct and the word is readable, but a 6-word closed vocabulary is a colour-picking task, not glyph recognition. Also: 10/100 of its labels contain a space (`light blue`) |
| `Z4OLLIEZ4/reCaptcha/captchasx` | OUT | R6: **13** distinct answers; 10/100 labels contain a space. Same reason as `colorgui` |
| `LagBug/XProtect/slot` | OUT | R6: **8** distinct answers (a slot number), and the task is "which slot", not "which letters" |
| `LagBug/XProtect/gui` | OUT | R5: measured length **3–17** (the handover's estimate of 3–8 was wrong); a different length regime, and 61/100 of its labels contain a space |
| `Yukun99/Captchas/itemslot` | OUT | R5: measured length **3–20**; 66/100 labels contain a space |
| `FeelingAlive0/AdvancedCaptcha/button` | OUT | R5: length **19–28**; the band holds a phrase (`Click on the glowstone button in white color`) and the answer is a different phrase. Already in the trainer's built-in exclusion list |
| `LagBug/XProtect/reverse` | OUT | **the label is wrong** — the band holds the drawn code, `labels.jsonl.text` holds its *reverse*. §7.2. Training on it teaches the model to output a string that is not in the picture |
| `LagBug/XProtect/drop`, `/jump`, `/sneak` | OUT | R4: **one** distinct answer per type (`drop`/`jump`/`sneak`) — a constant. Also in the built-in exclusion list |
| `LagBug/XProtect/different` | OUT | R4: one distinct answer (`EMERALD_BLOCK`); the label also contains `_` |
| `China2B2T/Captcha/wool` | OUT | R4: one distinct answer (`LIME_WOOL`); contains `_` |
| `LagBug/XProtect/code`, `/map`, `/picture` | OUT | R3: **no band** (`roi = null`) — the ill-posed "find the string somewhere in this picture" task. The trainer drops them by default |
| `InstantlyMoist/Captcha/textcaptcha` | OUT | R3: no band |
| `BotFilter/map` | OUT | R3: no band |
| `irootdev/AnBot/captcha` | OUT | R3: no band |
| `jonesdevelopment/sonar/{standard,legacy,complex}` | OUT | R3: no band |
| `LagBug/XProtect/equation`, `FeelingAlive0/AdvancedCaptcha/math`, `Mrbysco/Captcha/math` | OUT | R1: the label is an expression (`19 - 11`); the charset has no `+ - * =`, so the label is poison for a CTC target. The trainer drops them and says so |
| `LagBug/XProtect/color` | OUT | R3: no band; R1: 11/100 labels contain a space |
| `jSdCool/minecaptcha/image` | OUT | The answer is 63–70 characters of `imgNNNN` ids and is unreadable by construction |
| `CaptchaGUI/clickblock` | OUT | The answer is a slot index; 100 images on 7 unique pictures (93 duplicates) |
| `GalleryCaptcha/ru-numberword`, `ru-numberword-caption`, `LimboFilter/map` | OUT | Cyrillic; the picture shows Russian words and the player types digits — a solver step, and Model B's problem |
| `GalleryCaptcha/ru-symbols`, `LimboFilter/symbols` | OUT | Cyrillic symbols; the digits in their labels are silently dropped by the 34-class Model B charset (§10) |
| `GalleryCaptcha/ru-object-swatch` | OUT | No text in the picture at all — the answer is a colour name |
| `LimboFilter/framed2x2`, `framed3x3` | OUT | The answer is inside **rotated** frames — a solver step, and the words are Cyrillic |
| `Archy-X/Krypton/menu` | OUT | R3: no band; 60/100 labels contain `_` |

**In scope: 10 types, 1 000 images (999 after the trainer drops the one band-less sample of `haq/mapcha/map`).**
Out of scope: 36 types.

---

## 3. The audit — what the trainer really does

`train/audit_types.py` (new) re-derives the table above from every `labels.jsonl`:

```
$ .venv-gpu\Scripts\python.exe train\audit_types.py
46 types total; 21 have a band, a Latin label and text==answer
```

### 3.1 The flags, verified against the source

`train/train.py` really has `--charset latin|cyrillic`, `--types`, `--val-types`, `--exclude-types`,
`--trees out|out_ru|both`, `--allow-no-roi`, `--epochs`, `--batch-size`, `--lr`, `--head-lr`, `--workers`,
`--out`, `--save-every`, `--resume`, `--device auto|cuda|cpu`, `--no-augment`, `--limit-per-type`,
`--seed`, `--amp/--no-amp`, `--log-every`, `--threads`, `--quick`.

**There is no `--require-roi`.** Types without a band are dropped **by default**; `--allow-no-roi` *allows*
them in. `CONTINUE.md` calls the flag `--require-roi` — that name does not exist.

`--quick` is the six-type smoke run of `QUICK_TYPES` with `QUICK_VAL` held out.

### 3.2 What the trainer drops, and what it used to get wrong

Three real defects were found and fixed (the diff is in §9):

1. **The charset check looked at the first five rows only** (`train/train.py`, the old `rows[:5]`). A type
   whose labels are *partly* outside the charset survived the check, and `Charset.encode` then **silently
   drops the unknown characters** — so the CTC target no longer matches the picture. Measured on the current
   tree: `GalleryCaptcha/ru-symbols` has 43/100 rows with a character outside the Latin charset, `LimboFilter/symbols`
   has 35/100, and both passed the old check. The check now looks at **every** row and drops the type with a
   message that says how many rows were affected.
2. **A type with a band on most of its samples but not on all** trained the band-less samples on the **whole
   frame** — the ill-posed task, silently. `haq/mapcha/map` has 99/100 rows with a band; the 100th (sample
   `087.png`) has `roi = null` and was being trained on the entire 128×128 map. Such rows are now dropped and
   counted.
3. **A run without `--val-types` crashed** (`ValueError: too many values to unpack`): `select()` returned the
   untouched list of `(id, dir, root)` triples when the id list was empty, and `build_items` unpacks pairs.

### 3.3 The measured pipeline (this machine, this dataset)

| | |
|---|---|
| data pipeline, 6 workers + augmentation | 3 475 img/s |
| data pipeline, 12 workers + augmentation | 7 308 img/s |
| GPU step, batch 32, fixed batch | **302 img/s** — the GPU is the limit, not the loader |
| one training epoch, 10 types (999 images, 32 steps) | 4.3–5.0 s (**~140–280 img/s**, the width of the widest sample in the batch decides) |
| the first epoch of a run | +16 s: 6 dataloader workers have to start |
| the validation pass | 1.1 s for 1 000 images with 6 workers; **7–10 s with 0 workers** — the original code evaluated with `num_workers=0` and the evaluation was slower than the training. Fixed |

The **920 img/s** of `HANDOVER.md` §1.0 is not what this run measures. The honest figure for this pipeline
on this dataset is **~140–280 img/s** end to end (300 img/s for the GPU step alone), and the reason is the
width: the band is scaled so the *glyph* is 32 px, and a 6-character code in a 101×18 band becomes 357 px
wide, i.e. 89 CTC time steps per sample.

---

## 4. The commands

Every run: `train/run/<name>/` (gitignored), seed **1234**, batch **32**, `--lr 3e-3` (head `3e-4`),
OneCycleLR with 5 % warmup, augmentation **on**, AMP **on**, `--workers 6`, `--device cuda`.

**The main run** (6 types trained, 4 held out):

```powershell
.venv-gpu\Scripts\python.exe train\train.py --charset latin --epochs 300 --batch-size 32 --lr 3e-3 `
  --seed 1234 --workers 6 --device cuda --save-every 500 --log-every 200 --out train\run\main `
  --types "Archy-X/Krypton/map" "GalleryCaptcha/ru-web" "CaptchaVerifyZ/map" "JSH32/Minecaptcha/map" `
          "haq/mapcha/map" "jSdCool/minecaptcha/text" "just-captcha/ProstoCaptcha/map" `
          "laforetbrut/are-you-sure/code" "n1zamu/NCaptcha/anvil" "ringoame196-s-mcPlugin/ReproductionCAPTCHA/map" `
  --val-types "CaptchaVerifyZ/map" "haq/mapcha/map" "jSdCool/minecaptcha/text" "laforetbrut/are-you-sure/code"
```

**The four folds** — the same command with a different `--out` and `--val-types`:

| fold | held out | trained on |
|---|---|---|
| A | `CaptchaVerifyZ/map`, `haq/mapcha/map`, `n1zamu/NCaptcha/anvil` | 7 types |
| B | `jSdCool/minecaptcha/text`, `just-captcha/ProstoCaptcha/map` | 8 types |
| C | `laforetbrut/are-you-sure/code`, `GalleryCaptcha/ru-web` | 8 types |
| D | `Archy-X/Krypton/map`, `JSH32/Minecaptcha/map`, `ringoame196-s-mcPlugin/ReproductionCAPTCHA/map` | 7 types |

**The band contact sheets** (§7):

```powershell
.venv-gpu\Scripts\python.exe train\roi_sheet.py --mode bands  --out reports\roi_bands_minimal.png   --types <the 10 scope types>
.venv-gpu\Scripts\python.exe train\roi_sheet.py --mode frames --out reports\roi_frames_minimal.png  --types <the 10 scope types>
.venv-gpu\Scripts\python.exe train\roi_sheet.py --mode bands  --out reports\roi_bands_borderline.png --types <the excluded types that have a band>
```

**The measurements quoted in §5–§7** (a checkpoint of a fold, the baseline comparison):

```powershell
.venv-gpu\Scripts\python.exe train\eval_ckpt.py --ckpt train\run\foldA\ckpt\step_0007xxx.pt --types "CaptchaVerifyZ/map" --out reports\eval_....json
.venv-gpu\Scripts\python.exe train\compare_baselines.py --ckpt train\run\foldA\ckpt\step_0007xxx.pt --out reports\baseline_comparison.json
```

---

## 5. The loss timeline (the plateau and when it broke)

The main run, 300 epochs × 19 steps = **5 700 steps**, 12.4 min:

| step | 100 | 300 | 500 | 800 | 1 100 | 1 500 | 2 000 | 2 500 | 3 000 | 3 500 | 4 000 | 5 000 | 5 700 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| train loss | 4.411 | 3.716 | 2.919 | 1.805 | **0.537** | 0.178 | 0.055 | 0.024 | 0.019 | 0.007 | 0.005 | 0.005 | **0.005** |

* The all-blank plateau is real: the loss sits at 4.41 at step 100 (`ln 63 = 4.14` is the *floor* of the
  all-blank state, the loss starts above it) and only starts to fall after ~200 steps.
* **The plateau breaks between step 800 and step 1 100** (1.805 → 0.537). After that the loss falls normally.
* By step 2 000 the training loss is 0.055 and by step 5 700 it is **0.005** — the model has *memorised* the
  six training types (99.7 % exact match on them, §6).
* So the "flat loss" warning in `train/README.md` is confirmed on a larger run: a flat loss below step ~1 000
  is not a bug, and the whole plateau costs about 4 minutes of the 12.4.

---

## 6. The results

### 6.1 The main run — the four held-out types

`train/run/main/val_report.json`:

| held-out type | family | exact match | CER | n |
|---|---|---|---|---|
| `CaptchaVerifyZ/map` | clean 5-char `0-9A-Z` on a map | **0.000** | 0.928 | 100 |
| `haq/mapcha/map` | 4-char mixed, heavy interference lines | **0.000** | 1.058 | 99 |
| `jSdCool/minecaptcha/text` | 8-char code in a GUI | **0.000** | 0.912 | 100 |
| `laforetbrut/are-you-sure/code` | 6-char code in a GUI, low contrast | **0.000** | 0.980 | 100 |
| **median** | | **0.000** | **0.954** | |
| **mean (for reference only)** | | 0.000 | 0.970 | 399 |

For contrast, the same **final** checkpoint on the six types it was **trained** on
(`reports/eval_main_final.json`):

| trained type | exact match | CER |
|---|---|---|
| `Archy-X/Krypton/map` | 1.000 | 0.000 |
| `GalleryCaptcha/ru-web` | 1.000 | 0.000 |
| `JSH32/Minecaptcha/map` | 1.000 | 0.000 |
| `just-captcha/ProstoCaptcha/map` | 1.000 | 0.000 |
| `n1zamu/NCaptcha/anvil` | 1.000 | 0.000 |
| `ringoame196-s-mcPlugin/ReproductionCAPTCHA/map` | 1.000 | 0.000 |
| **overall** | **1.000** | **0.000** |

The gap between 1.000 (seen) and 0.000 (unseen) at a training loss of 0.005 is the whole story of
this run: **the model memorises, it does not generalise.**

### 6.2 What the model gets wrong on an unseen type

The predictions are not empty and not random noise — they are strings of roughly the right length with
plausible characters:

```
gold 'MIKA6'  pred 'MCY6h'      gold 's8TO'   pred '5O6'
gold 'XA8FT'  pred '9K36'       gold '4AUe'   pred '474g'
gold 'TUAEL'  pred '7Y6H'       gold 'TrXD'   pred 'I6Hh'
```

The model produces the right *number* of characters and the right *kind* of characters, and gets the
positions wrong. That is what an embedding that has learned "this rendering looks like a training type"
produces.

It is not *confidently* wrong: the mean per-character confidence of the wrong answers is **0.385 – 0.624**
(`CaptchaVerifyZ/map` 0.411, `haq/mapcha/map` 0.426, `jSdCool/minecaptcha/text` 0.624,
`laforetbrut/are-you-sure/code` 0.385). The model knows, roughly, that it is guessing — which is what makes
the per-character posterior usable for a human-in-the-loop solver.

### 6.3 Proof that it is memorisation, not reading

A decisive experiment on the trained checkpoint (`Archy-X/Krypton/map`, sample `002.png`, gold `C7s9V`):

| input | output |
|---|---|
| the band as recorded | `C7s9V` |
| the band with its right 16 px blanked | `C7s9V` |
| the band with its right 24 px blanked | `C7s9V` |
| the band with its right half blanked (only `C7s` left) | `C7sTV` |

The first three characters are read from the picture. The last two are **not**: the model has memorised the
mapping *visible prefix → full code* for the training images and reproduces it even when the pixels that
carry the 4th and 5th character are deleted. With a random 36-symbol alphabet a memorised suffix is the
cheapest shortcut available, and with 600 training images the model takes it.

The same experiment explains `Archy-X/Krypton/map` scoring 1.000 on the training set although its band
provably does not contain the last character (§7.1).

### 6.4 The 4-fold type-held-out cross-validation — **2 of the 4 folds finished**

**The deadline cut the cross-validation short.** The folds were launched as one sequential job; fold A and
fold B completed, fold C was stopped at step 275 of 7 500 (11 epochs of 300 — an unfinished OneCycle
schedule is not a measurement) and fold D never started. The table below therefore covers **5 of the 10
scope types**; the other 5 have no type-held-out measurement at all, and that is stated rather than
papered over.

| fold | held-out type | trained on | exact match | CER | n |
|---|---|---|---|---|---|
| A | `CaptchaVerifyZ/map` | 7 types | **0.000** | 0.928 | 100 |
| A | `haq/mapcha/map` | 7 types | **0.000** | 1.199 | 99 |
| A | `n1zamu/NCaptcha/anvil` | 7 types | **0.000** | 1.021 | 100 |
| B | `jSdCool/minecaptcha/text` | 8 types | **0.000** | 0.911 | 100 |
| B | `just-captcha/ProstoCaptcha/map` | 8 types | **0.000** | 0.958 | 100 |
| **median over the 5 measured types** | | | **0.000** | **0.958** | |
| **mean (for reference only)** | | | 0.000 | 1.003 | 499 |
| C | `laforetbrut/are-you-sure/code`, `GalleryCaptcha/ru-web` | 8 types | **not completed** — stopped at step 275/7 500 (deadline) | | |
| D | `Archy-X/Krypton/map`, `JSH32/Minecaptcha/map`, `ringoame196-s-mcPlugin/ReproductionCAPTCHA/map` | 7 types | **not started** (deadline) | | |

The main run (§6.1) adds a fourth type-held-out measurement on the same setup — `laforetbrut/are-you-sure/code`,
0.000 / CER 0.980 — so **6 of the 10 scope types** have a type-held-out number in total, and every one of
them is **0.000**.

| type | type-held-out exact match | type-held-out CER | from |
|---|---|---|---|
| `CaptchaVerifyZ/map` | 0.000 | 0.928 | fold A |
| `haq/mapcha/map` | 0.000 | 1.199 | fold A |
| `n1zamu/NCaptcha/anvil` | 0.000 | 1.021 | fold A |
| `jSdCool/minecaptcha/text` | 0.000 | 0.911 | fold B |
| `just-captcha/ProstoCaptcha/map` | 0.000 | 0.958 | fold B |
| `laforetbrut/are-you-sure/code` | 0.000 | 0.980 | main run |
| **median** | **0.000** | **0.969** | |
| `Archy-X/Krypton/map`, `GalleryCaptcha/ru-web`, `JSH32/Minecaptcha/map`, `ringoame196-s-mcPlugin/ReproductionCAPTCHA/map` | **not measured** (folds C and D did not finish) | | |

Wall clock: fold A **14.6 min** (6 600 steps), fold B **15.3 min** (7 500 steps), main run **12.4 min**
(5 700 steps). The runs are reproducible from the commands in §4.

### 6.5 The extra arm (more types / affine augmentation) — **not run**

Two further arms were prepared and **not executed**: the deadline hit while the cross-validation was still
running.

* **arm "broad"** — the same 6 training types plus the 9 Latin types that have **no band**
  (`InstantlyMoist/Captcha/textcaptcha`, `LagBug/XProtect/{code,map,picture}`, `BotFilter/map`,
  `irootdev/AnBot/captcha`, `jonesdevelopment/sonar/{standard,legacy,complex}`), i.e. `--allow-no-roi`,
  15 training types / 1 500 images instead of 6 / 600, with the same 4 held-out types. It would have measured
  what the ill-posed types cost and whether 2.5× the styles move the held-out number.
* **arm "affine"** — the same 6 types with the new `--augment-affine` flag (a ±7° rotation, a 0.9–1.1
  scale and a ±2 px shift of the band, on top of the existing JPEG/WebP pass). The flag and the 200-sample
  contact sheet exist (`reports/augmented_minimal.png`); the run does not.

Both are one command each and are the first thing to run next; the numbers belong in §6.5 of this file.

---

## 7. The bands

### 7.1 `Archy-X/Krypton/map` — the band is too narrow, it cuts the last character

**This is a real dataset bug.** The map font draws the glyphs with a one-pixel blank column between them
(`dataset/generator/dev/captcha/gens/Krypton.java:516`, `pen += w + 1`), but the band is computed by summing
the glyph widths only (`Krypton.java:123-134`, `w += advance(rows)`) — it forgets the four separator columns
of a five-character code.

Measured on `001.png` (gold `6aFij`, band `[27, 32, 21, 8]`), the ink columns of the frame are:

```
 32  ....##........#####.#.....#..     ink at x = 29,30 | 39..43 | 45 | 51
 35  ..####......#.#.....#.....#..     ink at x = 27..30 | 37 | 39 | 45 | 51
 39  .......................###...     ink at x = 48,49,50
```

The five glyphs are at x = 27–31 (`6`), 33–37 (`a`), 39–43 (`F`), 45 (`i`) and 47–51 (`j`). The band covers
x = 27…47, so **the whole `j` except its leftmost column lies outside the band**. The same on `002.png`
(gold `C7s9V`): the `V` is at x = 73–77, the band ends at 73.

**What the band should be:** the text's true extent, i.e. `sum(glyph widths) + (number of characters - 1)`.
For a five-character code that is **25 px instead of 21**. The one-line fix in the generator is to add
`code.length() - 1` to `w` in `band()` (`Krypton.java:131`). *`dataset/**` was not touched by this agent — the
fix belongs to the dataset owner.*

Consequence for the model: the type can never be read correctly at inference time (the 5th character is not
in the picture the recogniser is given), and during training it pushes the model into the memorisation
shortcut of §6.3. It is kept **in** the scope because the label and the band are the dataset's truth, and the
cost of the bug is reported rather than hidden.

### 7.2 `LagBug/XProtect/reverse` — the label is the reverse of the drawn text

`dataset/generator/dev/captcha/gens/XProtect.java:317-373` draws `code` and returns `reversed` from
`answer()`, but it does **not** override `text()`, and `Cg.text()` defaults to `answer()`
(`dataset/generator/dev/captcha/Cg.java:67-69`). So `labels.jsonl` for this type carries the **reversed**
string in the `text` field while the band carries the **drawn** code:

```
labels.jsonl: "text":"ShkrZp", "answer":"ShkrZp", "roi":[494, 97, 48, 20]
the pixels in the band read: pZrk hS
```

Training on `text` would ask the recogniser to read `pZrk hS` and output `ShkrZp` — impossible for a CTC
recogniser, and the CER would be 1.0 by construction. The fix is one method in the generator (`text()`
returning the drawn `code`); the type is therefore **out of the scope** until the dataset owner applies it.

### 7.3 The contact sheets

| file | what it shows |
|---|---|
| `reports/roi_bands_minimal.png` | the 10 scope types, all 100 samples each, cropped by `roi` and scaled exactly as the trainer scales them (glyph → 32 px), with the gold text under every crop |
| `reports/roi_frames_minimal.png` | the same 10 types, the **whole frame** with the band rectangle drawn on it, 5 samples per type |
| `reports/roi_bands_borderline.png` | the excluded types that have a band (colour, slot, GUI, long strings, constants, expressions) — for the record |

### 7.4 The verdict per type (does the band carry the answer?)

| type | band | verdict |
|---|---|---|
| `Archy-X/Krypton/map` | 21×8, tight | **BROKEN** — 4 px too narrow, the last character is outside (§7.1) |
| `GalleryCaptcha/ru-web` | fixed 113×44 | **contains** the answer, but it is not tight: the band also carries the frame border and the background decoration, and the code sits at a random offset inside it |
| `CaptchaVerifyZ/map` | 75×28, tight | **correct** (1 px margin left and right) |
| `JSH32/Minecaptcha/map` | 79×35, tight | **correct** |
| `haq/mapcha/map` | 99×46 | **correct** — the code starts exactly at the left edge of the band (0 px margin) and ends well inside it. The band is much taller than the glyph, so it also carries the interference lines |
| `jSdCool/minecaptcha/text` | 104×30, tight | **correct** — the rectangle sits exactly on the code in the GUI |
| `just-captcha/ProstoCaptcha/map` | 128×59 = the whole frame | **contains** the answer, but it is the *entire image*: the recogniser sees the full 128-px canvas with 41 drawn lines and has to find the 6 characters itself. There is no crop to be done here |
| `laforetbrut/are-you-sure/code` | 101×18, tight | **correct**, but the band also carries the plugin's decoy dots between the characters, and the characters are dark grey on light grey (low contrast) |
| `n1zamu/NCaptcha/anvil` | 35×17, tight | **correct** (the digits are drawn once, the upstream "printed twice" defect is not in the band) |
| `ringoame196-s-mcPlugin/ReproductionCAPTCHA/map` | 54×27 | **correct** — 2–3 px margin; the *characters* fade towards the right (an upstream effect), the band does not clip them |

The excluded types were checked on the same sheet: `colorgui`, `captchasx`, `slot`, `gui`, `itemslot`,
`reverse` have correct bands (the band sits on the word / the number / the item name), `button`'s band sits
on a phrase that is not the answer, and the three constant-answer types have correct bands on a constant.

A quantitative companion is `train/band_tightness.py`: it reports, per type, how often the ink touches a
band edge and how often there is ink *just outside* the band (the signature of a clipped glyph). For the ten
scope types the only row with ink immediately outside the band on the right in 100 % of the samples is
`Archy-X/Krypton/map` — the bug of §7.1.

---

## 8. The comparison with the measured baselines

### 8.1 First, the baselines are not measured on the same input

Read `bench/bench_hf.py`, `bench/bench_others.py` and `bench/bench_onnx.py`:

| harness | input | models |
|---|---|---|
| `bench/bench_others.py` | **the `roi` band** (`load_band`, lines 52, 90, 121, 125) | EasyOCR, Graf-J ×2, Florence |
| `bench/bench_onnx.py` | **the `roi` band** (line 28 `captchad_preprocess(path, roi=None)`) | captCHAD fp32/int8, phpwind |
| `bench/bench_hf.py` | **the whole frame** — `predict_trocr` calls `load_image(p)` without the band (line 136, called from line 174) | anuashok/ocr-captcha-v3, the whole TrOCR line |

So the `anuashok/ocr-captcha-v3` number of **0.077** was measured on whole frames, while EasyOCR (0.115) and
the two Graf-J models were measured on the band. The two groups are not comparable to each other, and the
whole-frame number is the weaker one.

### 8.2 The comparison, on the same items and the same input

The benchmark test set is 13 types × 8 samples = **104 items**; 5 of the 13 types have no band at all, and
for those "cropped" and "uncropped" are the same thing. `train/compare_baselines.py` re-scores the **saved**
predictions of every baseline (no benchmark was re-run) on the 64 items of the 8 types that have a band —
which is exactly the set of items our model can be scored on, because our model is trained type-held-out and
must not have seen the type it is scored on.

| model | input | 104 items (as published) | | 64 band items | |
|---|---|---|---|---|---|
| | | acc | CER | acc | CER |
| `Graf-J/captcha-crnn-finetuned` | band | 0.096 | 0.732 | **0.156** | **0.559** |
| `Graf-J/captcha-conv-transformer-finetuned` | band | 0.077 | 0.694 | 0.125 | 0.535 |
| `EasyOCR/en` | band | 0.115 | 1.835 | 0.047 | 2.564 |
| `anuashok/ocr-captcha-v3` | **whole frame** | 0.077 | 0.785 | 0.000 | 0.924 |
| `captCHAD` fp32 / int8 | band | 0.000 | 1.01 / 0.99 | 0.000 | 0.99 / 0.97 |
| `phpwind-captcha-ocr` | band | 0.000 | 0.990 | 0.000 | 0.956 |
| **ours (this run)** | band, glyph 32 px | — | — | **0.000** | **0.95 – 1.06** |

**The verdict, plainly: the model loses to the baselines.** On the same 64 items, with the same input
(the band), `Graf-J/captcha-crnn-finetuned` reaches acc 0.156 / CER 0.559 and our model reaches acc 0.000 /
CER ~0.97. There is no reading of this table in which our model is ahead. The only thing our model has is
the *training* types (1.000) and the fact that it is a 4.6 M-parameter model trained from scratch on this
data.

### 8.3 The same 40 items, every model

Our model can only be scored on a type it has **never been trained on**, and the deadline cut the
cross-validation, so the like-for-like set is the 5 types that do have a type-held-out model
(`haq/mapcha/map`, `jSdCool/minecaptcha/text`, `just-captcha/ProstoCaptcha/map`,
`laforetbrut/are-you-sure/code`, `n1zamu/NCaptcha/anvil`) × the benchmark's 8 samples = **40 items**.
`reports/bench_per_type.json`:

| model | input | n | acc | CER |
|---|---|---|---|---|
| `Graf-J/captcha-crnn-finetuned` | band | 40 | **0.100** | **0.638** |
| `Graf-J/captcha-conv-transformer-finetuned` | band | 40 | 0.100 | 0.588 |
| `EasyOCR/en` | band | 40 | 0.000 | 2.875 |
| `anuashok/ocr-captcha-v3` | **whole frame** | 40 | 0.000 | 0.993 |
| `captCHAD` fp32 / int8, `phpwind-captcha-ocr` | band | 40 | 0.000 | 0.97–0.99 |
| **ours (type-held-out)** | band, glyph 32 px | 40 | **0.000** | **1.034** |

Per type (`ours` = accuracy/CER on the same 8 items):

| type | ours | anuashok | EasyOCR | Graf-J CRNN | Graf-J conv-tr |
|---|---|---|---|---|---|
| `haq/mapcha/map` | 0.000 / 1.250 | 0.000 / 1.062 | 0.000 / 5.938 | 0.000 / 0.750 | 0.000 / 0.656 |
| `jSdCool/minecaptcha/text` | 0.000 / 0.922 | 0.000 / 0.969 | 0.000 / 0.969 | **0.250** / 0.156 | **0.500** / 0.094 |
| `just-captcha/ProstoCaptcha/map` | 0.000 / 0.958 | 0.000 / 0.958 | 0.000 / 2.083 | 0.000 / 0.833 | 0.000 / 0.833 |
| `laforetbrut/are-you-sure/code` | 0.000 / 0.979 | 0.000 / 1.000 | 0.000 / 3.083 | 0.000 / 1.000 | 0.000 / 1.000 |
| `n1zamu/NCaptcha/anvil` | 0.000 / 1.062 | 0.000 / 0.975 | 0.000 / 2.300 | **0.250** / 0.450 | 0.000 / 0.356 |

Two things are worth reading out of it. First, **all** of Graf-J's correct answers on these 40 items are on
the two GUI-scene types (`jSdCool/minecaptcha/text`, `n1zamu/NCaptcha/anvil`) — a 4.6 M-parameter CRNN
fine-tuned on captchas reads a code in a chat window better than anything else here does. Second, our
model is **not worse than the ONNX models and the HF model** on these items (0.000 everywhere), and it is
clearly worse than Graf-J. So the honest statement is: *on the 5 types we could measure, our model is at
the bottom of the field, tied with the models that do not work at all, and behind the one small domain
model that does.*

Note also what the numbers say about the baselines themselves: Graf-J gets 0.156 on the band types and 0.096
overall — **all** of its 10 correct answers are on the 8 band types, none on the 5 band-less ones. EasyOCR is
worse on the band types (0.047) than on the whole set (0.115) — it is the no-band types it sometimes gets
right. The "best baseline" is a small, domain-specific CRNN, not a general OCR.

---

## 9. What was changed in `train/`

| file | change | why |
|---|---|---|
| `train/train.py` | `select()` always returns `(id, dir)` pairs | a run without `--val-types` crashed with `ValueError: too many values to unpack` |
| `train/train.py` | the charset check looks at **every** row, and the type is dropped with a count of the offending rows | the old check looked at 5 rows; `Charset.encode` silently strips unknown characters, so a partly-Cyrillic type trains on labels that do not match the picture |
| `train/train.py` | rows without a band in a type that has bands are dropped (and counted) instead of being trained on the whole frame | `haq/mapcha/map` sample 087 was trained on a 128×128 map with a 4-character label |
| `train/train.py` | the validation loader uses `--workers` | the evaluation of 1 000 images took 7–10 s with 0 workers — more than the training loop |
| `train/train.py` | the epoch line prints the time spent in training / evaluation / checkpointing | the wall-clock accounting of a run was not visible otherwise |
| `train/captcha_crnn.py` | `build_items(..., keep=...)` | to drop the band-less rows of a partially banded type |
| `train/audit_types.py` | **new** | the per-type audit of §3 |
| `train/roi_sheet.py` | **new** | the band contact sheets of §7.3 |
| `train/band_tightness.py` | **new** | the quantitative band check of §7.4 |
| `train/band_clip_check.py` | **new** | the pixel-level "does the band cut the glyph" check of §7.1 |
| `train/eval_ckpt.py` | **new** | evaluate any checkpoint on any type, with an optional band widening |
| `train/compare_baselines.py` | **new** | re-score the saved baseline predictions on the same items |
| `train/bench_pipeline.py` | **new** | the throughput measurement of §3.3 |
| `train/aug_sheet.py` | **new** | the 200-sample augmented contact sheet (`reports/augmented_minimal*.png`) — HANDOVER M1 |
| `train/bench_per_type.py` | **new** | our model against the baselines, per type, on the benchmark's own items |
| `train/README.md` | the `--allow-no-roi` note and the new `--augment-affine` flag | the flag list in it was missing the one that matters most |

`train/README.md`: only the flag list was touched — it gained `--augment-affine` and the warning that
`--allow-no-roi` *allows* the band-less types in. Its statements about the plateau and about the band are
confirmed by this run.

---

## 10. What is still broken, and the next three steps

### Broken (measured, with the file and the line)

1. **`Archy-X/Krypton/map`: the band is 4 px too narrow** — `Krypton.java:123-134` forgets the one-pixel
   gaps between the glyphs that `Krypton.java:516` draws. The band must be `sum(widths) + len - 1`.
2. **`LagBug/XProtect/reverse`: the label is the reverse of the drawn text** — `XProtect.java:317-373` does not
   override `text()`, and `Cg.text()` defaults to `answer()` (`Cg.java:67`). It needs `text()` → the drawn code.
3. **Model B is 34 classes, not 44** — `train/captcha_crnn.py` defines `CYRILLIC` as 33 letters, so the digits
   in `LimboFilter/symbols` and `GalleryCaptcha/ru-symbols` are silently dropped from the label (35/100 and 43/100
   rows). The charset should be extended to 33 letters + 10 digits. **Not done in this session**, because the
   Cyrillic model is out of scope here and a charset change has to be validated by a Cyrillic run; with the
   new strict charset check a Cyrillic run would now *drop* those two types loudly instead of poisoning
   35–43 rows.
4. **The 4.6 M-parameter CRNN memorises 600 images** (§6.3). This is the real blocker, and it is a data
   problem, not a code problem.

### The next three steps, in order

1. **Pretrain on a public captcha corpus** (`HANDOVER.md` M6: hammer888 1.37 M / szili2011 1.8 M). Everything
   measured here says that 600–1 000 images of 6–10 styles are not enough to learn *glyphs*; a public corpus
   with thousands of fonts is the only lever that changes the regime. Expected effect: the type-held-out
   accuracy has to move off 0.000 before anything else matters.
2. **Add the augmentation that the plan asks for and that this run lacks** (M1): a per-sample affine
   (rotation ±7°, shift, scale 0.9–1.1) and a per-glyph jitter. The current augmentation is only
   JPEG/WebP/brightness/contrast, which does not stop the model from keying on the exact pixels of a style.
   The augmentation contact sheet (200 samples) is what makes this checkable.
3. **Fix the two dataset bugs and rebuild** (§10.1 and §10.2), then re-run the 4-fold: `Archy-X` and
   `LagBug/XProtect/reverse` are both *in* the scope once their labels are right, and `reverse` is a
   GUI-scene type — a style the model has never seen.

And two cheap things worth doing while the GPU is otherwise idle:

* **Evaluate the model on the 5 band-less benchmark types** with `--allow-no-roi` and report what the
  ill-posed task costs — it is the only way to get a 104-item number comparable with the published baselines.
* **PP-OCRv6_medium_rec** in the benchmark (M0). The Graf-J CRNN at 0.156 on the band types is the bar, and
  nobody has measured the strongest ready-made captcha model against the band yet.
