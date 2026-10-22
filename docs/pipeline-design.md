# PIPELINE DESIGN — from a captcha picture to the answer the player types

---

> **Заметка (2026-10-22): документ переехал** из `reports/PIPELINE_DESIGN.md` в `docs/pipeline-design.md` —
> это **проектная записка, а не измерение**, и `reports/` теперь содержит только измеренные результаты.
> Относительные ссылки внутри документа поправлены; измеренные числа остались в
> `reports/TRAINING_MINIMAL_LATIN.md`.

**Date:** 2026-10-21 · **Status:** a **design note for the next session**, not a measurement.
**Measured numbers live in [`reports/TRAINING_MINIMAL_LATIN.md`](TRAINING_MINIMAL_LATIN.md);** this document
only points at them and proposes the parts that do not exist yet. Every number in the "measured" rows below
was re-counted from the `labels.jsonl` files in this repository on 2026-10-21; everything else is marked
**proposal** or **not verified**.

---

## 1. What this document is, and what it is not

The project has a dataset, a benchmark and a training pipeline. What it does **not** have is the thing that
turns a picture into the string a player has to type: a **pipeline** that knows which plugin is being
served, crops the answer out of the picture, reads it with the model, and applies the plugin's conversion
rule.

This note writes that pipeline down, in three layers, with the parts that already exist marked as such and
the parts that do not exist marked as proposals.

| | |
|---|---|
| It is | a design: the layer split, the per-plugin knowledge, the order of the work |
| It is not | a report of a working solver. The recogniser exists and is measured; **layers 1 and 3 do not exist in the code** |

---

## 2. The three-layer scheme

```
picture ──▶ [1] cropper  (knows the plugin) ──▶ [2] recogniser (shared) ──▶ [3] solver (knows the plugin) ──▶ answer
```

| layer | what it is | implemented as | what it contributes |
|---|---|---|---|
| **1. cropper** | finds the rectangle that holds the answer | a per-plugin constant or a per-plugin rule | removes everything that is not the answer; without it the recogniser reads the wrong line |
| **2. recogniser** | reads the cropped band | `train/captcha_crnn.py` — CRNN + CTC, 4 623 615 parameters, 63 classes | the string that is drawn |
| **3. solver** | converts the drawn string into the typed answer | a per-plugin function, ~10 lines | `reverse` → reversed, `19 - 11` → `8`, «шестьсот девяносто» → `690` |

The two outer layers are **per plugin** and are a few lines each. The middle layer is **shared** and is the
only part that needs a neural network. That split is the whole point of the design: the expensive part is
trained once, the cheap parts are written per plugin and are deterministic.

### 2.1 The skeleton

Real APIs only: `CHARSET` / `build_encoder` (`train/captcha_crnn.py:36,67`), `CRNN` (`:340`),
`greedy_decode(logits, decode)` returning `(text, confidence)` pairs (`:378`), the band crop
(`CaptchaDataset._load`, `:158-169`) and the glyph-height measurement (`CaptchaDataset._line_height`, `:171`).
Everything else in this sketch is **proposed** and does not exist in the repository yet.

```python
from PIL import Image
import torch
from captcha_crnn import CHARSET, build_encoder, CRNN, greedy_decode

# PROPOSED: the per-plugin table, generated from the labels.jsonl files (see 4.1)
CONFIG = build_config(["dataset/out", "dataset/out_ru"])       # {type -> roi, alphabet, lengths, solver}

def solve(type_id, text):                                       # layer 3
    if type_id == "LagBug/XProtect/reverse":
        return text[::-1]
    if type_id in ("LagBug/XProtect/equation", "FeelingAlive0/AdvancedCaptcha/math", "Mrbysco/Captcha/math"):
        return str(eval(text))                                  # arithmetic
    if type_id in ("LimboFilter/map", "GalleryCaptcha/ru-numberword", "GalleryCaptcha/ru-numberword-caption"):
        return RUSSIAN_WORDS_TO_DIGITS[text]                    # lexicon
    return text

def crop(img, roi):                                             # layer 1, the fixed-rectangle variant
    x, y, w, h = roi
    return img.crop((x, y, x + w, y + h)).convert("L")

def read(band, model, encoder, cfg):                            # layer 2
    band = scale_to_glyph_height(band, 32)                      # the trainer's own scale
    x = torch.from_numpy(normalise(band)).unsqueeze(0).unsqueeze(0)
    with torch.no_grad():
        logits, _t = model(x)
    text, conf = greedy_decode(logits, encoder.decode)[0]       # (text, confidence)
    text = "".join(c for c in text if c in cfg.alphabet)        # the alphabet mask
    if len(text) not in cfg.lengths:                            # the length prior
        return None, conf
    return text, conf

def solve_captcha(png_path, type_id, model, encoder, cfg):
    band = crop(Image.open(png_path), cfg.roi)
    text, conf = read(band, model, encoder, cfg)
    if text is None or conf < cfg.min_confidence:               # human in the loop
        return None, conf
    return solve(type_id, text), conf
```

---

## 3. Layer 1 — the cropper

**Measured:** the band is already known for the dataset. In the current tree **29 of the 46 types carry a
band** (`roi` non-null), 17 do not, and **1 701 of the 4 600 label rows have `roi = null`**
(re-counted from every `labels.jsonl`; the same figure is in `agents/INDEX.md` §3 and
`reports/TRAINING_MINIMAL_LATIN.md` §7). The crop itself is 4 lines (`train/captcha_crnn.py:162-168`).

**Proposal — three variants**, in increasing order of cost per plugin:

| variant | what it does | fits | cost |
|---|---|---|---|
| **fixed rectangle** | the band is a constant of the plugin | 29 types that already have a band | ~0 lines - the constant is already in `labels.jsonl` |
| **template search** | find the line after a known marker ("Tries Left:", the window title) | scene types where the answer moves | ~30 lines per plugin |
| **text detector** | run a detector over the whole frame | types with no band and no marker | a second model; not proposed for now |

**What is not there:** no cropper code exists — only the *data* for the fixed-rectangle variant. The
template-search and detector variants are proposals. Whether a band-less type even *has* a visible answer is
discussed in §8 and is **not measured**.

---

## 4. Layer 2 — the recogniser, with the plugin's hints

The plugin is known at inference time, so several pieces of information are free. They are also **the
cheapest accuracy in the whole project**: no training, no data, just a constraint on the decoder.

| parameter | where it comes from | what it buys |
|---|---|---|
| `roi` — the band | the `labels.jsonl` of the type (29 of 46 types) | the recogniser is shown the answer line and nothing else |
| **alphabet mask** | the characters observed in the type's 100 labels | `BotFilter/map` is digits only; `CaptchaVerifyZ/map` is `0-9A-Z`; `GalleryCaptcha/ru-web` uses upper + lower + digits. Measured per type, below. |
| **length prior** | the lengths observed in the type's 100 labels | `CaptchaVerifyZ/map` is exactly 5, `GalleryCaptcha/ru-web` is exactly 5, `BotFilter/map` is 4 or 5 |
| **candidate bands** | several bands of the same type, when the answer moves | pick the band whose decode has the highest confidence |
| **model choice** | the alphabet of the type | Latin model (63 classes) vs Cyrillic model — see the class-count problem in §9 |

### 4.1 The per-plugin table is generated, not hand-written

Every field above is derivable from the `labels.jsonl` files: the band from `roi`, the alphabet from the
union of the characters in `text`, the lengths from the set of `len(text)`. A generator script would produce
one JSON per type. **Proposal** - the script does not exist yet.

### 4.2 The measured alphabet and length per type

Re-counted from the 4 600 label rows on 2026-10-21. "A" = upper case only, "a" = lower case only,
"Aa" = both, "0" = digits, "+" = other characters (space, `_`, `+`, `-`, `=`).

| type | band | alphabet | length | distinct answers / 100 |
|---|---|---|---|---|
| `BotFilter/map` | no | `0` | 4–5 | 100 |
| `CaptchaVerifyZ/map` | yes | `A0` | 5 | 100 |
| `GalleryCaptcha/ru-web` | yes | `Aa0` | 5 | 100 |
| `JSH32/Minecaptcha/map` | yes | `Aa0` | 4 | 100 |
| `haq/mapcha/map` | yes | `Aa0` | 4 | 100 |
| `laforetbrut/are-you-sure/code` | yes | `A0` | 6 | 100 |
| `ringoame196-s-mcPlugin/ReproductionCAPTCHA/map` | yes | `A0` | 5 | 100 |
| `jSdCool/minecaptcha/text` | yes | `Aa0` | 8 | 100 |
| `just-captcha/ProstoCaptcha/map` | yes | `Aa0` | 6 | 100 |
| `n1zamu/NCaptcha/anvil` | yes | `0` | 3–5 | 100 |
| `LagBug/XProtect/reverse` | yes | `Aa0` | 6 | 100 |
| `Archy-X/Krypton/map` | yes | `Aa0` | 5 | 100 |

A note on `ru-web`: the task statement for this note said "all 62". The **measured** alphabet of its 100
labels is upper + lower + digits; the *model's* charset is the full 62-symbol set
(`train/captcha_crnn.py:36`). A mask built from the observed alphabet is the tighter of the two, and it is
what the generator would produce.

---

## 5. Layer 3 — the solver

**Proposal.** Nothing of this layer exists in the code today, and the training agent did not write it.

| family | types | the rule | size |
|---|---|---|---|
| reversed | `LagBug/XProtect/reverse` | reverse the string | 1 line |
| arithmetic | `LagBug/XProtect/equation`, `FeelingAlive0/AdvancedCaptcha/math`, `Mrbysco/Captcha/math` | evaluate the expression (`19 - 11` → `8`) | ~3 lines, **with a whitelist of characters** - never `eval` on untrusted text |
| Russian number words | `LimboFilter/map`, `GalleryCaptcha/ru-numberword`, `GalleryCaptcha/ru-numberword-caption` | a lexicon of Russian number words → digits | a lexicon of ~40 entries |
| none | the other 38 types | `text == answer`, nothing to do | 0 lines |

The solver is deterministic and its inputs are all measured: `text != answer` in **8 of the 46 types**
(3 arithmetic, 3 Russian number words, and the same words inside the two rotated frames
`LimboFilter/framed2x2` and `framed3x3`; re-counted over every row, and recorded in `agents/INDEX.md` §3.3).
The other 38 types need no conversion.

**Important:** the Russian number family is **multi-line** - the band is a two or three line block, and the
glyph is only a fifth of the band (`train/captcha_crnn.py:171-186`). It therefore needs a per-line cropper
*before* the recogniser, not just a solver. **Proposal**, not measured.

---

## 6. The training recipe in three stages

| stage | what it is | data | status |
|---|---|---|---|
| **1. pretrain** | learn *glyphs* on a public captcha corpus | hammer888 1.37 M / szili2011 1.8 M images | **not done** - proposed; the corpus is named in `HANDOVER.md` §7 (M6) and `reports/MODEL_PLAN.md` §6 |
| **2. fine-tune per plugin** | adapt the model to one plugin's style | the 100 generated images of that plugin | **measured, and it works**: 1.000 exact match / 0.000 CER on the types it was fine-tuned on (`reports/TRAINING_MINIMAL_LATIN.md` §1 and §6.3) |
| **3. assemble the slot** | attach the cropper, the mask, the length prior and the solver to the fine-tuned model | - | **not done** - proposed; this document |

Stage 2 is the important one to understand: **the model is excellent on a plugin it was fine-tuned on and
worthless on a plugin it has not seen** (0.000 exact match on the held-out types, CER 0.912–1.058, median
0.954 - `reports/TRAINING_MINIMAL_LATIN.md` §1, §6.3, §6.4). Fine-tuning per plugin is therefore not a
workaround, it is the architecture of the solution: one shared pretrained model plus a small per-plugin
adapter, plus the two cheap per-plugin layers.

**Alternative to stage 2 for a plugin whose position moves:** a clone of the generator that synthesises tens
of thousands of variants of that plugin. This repository already has the generators
(`dataset/generator/`, `dataset/generator_ru/`) - but they produce 100 images per type, and the volume is
the thing that is missing. **Proposal.**

---

## 7. The implementation plan, step by step

| # | step | expected effect | state |
|---|---|---|---|
| **1** | build the whole pipeline: cropper + alphabet mask + length prior + solver + a confidence threshold, **around the model that already exists** | a correctly *formatted* answer end to end, with a "ask a human" path when the confidence is low. **No new neural network, ~300 lines.** | not started (proposal) |
| **2** | pretrain on a public captcha corpus (hammer888 / szili2011) | the only lever that changes the regime: the model has to learn *letters*, not *styles* | not started (proposal; `HANDOVER.md` §7 M6) |
| **3** | fine-tune per plugin on its 100 generated images | the measured 1.000 on the plugin it was tuned for | **the mechanism exists and is measured** (`reports/TRAINING_MINIMAL_LATIN.md` §1, §6.3) |
| **4** | fix the two broken types in the dataset, then regenerate and re-measure | `Archy-X/Krypton/map` (the band clips the fifth character) and `LagBug/XProtect/reverse` (the `text` field holds the reversed string) become trainable; the 4-fold can be completed | the bugs are **measured and documented** (`reports/TRAINING_MINIMAL_LATIN.md` §7.1, §7.2); the fix and the rebuild are **not done** |

Step 1 is worth doing **before** step 2: it is small, it needs no new data, and it makes every later
measurement meaningful, because the pipeline then produces an answer in the right format.

---

## 8. The limits of applicability — stated precisely

There are **17 types of the 46** whose labels carry `roi = null`, and **1 701 of the 4 600 rows** have a
null band (measured by re-counting every `labels.jsonl`; the same figures are in `agents/INDEX.md` §3.2 and
`reports/TRAINING_MINIMAL_LATIN.md` §7).

Two different statements get mixed up here, and only one of them is a measurement:

**(a) Measured: the band was not computed for these types.** `roi` is null, so the fixed-rectangle cropper
has nothing to crop. That is a fact about the dataset, and it is what the trainer reacts to: a type without
a band is excluded by default, and `--allow-no-roi` exists only to let it back in
(`train/train.py:195-213`).

**(b) Hypothesis, NOT measured: "the answer is not in the picture at all."** This is *not* true for all 17
types, and the difference matters:

| case | example | why it is different |
|---|---|---|
| the answer may well be drawn, the band was simply never computed | `LagBug/XProtect/code` (100 distinct 6-symbol answers, 100 distinct texts) | nothing in the data says the code is not in the frame; only that nobody drew a rectangle around it |
| the answer occupies the whole frame | `BotFilter/map` (digits, 4–5 characters, 128×128) | the code is the picture; a cropper would be "the whole image" |
| the answer is not text at all | `CaptchaGUI/clickblock` (the answer is a slot index), `GalleryCaptcha/ru-object-swatch` (the answer is a colour name) | a different task, not an OCR task |
| the answer is one of a few constants | `China2B2T/Captcha/wool`, `LagBug/XProtect/different` | a single answer per type |

The 17 band-less types, in full: `Archy-X/Krypton/menu`, `China2B2T/Captcha/wool`,
`InstantlyMoist/Captcha/textcaptcha`, `LagBug/XProtect/{code,color,different,map,picture}`,
`GalleryCaptcha/ru-object-swatch`, `BotFilter/map`, `CaptchaGUI/clickblock`, `irootdev/AnBot/captcha`,
`jonesdevelopment/sonar/{standard,legacy,complex}`, `LimboFilter/{framed2x2,framed3x3}`.

**What would settle (b):** drawing the band for those 17 types and looking at it. The contact-sheet tooling
already exists (`train/roi_sheet.py`, `train/band_tightness.py`, `train/band_clip_check.py`) and the
generator-side rule is in `AGENTS.md` §5: *a band that does not fit inside the frame is not a band* -
`roi()` returns null rather than a rectangle that holds part of the answer. **Not done.**

---

## 9. Links to the rest of the repository

| step | what already exists | what is missing | where it is described |
|---|---|---|---|
| dataset and bands | 4 600 labelled images, 46 types, `roi` on 29 types; the band rule; the checkers `tools/check_labels_and_roi.py` and `tools/check_band_vs_answer.py` | the bands for the 17 band-less types; the colour-level band rule (it lives only in `build/scratch/roilabel.py`) | `AGENTS.md` §3, `agents/INDEX.md` §3, `reports/TRAINING_MINIMAL_LATIN.md` §7 |
| the recogniser | `train/captcha_crnn.py` (model, charset, dataset, decode) and `train/train.py` (loop, type-held-out split, checkpoints) | the per-type alphabet / length mask in the decoder; the Cyrillic model is **34 classes instead of 44**, so the digits in the Cyrillic labels are dropped silently | `reports/MODEL_PLAN.md` §4.1, §4.3, §4.4; `HANDOVER.md` §3, §6.5 |
| the training recipe | the fine-tune-per-plugin step, measured at 1.000 on the tuned types | the pretrain stage on a public corpus; the completed 4-fold (folds C and D were not finished) | `HANDOVER.md` §7 (M4, M6); `reports/TRAINING_MINIMAL_LATIN.md` §6.4, §10 |
| the cropper | the band data, and the crop itself (4 lines) | any cropper code; the template-search and detector variants | `reports/TRAINING_MINIMAL_LATIN.md` §7.3 (contact sheets) |
| the solver | the rule per family, derivable from the labels | the solver code itself | `HANDOVER.md` §2 (groups A/B/C) |
| the publishing | `train/export_hf.py` exists but was **never executed** | the HF release, `reports/HF_RELEASE.md`, the per-family dataset repos | `HANDOVER.md` §7; `reports/MODEL_PLAN.md` §5 |
| the comparison | the measured baselines | the baselines were **not all measured on the same input**: `bench/bench_hf.py` reads the whole frame (`bench/bench_hf.py:136`), the other harnesses crop by the band | `reports/TRAINING_MINIMAL_LATIN.md` §8 |

---

## 10. Not verified

Everything in this document is a design except where it says otherwise. The honest list:

1. **Every part of layers 1 and 3 is a proposal.** No cropper code and no solver code exists in the
   repository. The *data* for the fixed-rectangle cropper exists; the code does not.
2. **The alphabet masks and length priors are measured from the dataset's own 100 labels per type**, which
   is what a generator would produce, but **they have never been applied to a decoder and their effect on
   accuracy has never been measured.** "The cheapest accuracy in the project" is a claim from the plan
   (`reports/MODEL_PLAN.md` §4.3), not a measurement of this repository.
3. **The Russian number lexicon** (words → digits) does not exist here; the 40-entry figure comes from
   `HANDOVER.md` §2 and was not re-counted.
4. **The pretrain corpora** (hammer888 1.37 M, szili2011 1.8 M) were **not downloaded, not inspected and
   not trained on**. Their size comes from `HANDOVER.md` §7 (M6). Whether they are downloadable, what
   licence they carry and whether they transfer to this domain are all unverified.
5. **The confidence threshold** for "ask a human" is a proposal. The measured basis for it is the
   per-character confidence of the wrong answers, 0.385–0.624
   (`reports/TRAINING_MINIMAL_LATIN.md` §6.2) - a range, not a threshold.
6. **The per-line cropper for the multi-line Russian number family** is a proposal; the measurement behind
   it is the glyph-height analysis in `train/captcha_crnn.py:171-186`.
7. **The 17 band-less types were not examined one by one.** §8(b) is explicitly a hypothesis; the split
   between "the band was never drawn" and "there is no text to crop" is a reading of the labels, not a
   measurement of the pictures.
8. **The end-to-end accuracy of the finished pipeline is unknown and not estimable from the parts** - the
   recogniser's 0.000 on unseen types (`reports/TRAINING_MINIMAL_LATIN.md` §1) is the number that matters
   for any type that has not been fine-tuned.
9. **The "generator clone" alternative** in §6 is a proposal: the generators exist and are faithful
   re-implementations, but the volume (tens of thousands of variants per plugin) has never been produced,
   and the fonts are machine-dependent, so the dataset is an artefact rather than a function
   (`agents/INDEX.md` §6).

---

*Design note written 2026-10-21. The measurements it cites were made in the same session and are stored
in `reports/TRAINING_MINIMAL_LATIN.md`; the type table in §4.2 and the counts in §8 were re-derived here
directly from the `labels.jsonl` files. No measured result was edited while writing this.*
