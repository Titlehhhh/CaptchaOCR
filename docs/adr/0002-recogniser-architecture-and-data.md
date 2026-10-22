# REVIEW — `reports/MODEL_PLAN.md`

---

> **ADR 0002 — Распознаватель с нуля против готовых движков, и данные как главный рычаг.**
>
> - **Дата:** 2026-10-22 · **Статус:** принято (план исполняется) · **Решение автора проекта:** владелец
> - **Контекст:** этот документ — ревью `reports/MODEL_PLAN.md`: проверялась каждая проверяемая цифра
>   (заново пересчитана по `labels.jsonl`), предлагаемый CRNN был собран в plain PyTorch, каждое
>   утверждение про transformers 5.x сверено с локально установленной версией 5.19.0.
> - **Решение:** брать **готовый движок как базу** (измерено: PP-OCRv6_medium_rec даёт 0.40 на нашем
>   датасете против 0.000 у нашего собственного CRNN на невиданных типах) и **не менять лосс** —
>   работа SVTRv2 (ICCV 2025) показывает, что CTC не уступает encoder-decoder. Главный рычаг —
>   **разнообразие данных**, а не объём: при одинаковых 600 тыс. сэмплов расширение покрытия
>   визуального пространства с 200 до 1000 кластеров даёт +5.38 п.п.
> - **Последствия:** оценка — только **type-held-out** (random split протекает: 34.3 % тестовых
>   сэмплов имеют свой точный ответ в обучающей половине), метрика — per-type + **медиана**, а не
>   среднее. Все измеренные числа лежат в `reports/`, а этот ADR хранит логику решения.

**Reviewer:** reviewer agent (task: find problems, not praise)
**Date:** 2026-10-21
**Subject:** `reports/MODEL_PLAN.md` (1212 lines), written 2026-10-21
**Method:** every checkable number re-measured from `dataset/out/` + `dataset/out_ru/`; the proposed CRNN
instantiated in plain PyTorch 2.14.1+cpu; every Hub/arXiv/PyPI claim re-queried live on 2026-10-21; every
transformers-5.x claim checked against the locally installed **transformers 5.19.0**.

All my scripts live in `build/review/` and are read-only with respect to `dataset/`, `AGENTS.md` and the plan.

---

## Status of this review (added later, the findings above are unchanged)

This review was written on 2026-10-21 against `reports/MODEL_PLAN.md` and the dataset of that day
(**44 types, 4 400 images**). Both have moved on since; the findings are kept exactly as they were
written and are annotated below with what has happened to them.

**The single most important change: recommendation 1 of §6 has been implemented.** The `roi` field
this review asked for - "the generators already know exactly where they drew the answer" - now exists
in every `labels.jsonl`, together with a `text` field that carries the string that is *drawn*. The
`roi` is the bounding box of the text band that carries the answer, or `null` when the whole frame is
the text; the rule it was computed with is *"a band that does not fit inside the frame is not a band"*,
so `roi()` returns `null` rather than a rectangle that holds only part of the answer. This turns
**B4**, **B5** and **B15** from proposals into facts, and the training pipeline already consumes it:
`train/captcha_crnn.py` crops to the band and scales the **glyph** to 32 px, which is exactly what
**B5** asked for.

The dataset itself has also changed shape:

| | at the time of this review | now |
|---|---|---|
| types | 44 | **46** |
| labelled images | 4 400 | **4 600** |
| `dataset/out_ru/` | 10 types x 100 = 1 000 | **12 types x 100 = 1 200** |
| types carrying a text band | - (the field did not exist) | **29 of 46** |
| `ru-puzzle2x2` / `ru-puzzle3x3` | 2 types | **gone** - the puzzle family is LimboFilter's `FRAMED_CAPTCHA`, generated as `LimboFilter/framed3x3` (384x384) and `LimboFilter/framed2x2` (256x256) |

And there is now a **training pipeline** (`train/captcha_crnn.py`, `train/train.py`, `train/README.md`)
on a **GPU**: the machine has an NVIDIA GeForce GTX 1080 Ti (11.8 GB, sm_61) and a CUDA build in
`.venv-gpu/` (`torch 2.14.1+cu126`), so the "no GPU" premise of `reports/MODEL_PLAN.md` §0.2 is gone.
The model that was built is a CRNN + CTC with **4 623 615** parameters and **63** classes - a fourth
reading of the architecture spec, and it is the one that runs at 920 img/s on the GPU.

Findings that are now settled by that work:

| finding | state |
|---|---|
| **B1** the architecture does not instantiate | **superseded** - the built model is 4 623 615 parameters, and `train/captcha_crnn.py` is the working spec |
| **B2** the CTC constraint `T ≥ 2L+1` fails for 15 types | **addressed** - the dataset widens a sample until the time steps satisfy it, and the model checks that the feature rows match |
| **B3** the `[48, 320]` width clamp distorts square frames | **moot** - the input is the **band**, scaled by the glyph height, not the frame |
| **B4** 25 of the 44 types are scenes | **fixed** - the `roi` field exists; the same number is now 29 bands out of 46 types |
| **B5** `H = 32` normalises the frame, not the glyph | **fixed** - the pipeline crops to the band and scales the glyph |
| **B9** the per-type answer diversity and the `dopr`/`jmpu`/`aekns` strings | **fixed in the docs** - the answers are `drop`/`jump`/`sneak` |
| **B13** the puzzle family is misclassified | **obsolete** - the types are gone; the framed types are a solver problem, not a recogniser's training target |
| **B15** `ru-numberword` is a Cyrillic OCR task | **implemented** - `text` carries the spelled-out words and `answer` the digits |
| **M1** the scene/clean-text axis | **implemented** - see above |
| **B6**, **B7**, **B8**, **B17**, **B18** | **still open** - they are about the licence table, the Hub claim and the benchmark harness |

**B10**, **B11**, **B12**, **B16**, **A1-A10**, **M2-M10** are measurements or advice taken against the
old 44-type tree; the numbers in them that are quoted as "44 types" or "4 400 images" are now
"46 types" and "4 600 images", and the type lists that mention `ru-puzzle*` refer to the framed types
of LimboFilter.

---

## 0. Verdict in one paragraph

The plan's *shape* is right — a small CRNN+CTC trained from scratch on this dataset, a type-held-out
validation protocol, a permissive licence, an ONNX export, and "the dataset is not one task" are all good
calls, and a remarkable number of the quoted external facts check out exactly. But the plan rests on a set of
measured numbers that are **wrong in nine places**, on an **architecture spec that does not instantiate**,
and on a **taxonomy that misses the single most important property of this dataset**: 25 of the 44 types are
not "an image of a string", they are *scenes* (Minecraft chat, inventory GUIs, web panels) in which the answer
is one string among several. The plan's central technical argument — "CTC is alignment-free, so it does not
need a segmentation or a character detector … a decisive advantage on captchas where the text can be anywhere
in the frame and the 'background' is often other text" (L177-L179) — is **exactly backwards for those 25
types**. Nothing in the plan's family A/B/C split can express "the image contains distractors".

Three of the four headline numbers the plan will put on a model card (`~2.2 M params`, `20 of 44 types have
a fixed answer length`, `per-type answer diversity 4…62`) are wrong. Two of them are wrong in a direction that
silently corrupts the experiment. Fix those before writing any training code; the rest of the plan is sound
and can be followed almost verbatim.

---

## 1. Blocking problems

### B1. The §4.2 architecture does not instantiate, and the parameter count is 2.4–2.6× the plan's

The plan's spec (L553-L569) is:

```
conv1 3x3 1→32 ; pool1 2x2   -> 16 x W/2
conv2 3x3 32→64 ; pool2 2x2  ->  8 x W/4
conv3 3x3 64→128; pool3 2x1  ->  8 x W/4   (keep the width!)
conv4 3x3 128→256; pool4 2x1 ->  8 x W/4   (keep the width!)
conv5 3x3 256→256; pool5 2x1 ->  4 x W/4
reduce Conv2d(256,256,1x1) -> 4 x W/4 ; reshape (B, T, 4*256 = 1024)
```

The annotations are wrong. A `(2,1)` MaxPool halves the **height** and keeps the width. Starting from the
plan's own `H = 32` (L529, L741):

```
32 --pool1(2,2)--> 16 --pool2(2,2)--> 8 --pool3(2,1)--> 4 --pool4(2,1)--> 2 --pool5(2,1)--> 1
```

The final feature map is **1 row**, not 4, so the reshape is `(B, T, 1*256 = 256)`, not `4*256 = 1024`.
Instantiating the spec verbatim raises:

```
RuntimeError: input.size(-1) must be equal to input_size. Expected 1024, got 256
```

(`build/review/arch_check2.py`, reading B.) The spec is only self-consistent if the input is `H = 64`
(64→32→16→8→4→2→1 — no, that also ends at 1) — the only reading that gives a final height of 4 from
`H = 32` is `pool3 (1,1)`, `pool4 (1,1)`, `pool5 (2,1)`. Three mutually consistent readings exist, and I
instantiated and timed all of them:

| reading | final H | LSTM input | **params** | train img/s @32×128 | infer img/s |
|---|---|---|---|---|---|
| **A** literal `(2,1),(2,1),(2,1)` | 1 | 256 | **3 710 725** | 170.5 | 658.5 |
| **B/C** annotations honoured, `H = 64` or pools `(1,1),(1,1),(2,1)` | 4 | 1024 | **5 283 589** | 99.0 | 370.6 |
| **D** reading C with LSTM hidden = 128 | 4 | 1024 | **2 640 389** | 127.2 | 438.3 |
| *plan's claim* | 4 | 1024 | *2 020 000 (L76) / "≈2.2 M" (L743)* | *150 (L81)* | *451 (L81)* |

**The plan's ~2.2 M is not reproducible from the plan's own architecture under any consistent reading.**
The closest is reading D (2.64 M), which needs the LSTM hidden size silently changed from 256 to 128.

Consequences:

* L743 `model | §4.2, ≈2.2 M params` → **5.28 M** (or 3.71 M if the literal pools are kept and the LSTM
  input is fixed to 256). A 2.4–2.6× error.
* L76-L84 (the whole measured-throughput table) and L87-L90 / L763-L771 (the wall-clock table) were measured
  on a **2.02 M model that is not the one the plan specifies**. With the spec as annotated (5.28 M) training
  runs at **99 img/s at W=128 and 46 img/s at W=320** — so "23 s/epoch for 3 400 images" becomes 34 s at
  W=128 and 74 s at W=320, and "a 4-fold experiment is 2–3 h" becomes roughly 4–6 h. Not fatal, but the
  table must be re-measured against the model that will actually be trained.
* L157: *"A 2 M-param model has ~37 000 parameters per training image; a 334 M-param TrOCR has 76 000 per
  character."* — 2.02 M / 4 400 = **459** parameters per image, not 37 000 (≈80× off); and 334 M / 4 400 =
  75 909, which is *per image*, not *per character*. The comparison as written does not follow from its own
  numbers.
* L1187-L1189 cites `Graf-J/captcha-crnn-base` as "3.57 M" and calls the plan's shape "deliberately the shape
  of Graf-J". Graf-J's CRNN is 3 570 943 params — so the plan's 2.2 M is *not* Graf-J's shape either.

**Correct version of §4.2.** Either
(i) keep `H = 32` and write `pool3 (1,1)`, `pool4 (1,1)`, `pool5 (2,1)`, `reshape (B, T, 1024)` → 5.28 M, or
(ii) keep the literal `(2,1)` pools and write `reshape (B, T, 256)`, `LSTM(256, 256, 2, bidirectional)` →
3.71 M — which is also closer to Graf-J's 3.57 M and 25 % cheaper. Either is fine; what is not fine is
publishing a parameter count and a throughput table for a model that cannot be built.
*(Note: reading A and B differ in the LSTM input dim, so the plan's "4*256 = 1024" line is the only thing
that makes the 5.28 M number meaningful — but it requires the pools to be `(1,1),(1,1),(2,1)`, which the
plan does not say.)*

---

### B2. The plan's own CTC constraint `T ≥ 2L+1` fails for 15 of 44 types — including 3 of the 13 benchmark types

The plan is right that CTC needs `T ≥ 2L+1` (L572-L576) and right to insist on an assert. It then never
checks the assert against the geometry it specifies. With `H = 32`, `W = round(32·w/h)` clamped to
`[48, 320]` (L532) and `T = W/4` (L565), the constraint is violated for **15 types / 1 500 of 4 400 images**:

| type | frame | W | T | max L | need 2L+1 | |
|---|---|---|---|---|---|---|
| `LagBug/XProtect/code` | 130×130 | 48 | 12 | 6 | 13 | **FAIL** |
| `LagBug/XProtect/map` | 130×130 | 48 | 12 | 6 | 13 | **FAIL** |
| `just-captcha/ProstoCaptcha/map` | 128×128 | 48 | 12 | 6 | 13 | **FAIL** |
| `LagBug/XProtect/picture` | 114×174 | 48 | 12 | 6 | 13 | **FAIL** |
| `Z4OLLIEZ4/reCaptcha/captchasx` | 186×122 | 49 | 12 | 10 | 21 | **FAIL** |
| `jSdCool/minecaptcha/text` | 550×356 | 49 | 12 | 8 | 17 | **FAIL** |
| `Archy-X/Krypton/menu` | 380×346 | 48 | 12 | 17 | 35 | **FAIL** |
| `China2B2T/Captcha/wool` | 414×314 | 48 | 12 | 9 | 19 | **FAIL** |
| `LagBug/XProtect/different` | 380×180 | 68 | 17 | 13 | 27 | **FAIL** |
| `LagBug/XProtect/gui` | 380×216 | 56 | 14 | 17 | 35 | **FAIL** |
| `Yukun99/Captchas/itemslot` | 614×296 | 66 | 16 | 20 | 41 | **FAIL** |
| `FeelingAlive0/AdvancedCaptcha/button` | 430×84 | 164 | 41 | 27 | 55 | **FAIL** |
| `jSdCool/minecaptcha/image` | 640×398 | 51 | 12 | 70 | 141 | **FAIL** |
| `ru:GalleryCaptcha/ru-symbols` | 250×150 | 53 | 13 | 18 | 37 | **FAIL** |
| `ru:GalleryCaptcha/ru-object-swatch` | 250×150 | 53 | 13 | 7 | 15 | **FAIL** |

**Three of these are in the 13-type benchmark** (`XProtect/code`, `XProtect/map`, `ProstoCaptcha/map`).
With `zero_infinity=True` (L583) the CTC loss on those 300 samples is silently **zeroed** — they contribute
no gradient and are always wrong at eval — so the plan's own "in-domain 13-type" headline (L633-L637) is
capped at 10/13 = 77 % by its own preprocessing, before any modelling happens. The plan's assert would fire
on the plan's own benchmark set.

The root cause is the width downsample of 4 combined with the small widths. The plan checks `W = 192` (L572:
"for W=192 that is T=24 … With T = W/4 = 48 at W=192 there is comfortable room") and never checks `W = 48`,
which is what 18 of the 44 types produce.

**Correct version.** Either (i) halve the width only once (`pool2 (2,1)` instead of `(2,2)`) so `T = W/2`
and `W = 48 → T = 24 ≥ 13`; or (ii) keep `T = W/4` and make the *minimum* width `4·(2·L+1) = 52` for
6-character types (i.e. raise the clamp floor from 48 to 56 and give the 6-char types `W = 56 → T = 14`);
or (iii) normalise per type so that the *label* always gets enough frames (the natural place to enforce it is
the data-prep assert the plan already promises). The plan should also state the *consequence* of the assert
firing, because the current text says "assert, don't silently pad" without saying that `zero_infinity=True`
will silently drop the sample instead.

---

### B3. The `[48, 320]` width clamp silently reintroduces the aspect distortion the plan says it is avoiding

L532-L536: `W = round(32 * w / h)`, clamped to **[48, 320]**, and the stated reason is
*"Why aspect-preserving: … Squashing everything to a fixed 32×128 distorts glyph aspect ratios (a `5`
becomes wide) and the network learns a scale prior that does not transfer."*

But the clamp floor does exactly that, for **18 of 44 types**:

| type | native W = 32·w/h | after clamp | horizontal stretch |
|---|---|---|---|
| `XProtect/code`, `XProtect/map`, `JSH32/Minecaptcha/map` (130×130) | 32.0 | 48 | **×1.50** |
| `Archy-X/Krypton/map`, `haq/mapcha/map`, `AnBot/captcha`, `sonar/{standard,complex,legacy}`, `ProstoCaptcha/map`, `ringoame196/map`, `CaptchaVerifyZ/map`, `BotFilter/map`, `InstantlyMoist/textcaptcha` (128×128) | 32.0 | 48 | **×1.50** |
| `LagBug/XProtect/picture` (114×174) | 21.0 | 48 | **×2.29** (and 2.3× vertically squashed the other way) |
| `Mrbysco/Captcha/math` (520×560) | 29.7 | 48 | ×1.62 |
| `Archy-X/Krypton/menu` (380×346) | 35.1 | 48 | ×1.37 |
| `China2B2T/Captcha/wool` (414×314) | 42.2 | 48 | ×1.14 |

Every square captcha in the dataset — which is the *majority* of the text types — gets a 1.5× horizontal
stretch, and the model will learn "the glyphs are 1.5× too wide", which is exactly the scale prior the plan
says it wants to avoid. This interacts with B2: the clamp floor was presumably chosen to make `W ≥ 48` look
safe, and it is what breaks the CTC constraint.

**Correct version.** Make the clamp floor *type-dependent* (`W = max(4·(2L+1), round(32·w/h))`, i.e. derive
it from the label length) and state explicitly that square frames will be stretched unless H is raised
instead. Better: normalise by the **text band**, not by the frame (see B5).

---

### B4. 25 of the 44 types are *scenes*, not "an image of a string" — and the plan's taxonomy has no axis for it

This is the finding I would most want the author to read.

The plan's taxonomy (L130-L132) classifies by **what the answer is** (a string / a transformed string /
not a string). It never classifies by **what the image is**. Those are different axes, and the second one
dominates the first here.

Looking at the real samples (`build/review/sheet_scenes.png`, `sheet_rest.png`, `sheet_anvil_zoom.png`):

* **Single-string images (14 types).** `AnBot/captcha` ("fur" alone), `InstantlyMoist/textcaptcha`,
  `Archy-X/Krypton/map`, `sonar/{standard,complex,legacy}`, `ringoame196/map`, `XProtect/{code,map}`,
  `BotFilter/map`, `ru-web`, `ru-symbols`, `ru-numberword(-caption)`, `ru-puzzle*`.
* **Scene images (25 types)** where the frame contains *other text* and the answer is one string among
  several: `XProtect/{reverse, equation, slot, color, drop, jump, sneak, gui, picture, different}`
  (a Minecraft chat log with 3–4 background lines), `n1zamu/NCaptcha/anvil` (an anvil GUI), `haq/mapcha/map`
  ("Captcha / Tries Left: 4 / JAsb"), `JSH32/Minecaptcha/map` ("Type this in chat / Tries Left: 2 / ln5a"),
  `just-captcha/ProstoCaptcha/map` ("PROSTO CAPTCHA / 9SjzYd"), `laforetbrut/are-you-sure/code` (a full
  Minecraft dialog), `jSdCool/minecaptcha/text` (a "Captcha" dialog with a Response box and a button),
  `CaptchaVerifyZ/map` ("SECURITY VERIFICATION / B16OB / Type the code in chat"), `China2B2T/wool`,
  `FeelingAlive0/{button,math}`, `Mrbysco/Captcha/math`, `Z4OLLIEZ4/captchasx`, `Joey61021/colorgui`,
  `Yukun99/itemslot`, `Archy-X/Krypton/menu`.
* **Grounding (3)**: `ru-object-swatch`, `CaptchaGUI/clickblock`, `XProtect/different`.
* **Jigsaw (2)**: `ru-puzzle2x2/3x3`.
* **Unknowable (1)**: `jSdCool/minecaptcha/image` (the README states the mapping is unknowable by construction).

Measured support: 23 of 44 types have **≥ 3 separate text bands** in the frame (`build/review/legibility.py`).

This breaks four things in the plan:

1. **L177-L179** — *"CTC is alignment-free, so it does not need a segmentation or a character detector — a
   decisive advantage on captchas where the text can be anywhere in the frame and the 'background' is often
   other text (chat scenes, map titles, counters)."* For a scene, "the text can be anywhere in the frame" is
   the **problem**, not the advantage. A whole-image CTC with one target string per image is trained on an
   **ill-posed target**: the same pixels admit many labels (the code, the whole line, the whole frame). CTC
   will latch onto layout heuristics ("emit the line that is red", "emit the line after `Tries Left:`") that
   do not transfer to an unseen plugin. The plan's own measurement of the baseline shows the failure mode
   from the other side: EasyOCR transcribes the *whole* frame ("Captcha Tries Lelt: IMe Lel: 12 Sec",
   "PROSTO CAPTCHA", "Type this in chat Tries Left:") and gets CER > 1 (L313, L635). The plan never asks
   why, and the answer is "the target is a substring".
2. **The architecture itself (L15, L551-L569)** is specified as `image → string` with no localisation stage.
   For 25 types there is no "the string" in the image; there is *a* string in the image.
3. **L134** "Roughly 20 of 44 types are family A" — 8 of the 13 benchmark types are scene types, so the
   "in-domain" benchmark is mostly a scene-reading benchmark. The plan's expectation at L1161
   (*"Expect: in-domain exact-match > 0.9"*) is not achievable from a whole-image recogniser.
4. **L131** puts `XProtect/reverse` in family B with the recipe "recogniser + per-type head/post-process". A
   post-process cannot recover a substring that was never isolated.

**Correct version.** Add a third axis to the taxonomy and make the *first* model a **crop-then-recognise**
pipeline for the scene types:

* The generators already know exactly where they drew the answer (`McUi.scene`, `Img.font`, the inventory
  widget code). Add an `roi: [x, y, w, h]` field to `labels.jsonl` for every scene type — that is ~20 lines
  in the generators and it converts 25 types from "ill-posed" to "supervised crop + recognise".
* Then: train the recogniser on the ROI crop (clean supervision, no chrome), and separately train (or
  hand-code, since the layout is per-plugin) the cropper. `bench/bench_hf.py` then scores the recogniser on
  crops and the pipeline scores end-to-end.
* Alternatively, and cheaper: a **type-conditioned** solver — the plugin identity is known at inference
  time (the plugin picks the captcha type!), so the cropper can be a per-plugin constant, not a learned
  detector. This is a strong argument the plan never makes: the solver always knows which plugin it is
  talking to, so the "scene" problem is solvable with a lookup table, not with a VLM.

> **Implemented (2026-10-21, later the same day).** The `roi` field exists in every `labels.jsonl`, and
> the cropper is the per-plugin constant this finding describes. 29 of the 46 types carry a band; the
> other 17 have `roi: null` because the whole frame is the text (or there is none). The training
> pipeline crops to the band before the recogniser sees the image, and the per-type charset, length
> and post-processing tables are derived from `labels.jsonl`.

---

### B5. `H = 32` normalises the *frame*, not the *glyph* — the answer shrinks to 2.8–8.5 px in most types

L529-L531: *"Height: 32 px, fixed. The smallest text bands in the dataset are 15–40 px tall inside 128×128 /
130×130 frames. H=32 preserves a 30-px glyph at 1:1 and upscales the small ones."*

This is backwards. The resize is `H_new = 32` **for every type**, so the scale factor is `32 / frame_height`
— which is < 1 for every type whose frame is taller than 32 px, i.e. **all of them**. The glyphs are
*downscaled*, and the smaller they are relative to their frame, the more they lose. Using the font sizes
read from the generator sources:

| type | frame | glyph px (from the generator) | scale 32/H | **glyph px after resize** |
|---|---|---|---|---|
| `LagBug/XProtect/reverse` (chat line) | 420×136 | 12 | 0.235 | **2.8** |
| `laforetbrut/are-you-sure/code` | 480×270 | ~24 | 0.119 | **2.9** |
| `n1zamu/NCaptcha/anvil` | 420×150 | 16 | 0.213 | **3.4** |
| `ru-symbols` | 250×150 | 17 | 0.213 | **3.6** |
| `ringoame196/map` | 128×128 | 16 | 0.250 | **4.0** |
| `XProtect/{code,map}` | 130×130 | 17 | 0.246 | **4.2** |
| `Mrbysco/Captcha/math` | 520×560 | 9 | 0.057 | **0.5** |
| `CaptchaVerifyZ/map` | 128×128 | 24 | 0.250 | 6.0 |
| `AnBot/captcha` | 128×128 | 20–40 | 0.250 | 5–10 |
| `haq/mapcha/map` | 128×128 | 30/40 | 0.250 | 7.5/10 |
| `ProstoCaptcha/map` | 128×128 | 32 | 0.250 | 8.0 |
| `JSH32/Minecaptcha/map` | 130×130 | 30 | 0.246 | 7.4 |
| `InstantlyMoist/textcaptcha` | 128×128 | 34 | 0.250 | 8.5 |
| `ru-web` | 150×90 | 30–44 | 0.356 | 10.7–15.7 |

> **One row is obsolete (2026-10-21, later the same day).** The `ru-symbols` row measured the
> **gallery's composite of the number-word map**, which is what `ru-symbols` was at the time of this
> review. The type has since changed: `ru-symbols` is now the gallery's composite of
> `LimboFilter/symbols`, the plugin's **symbol** mode, whose cap height is ~55 map px (≈ 64 px in the
> 250×150 composite). The ~17 px the row measured now belongs to `GalleryCaptcha/ru-numberword`, the
> composite of the number-word map. The other rows are unchanged.

A 2.8–4.2 px glyph is at the edge of legibility for a human and is *below* the resolution a CRNN needs to
separate `0/O`, `1/l`, `5/S`, `8/B` — the exact confusions the plan wants to beat (L680). And this is before
the compression stage (L442-L444, q 15–40 at p = 0.10) which the plan says "destroys thin strokes
almost entirely".

**Correct version.** Normalise on the **text band**, not the frame: crop to the answer ROI (see B4), then
resize so the *glyph height* is ~32 px. The frame height is the wrong denominator. Alternatively keep the
frame and make the input height per-type (`H_type = 32 · band_height / glyph_height`), which is a 5-line
change once the ROI exists.

> **Implemented (2026-10-21, later the same day).** The training pipeline crops to the `roi` and scales
> the **glyph** to 32 px, width by aspect, right-padded - which is the "correct version" above, not the
> 5-line alternative. The measured result is in `HANDOVER.md` §6.5: a held-out type
> (`InstantlyMoist/Captcha/textcaptcha`) scores **accuracy 1.000, CER 0.000** on clean data, while a
> held-out type whose band was still wrong scored 0.000.

---

### B6. The licence table files `irootdev/AnBot` as permissive; it is GPL-3.0

Plan L946 (the "MIT / CC0 → publish freely" row) includes `irootdev/AnBot`. The repo's own `README.md` L129
lists it as **GPL-3.0**, and I fetched the upstream file:

```
https://raw.githubusercontent.com/irootdev/AnBot/master/LICENSE
→ "GNU GENERAL PUBLIC LICENSE  Version 3, 29 June 2007"
```

I also verified the other two GPL claims and the three "no licence" claims from the upstream repos:

| upstream | upstream file | result | plan's claim | correct |
|---|---|---|---|---|
| `jonesdevelopment/sonar` | `main/LICENSE` | **GPL-3.0** ✓ | GPL-3.0 ✓ | ✓ |
| `China2B2T/Captcha` | `master/LICENSE` | **GPL-3.0** ✓ | GPL-3.0 ✓ | ✓ |
| `irootdev/AnBot` | `master/LICENSE` | **GPL-3.0** ✓ | *MIT/CC0* ✗ | **GPL-3.0** |
| `Archy-X/Krypton` | `master/LICENSE` 404, README has no licence mention | **none** ✓ | none ✓ | ✓ |
| `Yukun99/Captchas` | `main/master/LICENSE` 404, README no licence mention | **none** ✓ | none ✓ | ✓ |
| `ringoame196-s-mcPlugin/ReproductionCAPTCHA` | `main/LICENSE` 404 | **no licence file** ✓ | no licence file ✓ | ✓ |

So the plan's "no licence" claim is **right**, and its GPL-3.0 claim is **right for two of three plugins and
wrong for the third**. Consequence if not fixed: the AnBot renders (100 images) go into the permissive
dataset repo, and the published dataset then contains GPL-3.0-claimed material under an MIT card. That is
exactly the kind of error the split was supposed to prevent.

The plan's table also **omits three MIT plugins** — `Joey61021/captcha`, `Mrbysco/Captcha`, `n1zamu/NCaptcha`
— so the "permissive" repo would be incomplete.

> **Acted on (2026-10-21, later the same day).** The licence table in `reports/MODEL_PLAN.md` §5.5 has
> been corrected: `irootdev/AnBot` moved out of the MIT/CC0 row into the GPL-3.0 row, the three
> missing MIT plugins were added to the permissive row, and the three `dataset/out_ru/` plugins the
> table did not mention at all (`Supl1n/CaptchaGUI`, `Leymooo/BungeeCord`, `CaptchaVerifyZ`) were
> added with the licences recorded in `reports/SITE_CAPTCHAS.md` §7.1, §7.3 and §7.5. **B7** — whether
> GPL-3.0 reaches the rendered *images* at all, and whether the "one repo per licence family" split is
> needed — is **still open** and was not decided by that correction.

---

### B7. GPL-3.0 does not reach the rendered *output images* — the "one repo per licence family" split is not required

Plan L947: *"`jonesdevelopment/sonar`, `China2B2T/Captcha` | **GPL-3.0** | a derivative dataset must be
**GPL-3.0** → publish in a **separate repo with a GPL-3.0 card**."*

Two independent reasons this is the wrong call:

1. **GPL-3.0 says so itself.** §2 of the licence (verbatim from
   `https://raw.githubusercontent.com/jonesdevelopment/sonar/main/LICENSE`):
   > *"This License explicitly affirms your unlimited permission to run the unmodified Program. **The output
   > from running a covered work is covered by this License only if the output, given its content,
   > constitutes a covered work.** This License acknowledges your rights of fair use or other equivalent,
   > as provided by copyright law."*

   A rendered captcha PNG is not a copy of the plugin's source, does not incorporate any part of it, and its
   content (a random 6-character string) is not copyrightable. So the upstream GPL does not attach to the
   published images.
2. **The project did not use the upstream code anyway.** `README.md` L115/L124/L129 mark sonar, China2B2T
   and AnBot as **Clean-room** — "no code, comments, identifiers or copyright headers are carried over".
   A clean-room reimplementation is not a derivative work of the upstream. The images are the output of the
   *project's own* generator, which is the project's own work.

And the downside of the plan's call is concrete: declaring a dataset GPL-3.0 drags in GPL-3.0 §6
("convey the machine-readable Corresponding Source"), which for a dataset means shipping the generator
source under GPL — an obligation the project does not need, and which would sit badly next to the MIT
weights the plan wants to publish.

**Correct version.**
* One permissive dataset repo (or two: "our own renders" vs "reconstructed from the reference screenshots"), **MIT for
  the generator code and CC-BY-4.0 (or MIT) for the images**.
* Per-row `mode` (faithful / clean-room / reconstructed) and `upstream_licence` fields — the plan already
  proposes exactly these (L958-L960); that is the right mechanism and it does not need a repo split.
* State the *actual* residual obligations honestly: the **fonts** (see below), and the GalleryCaptcha type family being
  a reconstruction of a commercial site's output (a trademark/ToS question, not a licence question).
* If the owner still wants zero risk, keep the split — but then the plan must say *why* (risk appetite),
  not assert a legal requirement that GPL-3.0 §2 contradicts.

**A licence issue the plan missed entirely** (`README.md` L410): sonar's dot-matrix TTFs
(`dotness.ttf` = personal-use only, `DotMatrix.ttf` = no licence at all) **could not be redistributed**, so
the published sonar renders substitute Lucida Console / Courier New. The published sonar data is therefore
**an approximation, not a reproduction**, and the dataset card must say so. The plan's §5.5 table has no row
for this. (`Archy-X/Krypton` L408 is a similar case: 72 real material names with *invented* swatch colours.)

---

### B8. "Both API queries return empty" is false; the substantive claim survives

Plan L1211-L1212: *"no Minecraft-captcha model and no `CaptchaOCR` dataset exists on the Hugging Face Hub
(both API queries return empty)."*

Measured live on 2026-10-21:

| query | result |
|---|---|
| `api/models?search=captcha` | **100+ results** (the API returned a full page) — `anuashok/ocr-captcha-v3`, `Graf-J/*`, `confiacompany/*`, `ATH-MaaS/CaptchaMind-7B`, `CaptchaKraken/*`, `04RR/Florence-base-Captcha`, `hongyusir/*`, `DunnBC22/*`, `keras-io/ocr-for-captcha`, `wonder56/captcha-crnn-solver`, `langningchen/luogu-captcha-model`, `jacoblincool/ntnu-captcha-ocr-challenge-2024-baseline`, … |
| `api/models?search=minecraft` | **100+ results** — skins, voices, Minecraft LLM finetunes, `Minecraft*` org repos. **None** captcha-related. |
| `api/models?search=minecraft captcha` | **empty** ✓ |
| `api/models?search=spigot` | 21 results — all `Llama-3.2-1B-Lora-spigot-*` training runs + `jPlxg1n/spigot`. **None** captcha-related. |
| `api/datasets?search=captha` | **empty** ✓ |
| `api/datasets?search=captcha` | 100+ — `hammer888/captcha-data`, `ZHEN-04/CaptchaArena`, `inclusionAI/VenusBench-CAPTCHA`, … |
| `api/datasets?search=minecraft` | 50+ — none captcha-related |

So: the *substantive* claim (no Minecraft anti-bot-plugin captcha model on the Hub; no `CaptchaOCR` dataset)
**holds**, but the *stated evidence* ("both API queries return empty") is wrong, and the plan's own §7 offers
that as its closing word ("The niche this project occupies is unoccupied"). A reviewer of the model card will
paste `api/models?search=captcha` and get 100+ rows.

**Correct version:** "No model on the Hub targets Minecraft anti-bot-plugin captchas. `search=minecraft` and
`search=spigot` return 100+/21 results respectively, none of them captcha models; `search=minecraft captcha`
returns empty; `api/datasets?search=captha` returns empty. The closest existing work is
`Graf-J/captcha-*` (generic web captchas, hammer888 corpus), `confiacompany/confia-captcha-ocr-pt`
(fixed 5-char web captchas) and `CaptchaKraken/*` (commercial web puzzle captchas)."

---

### B9. The per-type answer-diversity numbers are wrong, and two of the quoted answer strings do not exist

Plan L110-L117 gives a table headed *"distinct answers / 100 samples"*:

| plan | measured (2026-10-21) |
|---|---|
| `XProtect/drop` → **4** (`dopr`) | **1** — the answer is the literal string `drop` in all 100 samples |
| `XProtect/jump` → **4** (`jmpu`) | **1** — `jump` |
| `XProtect/sneak` → **5** (`aekns`) | **1** — `sneak` |
| `XProtect/slot` → 8 | 8 ✓ |
| `XProtect/color` → 20 | **11** |
| `XProtect/code`, `/map`, `/reverse`, `Archy-X/Krypton/map`, `haq/mapcha/map` → *60–62 (full alphabet)* | **100** each (every sample unique) |

The plan's own headline "per-type answer diversity ranging from 4 to 62" (L108) is therefore **1 to 100**. The
strings `dopr`, `jmpu`, `aekns` **do not occur anywhere in the dataset** — I checked
`dataset/out/LagBug/XProtect/drop/labels.jsonl` line 1: `"answer":"drop"`. They appear to be invented.

Two consequences:

* The *direction* of the plan's argument survives (and is stronger than stated): with 1 distinct answer per
  100 samples, a random split leaks 100 % of the answer for these types (measured below), not "the same
  answer in both sides".
* The "60–62 (full alphabet)" row is a **charset size mistaken for an answer-diversity count**. `XProtect/map`
  has 100 distinct answers over 100 samples.

### B9b. The duplicate-image figures: one is right, one is wrong

Plan L119-L120 and L649-L650: *"8 duplicate images per 100 for `sneak`, 5–6 for `jump`, 2–5 for `drop`"*.
Measured (md5 of the PNG bytes, 100 samples per type):

| type | distinct images | excess duplicates | plan |
|---|---|---|---|
| `XProtect/sneak` | 92 | **8** | 8 ✓ |
| `XProtect/drop` | 95 | **5** | 2–5 ✓ |
| `XProtect/jump` | 98 | **2** | **5–6 ✗** |
| `XProtect/different` | 99 | 1 | — |
| `XProtect/slot` | 99 | 1 | — |
| `CaptchaGUI/clickblock` | **7** | **93** | — (not mentioned at all!) |

The repo's own `README.md` L466-L469 warns explicitly: *"Treat the **shape** as the specification — a
handful of duplicates confined to the chat-scene types — and not any particular integer."* The plan quotes a
stale expectation as a measured fact. `CaptchaGUI/clickblock` — 100 samples over **7** distinct images — is
the worst leak in the dataset and the plan does not mention it.

---

### B10. "20 of our 44 types have a fixed answer length" is 24 — and the slot-head covers at most 5

Plan L299: *"For fixed-length captchas, a per-slot classifier beats CTC … 20 of our 44 types have a fixed
answer length. Strong v2 candidate: a 'CapthaSlot' model for the fixed-length types."*

Measured: **24** types have a single distinct answer length, and they are spread over **nine** different
lengths:

| answer length | types | which (family-A ones in bold) |
|---|---|---|
| 1 | 2 | `XProtect/slot`, `CaptchaGUI/clickblock` |
| 3 | 1 | `AnBot/captcha` |
| 4 | 4 | `JSH32/Minecaptcha/map`, `XProtect/drop`, `XProtect/jump`, `haq/mapcha/map` |
| 5 | **8** | `Archy-X/Krypton/map`, `InstantlyMoist/textcaptcha`, `ringoame196/map`, `ru-web`, `CaptchaVerifyZ/map` (+`XProtect/sneak`, `ru-puzzle2x2`, `ru-puzzle3x3`) |
| 6 | 5 | `XProtect/code`, `XProtect/map`, `XProtect/reverse`, `ProstoCaptcha/map`, `laforetbrut/code` |
| 8 | 1 | `jSdCool/minecaptcha/text` |
| 9 | 1 | `China2B2T/wool` |
| 13 | 1 | `XProtect/different` |
| 18 | 1 | `ru-symbols` |

A slot-head model has a **fixed output length** — it cannot serve two lengths at once. The largest single
group is 8 types at length 5, of which only **5 are in family A**; the length-6 group has 5, of which 4 are
family A. So "a CapthaSlot model for the fixed-length types" is not one model — it is **nine models**
(5 for the OCR-relevant lengths 3/4/5/6, plus the Cyrillic length-18 one), and each would see 300–500 images.

This also inverts the plan's priority. `confiacompany/confia-captcha-ocr-pt` — the slot-head the plan cites
— is trained on **~800 samples of 5-character, 32-symbol web captchas** (`23456789abcdefghijklmnopqrstuvwxyz`
— no uppercase, no `0`, no `1`). Our length-5 family-A types use a 62-symbol mixed-case alphabet, at most
100 samples per type, across 6 different layouts (128×128 map, 128×128 web, 150×90 web, 250×150, …). A
slot-head's whole advantage is that the slot geometry is *known*; our slots are not at a fixed 30 px pitch
across types. **The CTC model is the better first model**, and the plan's own §0.1 conclusion ("the lever is
the data, not the architecture") points the same way. The slot-head is a reasonable *later* idea for one
well-chosen length (6, four family-A types) — not the v2 headline.

---

### B11. The vocabulary is 62, 96 or 34 — not 68/69/35

| plan | measured |
|---|---|
| L208 "Model A (Latin): 68 symbols (`,-0123456789A-Z[]_a-z`)" | that string has **67** characters (no space) |
| L156 "68 effective classes" / L568 "\|V\| = 69 (blank + 68)" / L744 / L829 `vocab_size: 69` | blank + 67 = **68**; and for the real Latin OCR family the answer charset is only `0-9A-Za-z` = **62** → \|V\| = **63** |
| L209 "Model B (Cyrillic): 35 symbols (blank + 33 Cyrillic + blank)" | blank + 33 = **34** (the plan double-counts blank) |
| L680 "Per-character confusion matrix \| 68×68" | 63×63 (Latin) / 96×96 (with Cyrillic) |

And note the characters `,` `-` `[` `]` `_` and space occur **only in types the plan excludes from Model A**:
`,` in `jSdCool/minecaptcha/image`; `-` in `AdvancedCaptcha/math`; `[`/`]` in `AdvancedCaptcha/button`;
`_` in `XProtect/different`, `China2B2T/wool`, `Archy-X/Krypton/menu`. Including them in Model A's charset
is harmless but pointless; excluding them while keeping "|V| = 69" is a contradiction.

---

### B12. `InterferenceCurves` at p = 0.50 is aimed at the wrong family, and XProtect has no curves at all

Plan L472-L483: *"A large fraction of these captchas have **thick black curves drawn over the text** — that
is what the `LagBug/XProtect` generators do, and it is the defining difficulty of the family. … So
`InterferenceCurves` at p=0.50 is the **highest-value augmentation in the list**."*

Measured (`build/review/interf2.py`, connected ink component with bbox diagonal ≥ 40 px, 20 samples/type):

| type | samples with ≥1 long stroke | median #strokes |
|---|---|---|
| **`LagBug/XProtect/map`** | **1 / 20** | **0** |
| **`LagBug/XProtect/code`** | **1 / 20** | **0** |
| `ru-numberword` | 20/20 | 2 |
| `ru-numberword-caption` | 19/20 | 2 |
| `laforetbrut/are-you-sure/code` | 20/20 | 6 |
| `jSdCool/minecaptcha/text` | 20/20 | 5 |
| `ru-symbols` | 0/20 | 0 |
| `AnBot/captcha`, `Archy-X/Krypton/map`, `ringoame196/map`, `CaptchaVerifyZ/map` | 0–1/20 | 0 |

`XProtect/map` draws **red glyphs on a black background with 51 short straight black segments**
(`XProtect.java` L82-L88: `g.drawLine(x, y, x + xl, y + l)` with `xl ∈ [0,13]`, `yl ∈ [0,15]`) — never a
curve, and only visible where a segment cuts a red glyph. Measured: the red glyphs form 6–8 connected
components for a 6-character answer, i.e. the interference cuts *one or two* glyphs per image. It is
**mild**, not "the defining difficulty of the family".

The thick black bezier curves are the **RussianCaptcha** family's signature (`RussianCaptcha.java` L505-L530:
70 % of samples get 3–6 black bezier strokes of 2.5–4.0 px sweeping the whole 250-px canvas; 30 % get 2–4
thin coloured straight lines) — that is **2 types / 200 images / 4.5 % of the dataset**.

So the transform is simultaneously **mis-attributed** (to XProtect instead of the Russian family),
**mis-shaped** (quadratic/bezier strokes, 1–3 px, alpha 0.55–1.0, "the way the generators do" — but the
generators use 2.5–4.0 px *opaque* black) and **mis-scoped** (p = 0.50 across all 44 types means 50 % of
~40 types that have *no* interference at all get an occlusion that never occurs in deployment — which
contradicts the plan's own thesis at L50-L56, "the augmentation's job is the axis the generator *cannot*
produce").

**Correct version.** Make occlusion **per-type**, and match the generator:
* `ru-numberword(-caption)`: 3–6 opaque black bezier sweeps, 2.5–4.0 px, p ≈ 0.70 (and 2–4 thin coloured
  lines, p ≈ 0.30) — this is where `InterferenceCurves` earns its place.
* `XProtect/{code,map}`: 40–60 short straight segments, 1 px, black-on-black (only the cut matters), p = 1.0
  — that is a **different transform**, and it is cheap to write.
* `laforetbrut/are-you-sure/code` and `jSdCool/minecaptcha/text`: a 1-px translucent strike bar (p = 1.0).
* the other ~35 types: **p = 0** (they have no occlusion; the plan's `CoarseDropout`/`Erasing` at p = 0.15 /
  0.10 should be reduced to 0 for them too).

---

### B13. The puzzle family is misclassified: the label is not recoverable from the pixels

Plan L131 puts `ru-puzzle2x2` and `ru-puzzle3x3` in family B — *"Text in the image, but the answer is a
transformation … tiles permuted **and rotated by multiples of 90°** … recogniser + per-type head/post-process
(a 'type-aware' solver)"* — while L330-L332 (in §2.2) correctly says they *"need spatial reasoning (which
tile is where) plus a rotation-aware recogniser"*. The plan contradicts itself, and **§0.3.1 is the wrong one**.

`WebCaptcha.java` L236-L300: the base captcha is rendered, cut into a 3×3 / 2×2 grid, and the tiles are
**permuted** (`perm`) and **each independently rotated by a random multiple of 90°** before being blitted
into its output cell. The answer is the string in the *original* tile order. So the pixels contain the glyphs
of the answer, but **shuffled and rotated**; a recogniser reading the image left-to-right sees the tiles in
the permuted order, and no post-process can undo a permutation it cannot observe.

I looked at the samples (`build/review/sheet_puz3x3.png`): `ru-puzzle3x3/001.png` (answer `1EOCD`) shows
`Ω` upside down at the left and a rotated `D` — the string is not present in reading order.

Furthermore the *rotation is not recoverable* either: the original tile rotation is 0, but a glyph like `N`
rotated 180° is still a valid `N`, so the per-tile rotation offset is ambiguous from the glyph alone; and
for the ~50 % of base renders whose background is a flat colour or a gradient (`WebCaptcha.render`, L318-L375:
`kind = r.nextInt(6)` → flat white / flat colour / gradient / hatch / dots / grid) the **tile order is not
recoverable at all** from background continuity.

**Correct version.** `ru-puzzle2x2` / `ru-puzzle3x3` are **family C (jigsaw / spatial reasoning)** — the same
verdict §2.2 reaches. They must be **excluded from the recogniser's training set** (200 images = 4.5 % of
the data would otherwise be irreducible label noise that the CTC loss can never fit, and would depress the
CTC loss curve the plan uses for checkpoint selection at L730-L732). If the project wants them, they need a
jigsaw solver (edge-matching / background-continuity) plus a per-tile rotation classifier — a second paper.

The plan's §0.3.1 also fails to mention that `ru-puzzle*` are the reason the "5 fixed-length types" include
two jigsaw types, and that `ru-symbols` (length 18) is the *only* other fixed-length Cyrillic type.

> **Obsolete in its premise, still right in its verdict (2026-10-21, later the same day).** The
> `ru-puzzle2x2` / `ru-puzzle3x3` types no longer exist: `PuzzleCaptcha.java` and the whole "picture
> cut into a grid and permuted" model behind them were wrong, and the puzzle family is now
> LimboFilter's own `FRAMED_CAPTCHA` - `LimboFilter/framed3x3` (384×384) and `LimboFilter/framed2x2`
> (256×256). The **verdict survives unchanged**: the framed types are family C, the answer lies in
> frames that have to be turned, and they are excluded from the recogniser's training set (200
> images — now generated from the plugin's own algorithm, not from a permuted picture). The
> "permuted" description in the finding above describes the old, wrong generator: the upstream splits
> the canvas in order and only **turns** the frames, it has no permutation step at all
> (`reports/PUZZLE_OBJECT_FAMILIES.md` §2.3). The `ru-symbols` "length 18" of the last paragraph is
> out of date as well: the symbol family is now three characters.

---

### B14. The `anvil` "superscript → plain" transformation is unnecessary — the image already contains the answer

Plan L131 and L222-L226 classify `n1zamu/NCaptcha/anvil` as family B ("Unicode superscript digits → plain
decimal") and say to put the transformation in the solver.

I zoomed the image (`build/review/sheet_anvil_zoom.png`, `dataset/out/n1zamu/NCaptcha/anvil/001.png`,
answer `27451`):

* the **title strip** shows the superscript form `²⁷⁴⁵₁`;
* the **input box** shows `27451` in Segoe UI 16 — at that size the Unicode superscript glyphs are visually
  indistinguishable from plain digits;
* the **footer** shows the **plain decimal** `27451` in the same size as the surrounding text
  (`NCaptcha.java` L85: `"&7Ответ (обычные цифры): &f" + number`).

So the answer is legible **in plain digits, twice**, without any transformation. The superscript→plain step
is a no-op on a recogniser's output (it contains no superscripts) and, worse, it is applied to a *whole-frame*
read that contains the number twice, so a solver post-process has nothing to act on.

This is a **faithful reproduction of an upstream defect** (the plugin prints its own answer) and it should be
documented as such — the repo's `README.md` "Faithful reproduction of upstream defects" table does not
currently list it. It is also a *scene* type (B4): the number is one string among the anvil chrome, so a
whole-image CTC has no well-defined target here.

**Correct version.** `anvil` is a scene type with a **leaked answer**; it does not need a transform, and it
should be excluded from, or ROI-cropped before, recogniser training.

---

### B15. `ru-numberword` is a Cyrillic OCR task, not "not OCR at all"

Plan L132 puts `ru-numberword` and `ru-numberword-caption` in family C — *"Not OCR at all … the image shows
a Russian number spelled out in words; the answer is the digits … **no** | classification / grounding /
arithmetic / VLM"* — and L138-L140 repeats *"a single image→string model cannot solve `ru-numberword`"*.

The first half is right (I verified the images: `build/review/sheet_numberword.png` shows
"пятьсот тридцать", "девяносто восемь", "четыреста тридцать"), but the conclusion is wrong, and it is wrong
in the same way the plan itself already gets right for `reverse` and `anvil`:

> **Plan L222-L226:** *"The recogniser stays a pure `image → string` function; the solver is
> `image → string → answer` with a per-type post-process."*

`ru-numberword` is exactly that: the recogniser reads the Cyrillic words (a 33-class OCR problem — the
Cyrillic Model B the plan already wants to build!), and the solver converts the word string to digits with a
**finite Russian numeral lexicon** (the generator's own `ONES`/`TENS`/`HUNDREDS` tables,
`RussianCaptcha.java` L68-L86 — 20 + 8 + 9 entries). That is a ~40-line lookup, not a VLM.

The cost of the plan's classification is concrete:

* It removes **200 usable Cyrillic images** from a Cyrillic model that the plan says will be trained on
  `ru-symbols` **only (100 images)** (L210-L211). Relabelling `ru-numberword(-caption)` to the *spelled-out
  words* triples the Cyrillic training set to 300 and makes the family-A training set contain a second
  multi-word layout (3 lines of words, one per line) — a genuinely useful augmentation of the layout
  distribution.
* It pushes the project to "the natural entry point is `ru-numberword` … where it has a 100-image fine-tune
  and no other competitor" (L368-L369, L1165) — a VLM fine-tune on 100 images, when a 40-line lexicon
  solves it exactly.

**Correct version.** `ru-numberword(-caption)` is **family B** (OCR + per-type transform). Relabel to the
word string (e.g. `четыреста семьдесят один` → `четырестасемьдесятодин`, spaces stripped, so the CTC target
is the glyph run), train it in Model B, and put `word→digits` in the solver.

> **Implemented (2026-10-21, later the same day).** This is exactly what the dataset now does, through
> the `text` / `answer` split in `labels.jsonl`: `text` is the number spelled out in Russian words
> («шестьсот девяносто»), `answer` is the digits (`690`). A recogniser trained on `text` and a
> 40-line lexicon in the solver is the whole solution. The Cyrillic model is still a separate head
> (`--charset cyrillic`, 33 letters + blank).

---

### B16. The `Graf-J` 97.38 % belongs to the *base* model, not the finetuned one

Plan L24 (executive summary) and L1187-L1189: *"`Graf-J/captcha-conv-transformer-finetuned` (MIT, 12.3 M
params) scores **97.4 % / 88.4 %** on real captcha distributions"*.

The model card's own table says:

| | CRNN (Base) | CRNN (Finetuned) | Conv-Transformer (Base) | **Conv-Transformer (Finetuned)** |
|---|---|---|---|---|
| # Parameters | 3 570 943 | 3 570 943 | 12 279 551 | 12 279 551 |
| Sequence Acc. (hammer888/captcha-data) | 96.81 % | 92.98 % | **97.38 %** | **95.36 %** |
| Sequence Acc. (Python Captcha Library) | 9.65 % | 86.20 % | 11.59 % | **88.42 %** |

So 97.38 % is the **base** Conv-Transformer's score on hammer888; the **finetuned** model — the one the plan
recommends reusing — scores **95.36 %** on hammer888 and **88.42 %** on the unseen distribution. The plan
quotes the base model's number for the finetuned model. (12 279 551 params = "12.3 M" ✓, MIT ✓.)

Also note L284-L286: *"a 'Convolutional Transformer' that beat a CRNN by 0.6 points on the training
distribution and 2.2 points on the unseen one"* mixes the two pairs: base-vs-base is +0.57 on hammer888 but
+1.94 on the unseen set; finetuned-vs-finetuned is +2.38 and +2.22. The sentence should say which pair it means.

**Correct version.** `Graf-J/captcha-conv-transformer-finetuned`: 12.28 M params, MIT, **95.36 %** on
hammer888/captcha-data (CER 1.03 %), **88.42 %** on the unseen Python-Captcha-Library distribution
(CER 2.08 %), 733 img/s on an RTX A6000. `Graf-J/captcha-crnn-base`: 3.57 M, 96.81 % / 9.65 %.

---

### B17. The `Graf-J` load failure is misdiagnosed, and the plan's M0 remedy is the wrong one

Plan L1073-L1077: *"**Why the `Graf-J` models fail to load:** their `configuration_captcha.py` /
`processing_captcha.py` pre-date v5's config and processor handling, and v5's `auto_map` resolution plus the
new `SubConfigSpec` config machinery rejects the old-style custom config. … **Fix:** re-save the config and
processor with a v5 `transformers`"*, and M0 (L1157) accordingly: *"add `Graf-J/captcha-crnn-base` with a
v5-compatible processor re-save"*.

The repos are **already v5-shaped**:

```json
// https://huggingface.co/Graf-J/captcha-crnn-base/raw/main/config.json
{ "model_type": "captcha_crnn", "transformers_version": "5.1.0",
  "auto_map": { "AutoConfig": "configuration_captcha.CaptchaConfig",
                "AutoModel":  "modeling_captcha.CaptchaCRNN",
                "AutoProcessor": "processing_captcha.CaptchaProcessor" },
  "custom_pipelines": { "captcha-recognition": { "impl": "pipeline.CaptchaPipeline", "pt": ["AutoModel"], ... } } }
```

That is *exactly* the layout the plan recommends in §5.2. The actual failure, from
`reports/bench_results_others.json`, is:

```
ValueError: Unrecognized configuration class <...CaptchaConfig> for this kind of AutoModel:
AutoModelForImageTextToText. Model type should be one of AriaConfig, ...
```

i.e. `captcha_crnn` is not in v5's **auto-mapping registry** for that auto class — and
`bench/bench_others.py` L59-L61 only ever tries `AutoModelForImageTextToText`, with **no `AutoModel`
fallback**. The Graf-J model card's own "Advanced Usage" snippet uses `AutoModel` + `AutoProcessor`.

**Fix:** one line in the harness — try `AutoModel.from_pretrained(model_id, trust_remote_code=True)` (and/or
`pipeline("captcha-recognition", ...)` via the `custom_pipelines` entry the repo already ships) **before**
`AutoModelForImageTextToText`. No re-save, no processor surgery, no config change. This is ~10 minutes of
work, not the "re-save the config and processor" project the plan describes, and it unblocks M0.

---

### B18. The "in-domain" 13-type number is a *training-set* number presented as directly comparable

Plan L633-L637 proposes the existing `bench/bench_hf.py` set (13 types × 8 = 104) as the "secondary
(comparison) number", correctly noting *"These types are in training, so this number is optimistic by
construction — say so on the card, and label it 'in-domain'."* But L660-L662 then says:

> *"It is a harder, fairer test than the published baselines got. Those baselines were evaluated on the same
> 13 types; our in-domain number on the same 13 types is **directly comparable**, and our unseen-style number
> is a **stricter** claim."*

It is not directly comparable: the baselines (EasyOCR 0.115 / CER 1.835, `anuashok/ocr-captcha-v3`
0.077 / 0.785 — both verified in `reports/bench_results*.json`, n = 104) were scored on a **test** set; our
model would be scored on its **training** set. The plan is right that the unseen-style number is the
stricter claim; it is wrong that the two are "directly comparable". If the in-domain number goes on the card
next to the baselines, a reader will assume parity of conditions.

Two further facts about that test set the plan does not mention:

* `bench_hf.py` L38 takes `rows[:N_PER_TYPE]` — the **first 8** samples of each type, a deterministic prefix,
  not a random sample. For `n1zamu/NCaptcha/anvil` the length histogram is `4:12, 5:88`, so the first 8 are
  **all 4-digit** — the test set is not representative of that type.
* One of the 13 types (`n1zamu/NCaptcha/anvil`) is a **transform/scene** type (B4, B14) and 8 of the 13 are
  **scene** types (B4). So the "13 text types" benchmark is mostly a scene benchmark.

**Correct version.** Keep the 104-image set as a *regression* check on the harness, but publish a **held-out
sample split**: for the 13 types, reserve 20 samples per type that are excluded from training, and report
both "in-domain (held-out samples)" and "unseen type". Then the comparison to the published baselines is
like-for-like.

---

## 2. Bad advice (choices that would hurt, with the reason)

**A1. `H = 32` fixed for all types (L529-L531, L741).** See B5. The frame height is the wrong denominator;
normalise on the text band / glyph height. A 2.8–4.2 px glyph is below the resolution needed to separate
`0/O`, `1/l`, `5/S`, `8/B` — the confusions the plan's own confusion matrix (L680) is meant to expose.

**A2. One global augmentation policy (L406-L448).** The 44 types have frame sizes from 114×174 to 730×84 and
completely different content (a 5-character code on white vs a 420-px Minecraft chat log). Applying
`A.Affine(rotate ±8°, shear ±5°)` to a chat scene rotates the *chrome*, and applying `A.Downscale(0.5–1.0)`
to a 128×128 map with 4.2-px glyphs destroys them. Augmentation strength should be **per type**, keyed off the
same ROI/geometry metadata the plan would need for B4/B5 anyway.

**A3. `A.RandomScale` as the `RandomResizedCrop` replacement (L494).** The ban itself is right (see §3), but
albumentations 2.x `RandomScale(scale_limit=…)` *"randomly scales the input image by a factor … the image is
then padded or cropped to the original size"* — with a scale limit above 1.0 it **crops the border**, which is
precisely the "cuts a glyph in half" failure the plan is trying to avoid. The correct replacement is
`A.Affine(scale=…)` (which the plan already has at stage 1) or `A.Resize` to a fixed width — or, for the
map-style types, a *padded* scale that never crops.

**A4. `InterferenceCurves` p = 0.50 globally (L423, L472-L483).** See B12. It should be per type, and for
~35 of the 44 types it should be 0.

**A5. The per-character confidence formula (L607-L616).** Two problems:

* *"The character's confidence = the geometric mean of the posteriors of those frames at the chosen class"*
  uses the **emission posterior** `p[t,c] = softmax(logits_t)[c]`, not the **path posterior**
  `P(γ | x) = Σ_{π consistent with γ} P(π | x)` that CTC actually defines. The emission posterior ignores
  the blank-vs-character competition and the other alignments entirely: a frame with `p[c]=0.6` and
  `p[blank]=0.39` may be forced into a character by the alignment, and the *path* probability of the decoded
  string can be near 1 while the emission posteriors look mediocre. The correct per-character posterior is
  obtained from the CTC forward-backward (α/β) marginals; the emission geometric mean is a heuristic
  **ranking score**, not a posterior. The plan presents it as "how to compute it honestly".
* *"The sequence confidence = the geometric mean of the per-character confidences. Equivalently, with prefix
  beam search, `exp(sum log P(path))`."* These are **not** equivalent — a geometric mean of per-character
  emission scores is not a path probability, and the plan's own "equivalently" is false. (For the same reason,
  *"Fit a single temperature T on the validation set by minimising NLL"* is ill-posed on this quantity: it is
  not a log-probability of the string, so there is no NLL to minimise over it. Temperature-scaling the
  **logits** and then computing the CTC path posterior is well-posed; Platt-scaling the final confidence
  score is also well-posed. The plan conflates the two.)
* The plan should also drop the "geometric, not arithmetic: CTC posteriors are multiplicative along a path"
  justification for the *character* score: the multiplicative-along-a-path argument is about the **sequence**
  probability, not about aggregating the frames of one character.

**A6. "No label smoothing on CTC" — the conclusion is right, the reason is wrong (L585-L591).** The plan
says *"The published label-smoothing literature is about cross-entropy and attention seq2seq, not CTC."* That
is not true: there is a real CTC-regularisation literature, it just does not use the label-smoothing name.
The clearest example is **EnCTC / AdaMER-CTC** — *"Connectionist Temporal Classification with Maximum Entropy
Regularization"*, NeurIPS 2023, [arXiv:2403.11578](https://arxiv.org/abs/2403.11578) — whose abstract
states the symptom directly: *"In Automatic Speech Recognition (ASR) systems, a recurring obstacle is the
generation of narrowly focused output distributions. This phenomenon emerges as a side effect of Connectionist
Temporal Classification (CTC)"* — i.e. **CTC is over-confident**, and the fix is entropy-based
regularisation of the CTC posterior, not label smoothing. That is the *same* symptom the plan itself names at
L614 (*"CTC posteriors are notoriously overconfident"*).

And the reference implementation the plan itself points at (PP-OCRv6 = PaddleOCR) confirms the practical
conclusion: `ppocr/losses/rec_ctc_loss.py` has **no label-smoothing option**; it offers `use_focal_loss`
instead (reweighting by `(1 − exp(−loss))²`).

**Correct version:** *"Label smoothing has no established role in CTC and we will not use it. The published
CTC regularisers are entropy-based (EnCTC / AdaMER-CTC, NeurIPS 2023) or focal reweighting (PaddleOCR's
`use_focal_loss`); if the CTC posteriors prove over-confident on our validation set, EnCTC is the principled
fix and it is worth an ablation — but it is a v2 item, not a v1 one."* And the plan should then stop
reaching for a temperature on a non-probability (A5).

**A7. "Slot-head for the fixed-length types" as a single v2 model (L299, L1163).** See B10. It is nine models,
not one, and the slot geometry is not shared across our layouts. Keep it as an idea for a *single* length
(6) with a *single* well-populated family, after the CTC baseline exists.

**A8. The augmentation ramp (L509-L521) and the epoch/wall-clock budget (L737-L775).** Two problems.
(i) The ramp starts at epoch 0 with *no* augmentation for 5 epochs and ramps to full by epoch 15 — but the
plan's own checkpoint-selection rule (L730-L732) selects on the **unseen-type exact-match**, which is
measured on the *clean* validation images. Training without augmentation and then suddenly applying
`Affine + Elastic + Interference + compression` at epoch 5-15 is a **distribution shift the model has never
seen**; the ramp helps but a cosine schedule on a *ramped* probability is not the same as a schedule on a
fixed one. More importantly, "fixed vs ramped" is the wrong A/B: with 4 400 images the more valuable ablation
is **"which types are in the training set"** (B4/B15) and **"per-type augmentation policy"** (A2/A4).
(ii) The wall-clock table is built on the 2.02 M model (B1); with the specified 5.28 M model, "2–3 h for the
4-fold experiment" becomes 4–6 h and "23 s/epoch" becomes 34 s (W=128) to 74 s (W=320) before augmentation
cost.

**A9. "Start from the `Graf-J/captcha-crnn-base` weights" (L699-L703).** The advice is licensed and legal
(MIT, attribution required) and the plan's *reasoning* — that a captcha-corpus pretrain beats ImageNet — is
supported by the card. But Graf-J's base CRNN scores **9.65 %** on an unseen captcha distribution (their own
number) and its alphabet is 63 symbols (`num_chars: 63`) that does not match ours; the plan proposes it
*and* a from-scratch model in the same breath (L15 "trained from scratch" vs L699 "start from the
Graf-J weights"). Pick one. My recommendation: **from scratch, on our data, with the public corpus as the
stage-1 pretraining set if the unseen-style number is below 0.7** (which is what M6(a) already says) — do
not start from a checkpoint whose headline number is 9.65 % on anything resembling an unseen style.

**A10. `A.ToGray` / `A.InvertImg` at a single global p (L431-L432, L505-L507).** The plan's reasoning for
`InvertImg` is good and correct (the dataset genuinely has both polarities). But the *rate* is a global
constant over 44 types whose colour statistics differ wildly: `ru-object-swatch` is 5 saturated colour
fields (inverting it destroys the task), `XProtect/code` is red-on-black, `ru-symbols` is black-on-white.
Colour-sensitive augmentation must be per type. (For the same reason, `A.ToGray` at p = 0.15 is fine only
for the text types; it is meaningless for the swatch type.)

---

## 3. Verified claims (the ones I confirmed, with the numbers I measured)

These are the parts of the plan that hold up. They are a lot of the plan, and they are the reason the
document is worth acting on.

**Dataset facts (all re-measured from `dataset/out/` + `dataset/out_ru/`, `build/review/measure_dataset.py`):**

| plan | claim | measured | verdict |
|---|---|---|---|
| L100 | 4 400 images, 44 types, 100 per type | 44 types, 4 400 `labels.jsonl` rows, 4 400 PNGs | ✅ |
| L101-L103 | union charset **101 symbols**, exactly `,-0123456789A-Z[]_a-z` + 33 Cyrillic | **101**, and the string matches **byte for byte** (including the leading space) | ✅ |
| L106 | 2 880 distinct answers over 4 400 samples | **2 880** | ✅ |
| L105 | length histogram 5→1068, 4→765, 6→648, 3→590, 1→271, 2→172, long tail to 70 | **identical** | ✅ |
| L199-L201 | only 2 of 44 types contain Cyrillic — `ru-symbols` and `ru-object-swatch` | **exactly those two** | ✅ |
| L202-L203 | `ru-numberword(-caption)` answer = digits, length 2–3 | digits; `2:9, 3:91` and `2:6, 3:94` | ✅ |
| L469 | `XProtect/reverse` = read-then-reverse | `XProtect.java` L227-L233: image shows `code`, `answer()` returns the reversed string | ✅ |
| L131 | `anvil` = superscript→plain | `NCaptcha.java` L32-L44, L53: superscripts in the title, plain decimal answer | ✅ (but see B14) |
| L132 | `ru-object-swatch` = colour name, not OCR; no text in the image | `ObjectCaptcha.java` L48-L55: *"This is **not** an OCR task: there is no text in the image"*; 5 swatch names, 5 distinct answers | ✅ |
| L130 | the 13 benchmark types are family A | the 13 `TEXT_TYPES` in `bench/bench_hf.py` L9-L23 | ✅ (but see B4) |
| L322 | family C = 24 of 44 | the plan's own table lists **21** | ❌ (21) |
| L134 | ~20 of 44 are family A | 20 by the plan's own table (13 bench + 7) | ✅ |
| L132 | `jSdCool/minecaptcha/image` label is not recoverable from pixels | `README.md` L411: *"The answer cannot be recovered from the image — the mapping is unknowable by construction"* | ✅ |

**Leakage (the plan's central validation argument) — confirmed and quantified.**
`build/review/leak_interf.py` simulates 200 random 50/50 image splits per type:

| type | distinct answers | answer leaks into the other half | identical image in the other half |
|---|---|---|---|
| `China2B2T/wool` | 1 | **100 %** | 0 % |
| `Joey61021/colorgui` | 6 | **100 %** | 0 % |
| `XProtect/different` | 1 | **100 %** | 0.9 % |
| `XProtect/drop` | 1 | **100 %** | 5.6 % |
| `XProtect/jump` | 1 | **100 %** | 2.0 % |
| `XProtect/sneak` | 1 | **100 %** | 8.4 % |
| `XProtect/slot` | 8 | 99.9 % | 1.1 % |
| `ru-object-swatch` | 5 | **100 %** | 0 % |
| `CaptchaGUI/clickblock` | 7 | **100 %** | **100 %** |
| `XProtect/color` | 11 | 98.1 % | 0 % |
| `Z4OLLIEZ4/captchasx` | 13 | 97.9 % | 0 % |
| `XProtect/equation` | 25 | 86.7 % | 0 % |
| `XProtect/gui` | 36 | 72.1 % | 0 % |
| the 100-distinct-answer types (code, map, reverse, Krypton/map, …) | 100 | **0 %** | 0 % |
| **weighted over all 4 400** | | **34.3 %** | **2.7 %** |

The plan's conclusion — *"a random image split measures memorisation here, and measurably so … A random
split's number cannot be defended when someone points out that `sneak` leaked"* (L648-L659) — is **right, and
the true number is worse than the plan says**: under a random split, **one third of all test samples have
their exact gold answer string present in the training half**, and `CaptchaGUI/clickblock` has 100 %
*pixel-identical* leakage (100 samples over 7 distinct images). The type-held-out protocol (L625-L669) is
the right call.

**Hub / arXiv / PyPI claims (all re-queried live on 2026-10-21):**

| plan | claim | verified |
|---|---|---|
| L23, L1177 | `PP-OCRv6_medium_rec`, arXiv **2606.13108** | ✅ <https://arxiv.org/abs/2606.13108> → *"PP-OCRv6: From 1.5M to 34.5M Parameters, Surpassing Billion-Scale VLMs on OCR Tasks"* |
| L230, L248 | 19 M params, Apache-2.0, ONNX repo | ✅ card: *"contains 19M parameters"*, `license: apache-2.0`; `PP-OCRv6_medium_rec_onnx` = 55 342 downloads, exactly as quoted |
| L231-L232 | 83.2 % W-Avg; "Confusable" 64.9 % | ✅ both exact in the card's table |
| L233 | beats PP-OCRv5_server (78.1) by +5.1, v5_mobile (73.7) by +9.5 | ✅ 83.2 − 78.1 = 5.1; 83.2 − 73.7 = 9.5 |
| L37-L38, L308-L311 | beats Qwen3-VL-235B 74.9, Gemini-3.1-Pro 71.4, Kimi-K2.6 62.9, GPT-5.5 64.2, MiniMax-M3 54.1; Confusable 64.9 vs 56.1 | ✅ every number matches the card's table exactly |
| L234-L236 | LCNetV4 + `EncoderWithLightSVTR` + CTC+NRTR multi-head | ✅ verbatim from the card |
| L620 | PP-OCRv6 example `rec_score` 0.9857 | ✅ the card's own JSON output |
| L24, L1187 | `Graf-J/captcha-conv-transformer-finetuned`, MIT, 12.3 M | ✅ MIT, 12 279 551 params — but the 97.38 % is the **base** model's (B16) |
| L160, L1189 | `confiacompany/confia-captcha-ocr-pt`, MIT, 1.2 M, positional slot head | ✅ *"~1.2 milhões de parâmetros"*, *"Positional Slot-Head CNN"*, 3 conv blocks, 6×20 grid, 5 slots of ~30 px, 150×50, < 5 ms CPU — all exact |
| L42-L43, L1190 | `anuashok/ocr-captcha-v3`, 61 323 downloads, 43 likes, CER 0.0139 | ✅ 61 323 downloads, 43 likes, *"CER: 0.01394585726004922"* |
| L340-L347 | `CaptchaKraken/CaptchaKraken-v1.2-GGUF`, 2 996 downloads, Qwen3.5-9B LoRA, 44 puzzle types / 10 vendors, graded 0.6155 on 1 458 held-out, source-available no-resell | ✅ **every** number: 2 996 downloads, `base_model: Qwen/Qwen3.5-9B`, *"44 puzzle types across 10 vendors"*, *"full 1458-sample held-out real eval"*, total **0.6155**, reCAPTCHA 0.600, GeeTest 0.780, BotDetect 0.929, Yandex 0.364, *"the GGUF builds land about 5 points below the same weights served with vLLM"*, and the *"answer goes to `reasoning` and `content` comes back empty, on every puzzle"* + *"flat 720² pixel budget"* warnings |
| L361-L363 | `ATH-MaaS/CaptchaMind-7B` Apache-2.0 + `ATH-MaaS/Captcha` CC BY-NC 4.0 | ✅ model exists, Apache-2.0, 103 downloads |
| L1035-L1036 | transformers v5.0.0 shipped 2026-01-26; v5.20.2 on 2026-10-19 | ✅ PyPI: 5.0.0 uploaded 2026-01-26, 5.20.2 uploaded 2026-10-19, **5.20.2 is the current latest** |
| L1089-L1092 | pin `transformers==5.20.2` | ✅ correct advice, and the installed version here is 5.19.0 (L69 ✓) |
| L909-L912 | `optimum-onnx` 0.1.0 declares `transformers<4.58.0,>=4.36`; `optimum` 2.3.0 declares `transformers>=4.29` | ✅ PyPI metadata, exact |
| L393-L395, L1196-L1199 | `albumentations==2.0.8` deps satisfiable; `onnxscript` 0.7.2, `datasets` 5.1.0, `evaluate` 0.4.6 | ✅ PyPI: albumentations 2.0.8 requires numpy>=1.24.4, scipy>=1.10.0, pydantic>=2.9.2, albucore==0.0.24, opencv-python-headless>=4.9.0.80 (all satisfied: pydantic 2.13.4, opencv 5.0.0.93); onnxscript 0.7.2, datasets 5.1.0, evaluate 0.4.6 are the current releases |
| L60-L84 | environment table | ✅ **every** value: Python 3.14.5, torch 2.14.1+cpu (`cuda False`, 0 devices, 18 threads), torchvision 0.29.1, transformers 5.19.0, hub 1.33.0, tokenizers 0.23.2, safetensors 0.8.0, accelerate 1.15.0, numpy 2.4.6, scipy 1.18.1, scikit-image 0.26.0, shapely 2.1.2, pillow 12.2.0, opencv 5.0.0.93, onnxruntime 1.30.0, easyocr 1.7.2, diffusers 0.41.0, pydantic 2.13.4; and the "absent" list (datasets, albumentations, evaluate, optimum, peft, timm, tensorboard) is **exactly** right |
| L313, L635 | EasyOCR 0.115 / CER 1.835; 388 ms/image | ✅ `bench_results_others.json`: accuracy 0.1154, mean_cer 1.8353, 40.3 s / 104 = **387.5 ms** |
| L254-L255, L635 | `anuashok/ocr-captcha-v3` 0.077 / 0.785 | ✅ `bench_results.json`: acc 0.0769, cer 0.7853, n = 104 |
| L1079-L1086 | `keras-io/ocr-for-captcha` fails (no `from_pretrained_keras`); `04RR/Florence-base-Captcha` fails on `forced_bos_token_id` | ✅ both error strings in `reports/bench_results_others.json` are exactly as described |

**transformers 5.x claims (checked against the locally installed 5.19.0, `build/review/check_transformers.py`):**

| plan | claim | measured |
|---|---|---|
| L74, L905 | `import transformers.onnx` → ModuleNotFoundError | ✅ `ModuleNotFoundError: No module named 'transformers.onnx'` |
| L1040 | `AutoModelForVision2Seq` removed | ✅ not in `dir(transformers)`; `AutoModelForImageTextToText` present |
| L1041-L1044 | `image-to-text` and `vqa` pipelines removed; `image-text-to-text` survives | ✅ registry contains `image-text-to-text`, no `image-to-text`, no `vqa`, no `text2text` |
| L1066-L1067 | `Trainer`: `tokenizer`→`processing_class`, `no_cuda`→`use_cpu`, `per_gpu_train_batch_size`→`per_device_train_batch_size`, `use_legacy_prediction_loop` removed | ✅ all four confirmed (`Trainer.__init__` has `processing_class`; `TrainingArguments` has `use_cpu`, `per_device_train_batch_size`, and neither `no_cuda`, `tokenizer`, `use_legacy_prediction_loop`) |
| L1066 | **`warmup_ratio` → `warmup_step`** | ❌ **`warmup_ratio` is gone, `warmup_steps` (plural) is the field; there is no `warmup_step`**. The correct statement is "`warmup_ratio` was removed; use `warmup_steps` (an integer) or a `lr_scheduler` with `num_training_steps`". |
| L1048-L1049 | `special_tokens_map.json` / `added_tokens.json` no longer written | ✅ a saved tokenizer writes only `chat_template.jinja`, `tokenizer.json`, `tokenizer_config.json` |
| L1061-L1062 | `batch_decode` → `decode`; `as_target_tokenizer` removed | ⚠️ `as_target_tokenizer` **is** removed ✅, but `PreTrainedTokenizerBase.batch_decode` **still exists** in 5.19.0. The plan should say "the *tokenizer* `batch_decode` is deprecated in favour of `decode`; `ProcessorMixin.batch_decode` is unaffected" — as it does at L1061/L1103, but L1062 states it as a removal. |
| L1060 | `safe_serialization=False` removed | ⚠️ not checked (needs a v5 source read); not contradicted by anything I measured |

---

## 4. What the plan missed

**M1. The scene/clean-text axis (see B4) — the most important omission.**
The taxonomy A/B/C answers *"what is the answer?"*, not *"what is the image?"*. 25 of 44 types are scenes.
Concretely missing from the plan:
* a decision that the first recogniser is fed an **ROI crop**, not the frame;
* the observation that **the plugin identity is known at inference time**, so the cropper can be a per-plugin
  constant — which dissolves the "we need a VLM for the GUI types" argument (L333-L335) for the crop step;
* the observation that the `prompt()` field in `labels.jsonl` already carries the challenge text, so a
  *text-conditioned* solver (crop the region the prompt points at) is possible for the XProtect family;
* any acknowledgement that the 13-type benchmark is 8/13 scene types.

**M2. The answer is a *substring* of the frame — the plan never states the target for a scene type.**
L185-L195 and L598-L606 treat "the prediction" as the whole string. For `haq/mapcha` the gold is `JAsb` and
the frame says "Captcha / Tries Left: 4 / JAsb". What is the model's output? The plan does not say, so the
metric in §4.5 is undefined for 25 types. (The benchmark's `norm()` keeps only `[A-Za-z0-9+\-*]`, so a
whole-frame transcription scores CER > 1 — which is exactly what we see for EasyOCR.)

**M3. `ru-numberword` is relabellable into a normal OCR task (see B15).** The plan throws away 200 usable
Cyrillic images and proposes a VLM fine-tune for a task a 40-line lexicon solves exactly.

**M4. The puzzle family's label is not recoverable (see B13).** The plan half-knows this (§2.2) and
half-misclassifies it (§0.3.1); it never says the 200 images must be *excluded* from the recogniser's
training set, where they will act as irreducible label noise.

**M5. Five types have a single constant answer and carry no information.**
`XProtect/drop` = `"drop"`, `XProtect/jump` = `"jump"`, `XProtect/sneak` = `"sneak"`, `XProtect/different` =
`"EMERALD_BLOCK"`, `China2B2T/wool` = `"LIME_WOOL"` — 500 of 4 400 images (11.4 %) whose label is a constant.
They teach a recogniser "Minecraft chat scene → a fixed word", they leak 100 % under a random split, and the
plan's type-uniform sampler (L725-L729) will *oversample* them. They should be excluded from the recogniser's
training set and used as a separate "chat-scene OCR" evaluation, or relabelled to the actual question.

**M6. The published renders are not always reproductions (licence blind spot).** `README.md` L408-L410:
sonar's dot-matrix fonts could not be redistributed (personal-use-only / no licence) so the renders
substitute Lucida Console and Courier New — *"the one place where the render is an approximation rather than
a reproduction"*; and `Archy-X/Krypton`'s swatch colours are invented. The dataset card must say which types
are approximations, and the plan's §5.5 table has no such column.

**M7. The `anvil` upstream defect (answer printed in the image) is not in the "upstream defects" table.**
`README.md` §"Faithful reproduction of upstream defects" lists 7 defects; the anvil footer leak is not among
them. It is a big one — it makes the type trivially solvable by a naive OCR, and it invalidates any
"superscript→plain" post-process design.

**M8. The plan's own M0 is blocked by a one-line harness bug (see B17).** M0 is the plan's first action and
its stated remedy is wrong; `AutoModel` is already in the repos' `auto_map` and in the model card's usage
snippet.

**M9. `bench/bench_hf.py`'s `norm()` is not a fair normaliser for a per-character metric.** L47-L52 strips
everything except `[A-Za-z0-9+\-*]`, so `_`, `[`, `]`, `,` and the space are removed from both prediction and
gold. For the 5 types whose answers contain those characters the CER is computed on a *different string* than
the label — e.g. `LIME_WOOL` → `LIMEWOOL`. The plan's §4.5 adopts this function as the definition of CER
(L676) without noting the caveat. The published baselines' CERs are therefore not exactly comparable to a
"normalised exact-match" on the raw labels.

**M10. Nothing in the plan addresses the *constant* nature of the deployment problem.** 44 types is a small
world; the plan's type-held-out k-fold is the right instrument, but a 4-fold split over ~20 family-A types
means each fold holds out 5 types — and one held-out type can move the headline by ±20 points on a
4-fold mean. The plan reports "mean ± std of the per-fold exact-match and CER" (L630-L631) but does not say
that the **per-fold** numbers, not the mean, are the honest statistic, and that the std of a 4-fold mean over
5 types per fold is huge. Reporting per-type (which the plan does want, L677) plus the median-across-types
is more robust than a fold mean.

---

## 5. Corrected numbers, in one table

| # | plan | correct value | where it came from |
|---|---|---|---|
| 1 | params ≈ 2.2 M (L76, L743) | **5 283 589** (or 3 710 725 with the literal pools) | instantiated in PyTorch |
| 2 | train 150 img/s @32×128 (L81) | **99 img/s** for the 5.28 M model; 127 for 2.64 M; 170 for 3.71 M | measured, 8 threads |
| 3 | inference 451 img/s (L81) | **371 img/s** (5.28 M) | measured |
| 4 | \|V\| = 69 / 68 classes (L156, L568, L744, L829) | **63** for the Latin OCR family (`0-9A-Za-z` + blank); 97 with Cyrillic | measured |
| 5 | Model B vocab 35 (L209, L744) | **34** | measured |
| 6 | fixed-length types: 20 (L299) | **24**, over 9 distinct lengths | measured |
| 7 | answer diversity 4…62 (L108) | **1…100** | measured |
| 8 | drop/jump/sneak: 4/4/5 answers, `dopr`/`jmpu`/`aekns` (L111-L114) | **1/1/1**; the answers are `drop`/`jump`/`sneak` | measured |
| 9 | `XProtect/color` diversity 20 (L116) | **11** | measured |
| 10 | `code`/`map`/`reverse`/… 60–62 (L117) | **100** each | measured |
| 11 | duplicate images: jump 5–6 (L120, L650) | **2** | measured |
| 12 | family C = 24 (L322) | **21** (or 23 with the puzzles moved in, per B13) | plan's own table |
| 13 | `n1zamu/anvil` needs superscript→plain (L131) | the image contains the plain answer twice | zoomed the PNG + generator |
| 14 | puzzles are family B (L131) | family C — the label is not recoverable | generator + images |
| 15 | `ru-numberword` is "not OCR at all" (L132) | family B — Cyrillic OCR + a lexicon | generator + images |
| 16 | XProtect has "thick black curves" (L475) | short straight segments; curves are the Russian family's | measured + generator |
| 17 | Graf-J finetuned = 97.4 % (L24) | **95.36 %** (97.38 % is the base model's) | model card |
| 18 | "both API queries return empty" (L1212) | `search=captcha` → 100+, `search=minecraft` → 100+; `search=minecraft captcha` and `datasets?search=captha` → empty | HF API |
| 19 | AnBot is permissive (L946) | **GPL-3.0** | upstream LICENSE + README L129 |
| 20 | GPL-3.0 forces a GPL dataset repo (L947) | the output of a covered work is covered "only if the output … constitutes a covered work" (GPL-3.0 §2) | the licence text |
| 21 | `warmup_ratio` → `warmup_step` (L1066) | `warmup_ratio` removed; the field is **`warmup_steps`** | transformers 5.19.0 |
| 22 | `batch_decode` removed (L1062) | still present on `PreTrainedTokenizerBase` in 5.19.0 | transformers 5.19.0 |
| 23 | random-split leakage (L648-L659) | **34.3 %** of test samples leak their gold answer; 2.7 % leak the image; 9 types leak 100 % | measured over 200 splits/type |
| 24 | "20 of 44" family A are clean text | 12 are single-string images; **25 are scenes** | visual + band analysis |
| 25 | H=32 keeps glyphs legible (L529) | 2.8–8.5 px for most types | generator font sizes |

---

## 6. What I would change, in priority order

1. **Add an `roi` field to `labels.jsonl`** for the 22 scene types (the generators know the coordinates
   already). This unlocks B4, B5, A1, A2 and M1 at once, and it is the single highest-leverage change in
   this review. It also converts the 13-type benchmark from "read a chat log" into "read a code", which is
   what the published baselines were *intended* to measure.

   > **Done (2026-10-21, later the same day).** The field exists, together with a `text` field beside
   > it. The generators compute it from the pen walk, and `tools/check_labels_and_roi.py` and
   > `tools/check_band_vs_answer.py` keep it honest. 29 of the 46 types carry a band.
2. **Re-cut the taxonomy as a 2×2**: {single-string, scene} × {OCR, non-OCR}. The plan's A/B/C becomes a
   *column* in that table. Family sizes, measured: single-string-OCR 12, single-string-transform 4
   (reverse, numberword×2, anvil-as-OCR), scene-OCR 22, scene-non-OCR 3, jigsaw 2, unknowable 1.
3. **Fix the architecture spec** (B1), the CTC constraint (B2) and the width clamp (B3) together — they are
   one bug: the geometry was designed for `W = 192` and never checked at `W = 48`. Print `T`, `2L+1` and the
   effective glyph height in the data-prep assert.
4. **Normalise on the text band, not the frame** (B5). `H = 32` should mean "32 px of *glyph*", not "32 px of
   picture".
5. **Drop the puzzle types from the recogniser's training set** (B13) and relabel `ru-numberword` to the
   spelled-out words (B15) so the Cyrillic model gets 300 images instead of 100.
6. **Make the augmentation policy per type** (A2, A4, B12) and drive it from the same per-type metadata
   (frame size, glyph size, has-interference, is-scene).
7. **Fix the licence table** (B6) and reconsider the repo split (B7); add a *font*/*approximation* column to
   the dataset card (M6).
8. **Fix M0**: add an `AutoModel` fallback to `bench/bench_others.py` (B17) — 10 minutes, and it puts the
   strongest known CRNN on the table.
9. **Re-measure the throughput table** against the model you will actually train (B1) and re-plan the
   wall-clock (A8).
10. **Publish the in-domain number on a held-out *sample* split**, and keep the 104-image set as a harness
    regression check (B18).
11. **Fix the confidence computation** (A5) — use the CTC forward-backward posterior, or a prefix-beam
    probability, and drop the "geometric mean ≡ path probability" equivalence.
12. **Restate the Hub-niche claim correctly** (B8) and drop the two fabricated answer strings `dopr`/`jmpu`/
    `aekns` (B9).

---

*Reviewer artefacts: `build/review/measure_dataset.py`, `per_type_table.py`, `arch_check.py`, `arch_check2.py`,
`leak_interf.py`, `interf2.py`, `legibility.py`, `charset.py`, `check_transformers.py`, `sheets.py`,
`dataset_facts.json`, and the contact sheets `sheet_scenes.png`, `sheet_rest.png`, `sheet_puz3x3.png`,
`sheet_numberword.png`, `sheet_anvil_zoom.png`, `sheet_xp_map.png`, `sheet_ruweb.png`.*
