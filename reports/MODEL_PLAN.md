# CaptchaOCR — model plan (architecture, augmentation, training, publishing)

**Status:** design document, written 2026-10-21. **Partly implemented since** — see the note below.
**Date:** 2026-10-21
**Scope:** the *first* model, the *first* augmentation pipeline, the *first* Hugging Face release.
**Ground truth for every number below:** measured on this machine (see §0.2), or quoted from a primary
source with a link (§7).

> **What has changed since this plan was written (2026-10-21, later the same day).**
>
> * **There is a GPU.** The machine has an **NVIDIA GeForce GTX 1080 Ti (11.8 GB, sm_61)**, driver
>   581.57. The system Python still carries `torch 2.14.1+cpu`, but a CUDA build
>   (`torch 2.14.1+cu126` - the newer wheels dropped the sm_61 kernels the 1080 Ti needs) is installed in
>   `.venv-gpu/`. Training runs at **920 img/s** on the GPU against **99 img/s** on the CPU. Every
>   "no GPU" statement in this plan is therefore obsolete; see **§0.2**.
> * **The training code exists**: `train/captcha_crnn.py` and `train/train.py`, with `train/README.md`.
>   The model is a CRNN + CTC with **4 623 615 parameters** and **63 classes** - a fourth reading of the
>   §4.2 spec, and the one that runs.
> * **The `roi` field this plan was missing now exists** in every `labels.jsonl`, together with a `text`
>   field: `roi` is the bounding box of the text band that carries the answer (`null` when the whole
>   frame is the text), `text` is the string that is *drawn* in the picture. The pipeline therefore crops
>   to the band and scales the **glyph** to 32 px, instead of normalising the frame as §4.1 proposes.
>   This is the change the review of this plan (`docs/adr/0002-recogniser-architecture-and-data.md`, B4/B5 and item 1 of §6)
>   asked for, and it is the one that matters most.
> * **The dataset has changed shape**: **46 types and 4 600 labelled images** (34 + 12 types, 100 each),
>   not 44 and 4 400. The `ru-puzzle2x2` / `ru-puzzle3x3` types are **gone** - the puzzle family is
>   LimboFilter's `FRAMED_CAPTCHA` and is generated as `LimboFilter/framed3x3` (384x384) and
>   `LimboFilter/framed2x2` (256x256); they remain a solver problem, not a recogniser's training target.
>
> The measurements inside this plan that were taken against the old tree (§0.2, §0.3, the family A/B/C
> split) are marked where they have moved on.

---

## 0. Executive summary

| Question | Answer |
|---|---|
| **First architecture** | **CRNN (CNN + BiLSTM) + CTC head, trained from scratch**, published as a `trust_remote_code` custom HF repo, **plus an ONNX export** |
| **Runner-up 1** | **PP-OCRv6_medium_rec** (19 M params, Apache-2.0, ONNX available) — not as *our* first model, but as **the baseline we must add to the benchmark this week**; it is the strongest ready-made model in the world for this problem |
| **Runner-up 2** | **TrOCR (`microsoft/trocr-base-printed`) fine-tune** — the thing to beat (61 k downloads, the top captcha model on HF), but 334 M params vs 4 600 images ⇒ not trainable in reasonable time on CPU; on the 1080 Ti it becomes viable |
| **Runner-up 3** | **PARSeq / SATRN / VisionLAN / ABINet** — scene-text SOTA, wrong problem shape (long curved text + LM), 3–10× the compute, no HF packaging ⇒ later |
| **VLM OCR** | **No, not for the text types.** The 2025-26 frontier is *document parsing*; a 19 M OCR model beats Qwen3-VL-235B on OCR. VLMs are the right tool for the **non-text** types (GUI/puzzle/colour/arithmetic) — a second system, not the first model |
| **Augmentation** | **Albumentations 2.0.8** + ~3 custom transforms. Geometric warps **weak** (the generator already distorts), photometric/noise/**JPEG+WebP compression** strong, compression applied **last** |
| **Validation** | **Type-held-out k-fold** (k=4) as the headline generalisation number + the existing 13-type benchmark as the in-domain comparison number. Two numbers, both reported |
| **Publishing** | Custom-code repo with `AutoConfig`/`AutoModel`/`AutoProcessor` in `auto_map`, **no sub-processor** (this is the single change that fixes the v5 load failures), `processor_config.json` **and** `preprocessor_config.json`, `vocab.json` (no tokenizer), ONNX via `torch.onnx.export` (**not** `optimum` — it is incompatible with transformers 5.x), MIT weights, per-family dataset repos with per-family licences |
| **Biggest surprise** | **PP-OCRv6** (arXiv 2606.13108, June 2026) is downloadable as ONNX with a character dictionary, and **is not in the current benchmark**. Adding it is ~30 lines and needs only `onnxruntime`, which is already installed |
| **Second surprise** | `Graf-J/captcha-conv-transformer-finetuned` (MIT, 12.3 M params) scores **97.4 % / 88.4 %** on real captcha distributions and its whole architecture is **50 lines**. It fails under transformers 5.x only because of the config/processor *format*, not the weights |
| **Third surprise** | The dataset is **not one task**. Only ~20 of 46 types are image→text. The Russian "number-word" family has a **digit** answer for a **word** image, and the object-swatch family has a colour name for an image with **no text at all** |
| **Hard blocker** | ~~**No GPU on this machine**~~ — **there is one**: an NVIDIA GeForce GTX 1080 Ti (11.8 GB, sm_61), with a CUDA build in `.venv-gpu/`. Measured: 920 img/s training for the 4.62 M-param CRNN on the GPU (99 img/s on the CPU) |

---

## 0.1 The three findings that shape everything else

**1. The 2025-26 "OCR frontier" is document parsing, not short-string recognition.**
The new models on the Hub are DeepSeek-OCR / DeepSeek-OCR-2, GLM-OCR, Xiaomi-OCR-0, MinerU 2.5,
Baidu Unlimited-OCR, PaddleOCR-VL, Qianfan-OCR, Chandra-OCR, Naqta-OCR, typhoon-ocr. Every one of them
targets *pages*, not 4-character strings. The irony is quantified in the PP-OCRv6 paper: the 19 M-param
PP-OCRv6_medium reaches **83.2 %** weighted-average recognition accuracy and **beats**
Qwen3-VL-235B (74.9), Gemini-3.1-Pro (71.4), Kimi-K2.6 (62.9), GPT-5.5 (64.2) and MiniMax-M3 (54.1)
on OCR benchmarks. *Small task-specific models beat frontier VLMs at OCR.* That is the thesis of this
project, with numbers.

**2. The failure of every off-the-shelf model we measured is a domain problem, not a capacity problem.**
`anuashok/ocr-captcha-v3` (TrOCR-base, 61 323 downloads) claims **CER 0.0139** on its own distribution
and scores **CER 0.785 / acc 0.077** on ours. That is not "TrOCR is bad at captchas" — it is
"TrOCR fine-tuned on one captcha style does not transfer to a different one". The same story plays out
in `Graf-J`'s own numbers: the same CRNN scores **96.81 %** on the distribution it was trained on and
**9.65 %** on an unseen one, until it is fine-tuned (**86.20 %**). *Everything in this plan follows
from that: the model must be trained on our data, and the validation must measure transfer to unseen
styles, not memorisation of seen ones.*

**3. Our dataset already contains the distortion, so augmentation must not add more — it must simulate
the *deployment* instead.** The generators already draw per-glyph rotation, wave/ripple, bezier
interference curves, blur, noise, and photo backgrounds. A generic OCR augmentation recipe (heavy
elastic, strong perspective) applied on top of that produces *ambiguous* labels, not hard ones. The
augmentation's job here is the axis the generator cannot produce: **compression, rescaling,
screenshotting, colour and polarity shifts**. That is why §3 puts compression last and makes it strong,
and why the geometric section is deliberately weak.

---

## 0.2 Measured environment (this machine, 2026-10-21)

Everything in the plan is written against this, so the numbers are reproducible.

| Item | Value |
|---|---|
| Python | 3.14.5 |
| torch | **2.14.1+cpu** — `torch.cuda.is_available() == False`, 0 devices, 18 CPU threads |
| **GPU** | **NVIDIA GeForce GTX 1080 Ti**, 11 264 MiB (11.8 GB), sm_61, driver 581.57 — present, and **usable**: a CUDA build (`torch 2.14.1+cu126`, `torch.cuda.get_arch_list()` contains `sm_61`) is installed in `.venv-gpu/`. Measured: **920 img/s** training for the 4 623 615-param CRNN, against 99 img/s on the CPU |
| torchvision | 0.29.1 |
| transformers | **5.19.0** |
| huggingface_hub | 1.33.0 · tokenizers 0.23.2 · safetensors 0.8.0 · accelerate 1.15.0 |
| numpy 2.4.6 · scipy 1.18.1 · scikit-image 0.26.0 · shapely 2.1.2 · pillow 12.2.0 | present |
| opencv-python-headless 5.0.0.93 · onnxruntime 1.30.0 · easyocr 1.7.2 · diffusers 0.41.0 | present |
| **absent** | `datasets`, `albumentations`, `evaluate`, `optimum`, `peft`, `timm`, `tensorboard` |
| `import transformers.onnx` | **ModuleNotFoundError** — the module was removed in v5 (verified locally) |

Measured CRNN training throughput (2.02 M params, 4 conv blocks + 2-layer BiLSTM, CTC loss,
`torch.set_num_threads(8)`, batch 32) — **on the CPU**; the GPU numbers are in the row above:

| input | train step | train img/s | inference | inference img/s |
|---|---|---|---|---|
| 32×128, B=32 | 213 ms | **150** | 70.9 ms | **451** |
| 32×160, B=32 | 275 ms | 116 | 86.9 ms | 368 |
| 48×192, B=16 | 258 ms | 62 | 78.9 ms | 203 |
| 64×256, B=8 | 236 ms | 34 | 77.0 ms | 104 |

Consequences:
* A 2 M-param CRNN at 32×128 is **cheap**: 3 400 training images ≈ **23 s/epoch** of pure compute.
  A 60-epoch run is ~25 min; a 4-fold type-held-out experiment is **2–3 h on this CPU** — and
  **minutes on the 1080 Ti**, which is where it actually runs now.
* Evaluation is free: the whole dataset scores in ~10 s.
* **This inverts the usual priority.** When the model is this cheap, the lever is the *data*, not the
  architecture. Spend the compute on k-fold validation and on ablation, not on a bigger backbone.
* TrOCR-base (334 M params, 384×384) is ~100–300× the per-image cost: **20–60 h for 3 epochs on this
  CPU**, and about **1–2 h on a consumer GPU** — hence it is runner-up 2, not the first model.

---

## 0.3 Measured dataset facts (re-measured 2026-10-21, after the `out_ru/` growth)

**4 600 labelled images · 46 captcha types · 100 images per type** (`dataset/out/` 34 types +
`dataset/out_ru/` 12 types). *The census below was taken against the 44-type tree of that morning
(4 400 images); the type list and the two `ru-puzzle*` rows have since changed — see the note at the
top of this document.*) Union charset **101 symbols**:
`,-0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ[]_abcdefghijklmnopqrstuvwxyz` + 33 Cyrillic
`абвгдежзийклмнопрстуфхцчшщъыьэюяё`.

Answer-length histogram: 5→1068, 4→765, 6→648, 3→590, 1→271, 2→172, then a long tail up to 70
(the `jSdCool/minecaptcha/image` sprite-atlas labels). **2 880 distinct answers** over 4 400 samples
(the same census over the 46-type tree has not been re-run).

**Crucially, the per-type answer diversity is wildly uneven** — this drives the sampling design in §4.5:

| type | distinct answers / 100 samples |
|---|---|
| `LagBug/XProtect/drop` | **4** (`dopr`) |
| `LagBug/XProtect/jump` | **4** (`jmpu`) |
| `LagBug/XProtect/sneak` | **5** (`aekns`) |
| `LagBug/XProtect/slot` | 8 |
| `LagBug/XProtect/color` | 20 |
| `LagBug/XProtect/code`, `/map`, `/reverse`, `Archy-X/Krypton/map`, `haq/mapcha/map`, … | 60–62 (full alphabet) |

Three of those types are **fixed upstream** — the generator's own README records 8 duplicate images per
100 for `sneak`, 5–6 for `jump`, 2–5 for `drop`. A random image split therefore puts *the same answer*
in both train and val. **This alone justifies the type-held-out split** (§4.4).

### 0.3.1 The dataset is not one task — the taxonomy

Reading the generator sources (`RussianCaptcha.java`, `ObjectCaptcha.java`) and the plugin docs gives
three families, not one. This matters for "what is the first model for":

| Family | Types | Is the answer recoverable from pixels alone? | Model |
|---|---|---|---|
| **A. Text in the image** | the 13 benchmark types + `GalleryCaptcha/ru-symbols`, `Z4OLLIEZ4/reCaptcha/captchasx`, `GalleryCaptcha/ru-web`, `jonesdevelopment/sonar/{complex,legacy}`, `CaptchaVerifyZ/map`, `BotFilter/map`, `ringoame196/.../map`, `LimboFilter/symbols` | **yes** | **image→text recogniser — our first model** |
| **B. Text in the image, but the answer is a *transformation*** | `LagBug/XProtect/reverse` (read then reverse), `n1zamu/NCaptcha/anvil` (Unicode superscript digits → plain decimal), `GalleryCaptcha/ru-numberword(-caption)` and `LimboFilter/map` (read the Russian words → the digits) | yes, with a per-type post-process | recogniser + per-type head/post-process (a "type-aware" solver) |
| **C. Not OCR at all** | `GalleryCaptcha/ru-object-swatch` (3×3 flat colour fills, answer is a *colour name*; the source says "This is **not** an OCR task"), `LimboFilter/framed2x2` / `framed3x3` (**the answer lies in turned frames** - the frames have to be turned and reassembled first), `China2B2T/wool`, `Yukun99/itemslot`, `FeelingAlive0/button`, `Joey61021/colorgui`, `CaptchaGUI/clickblock`, `LagBug/XProtect/{color,different,drop,gui,jump,picture,slot,sneak}`, `FeelingAlive0/math`, `Mrbysco/Captcha/math`, `LagBug/XProtect/equation`, `Archy-X/Krypton/menu`, `jSdCool/minecaptcha/image` | **no** | classification / grounding / arithmetic / **VLM** — a *different* model |

Roughly **20 of 46 types are family A**. That is the target of the first model, and the first model
should be trained on family A + the transformable part of family B, with the per-type transformation
kept in the solver (not the recogniser) so that the recogniser stays a pure image→string function.

> This is also the honest answer to "one model for everything": a single image→string model cannot
> solve `ru-object-swatch` (a colour match). The number-word family *can* be solved by a recogniser
> plus a 40-line lexicon - which is what the dataset now does, with the drawn words in the `text`
> field and the digits in the `answer` field.

**The taxonomy above is the one the review of this plan attacked** (`docs/adr/0002-recogniser-architecture-and-data.md`,
B4/B15): it classifies by *what the answer is* and not by *what the image is*, and 29 of the 46 types
are scenes in which the answer is one line among several. The `roi` field in `labels.jsonl` now
answers that second axis, and the training pipeline crops to the band before the recogniser sees the
image.

---

## 1. Architecture choice for the first model

### 1.1 The recommendation

> **A 2–3 M-parameter CRNN — 4 conv blocks (32/64/128/256) with BatchNorm+ReLU, a 1×1 conv
> reduction, a 2-layer bidirectional LSTM (hidden 256), and a linear CTC head over a 68-symbol
> character vocabulary — trained from scratch on family A, with an optional stage-1 pretraining on a
> large public generic-captcha corpus. Greedy CTC decoding with a calibrated per-character
> confidence. Published as a `trust_remote_code` custom repo plus an ONNX export.**

> **As built:** `train/captcha_crnn.py` — CRNN + CTC, **4 623 615 parameters**, **63 classes**
> (blank + `0-9A-Za-z`), 3 pools `(2,2), (2,2), (2,1)`, 4 feature rows, BiLSTM(256, 2, bidirectional).
> The vocabulary is the 63-symbol Latin set, not the 68-symbol one proposed above, and the input is
> the **band**, scaled so the glyph is 32 px tall.

### 1.2 Why, in the order that actually decided it

**(a) Dataset size vs model size.** 4 600 images, 46 types, 63 effective classes, 4–6 characters per
answer. A 2 M-param model has ~37 000 parameters per training image; a 334 M-param TrOCR has 76 000
*per character*. For a random alphanumeric string there is no semantic structure to amortise a large
model over — the model is learning glyph shapes and a 63-way classifier, and that is a small problem.
`confiacompany/confia-captcha-ocr-pt` ships **1.2 M parameters** for exactly this task; `Graf-J`'s CRNN
is **3.57 M**. The community has already converged on 1–4 M for captchas, and the evidence is that
this size reaches 96.8 % on a 1.37 M-image corpus. We are not short of capacity; we are short of
*data*, and a small model is the one that does not overfit it.

**(b) CTC vs attention decode.**
*CTC wins here:*
* The labels are 4–6 random characters. A language model has **nothing to exploit** — `7Kq2m` is no
  more or less likely than `7Kq2n`. The advantage of attention decoders (PARSeq, SATRN, ABINet) comes
  from a lexicon or LM prior over *real* words; on random strings an LM is at best neutral and at
  worst actively harmful (it steers the decoder toward a more frequent but wrong string).
* CTC needs **no decoder at all** for the greedy path: `argmax → collapse repeats → drop blanks`. That
  is O(T) with no hyper-parameters, and it is what PP-OCRv6's CTC head does.
* CTC gives **per-character posteriors directly**, which is a hard requirement here (a confidence
  score for the human-in-the-loop solver and for the ensemble). Attention decoders give you sequence
  log-probabilities but no clean per-character posterior, and their confidence is famously
  miscalibrated.
* CTC is **alignment-free**, so it does not need a segmentation or a character detector — a decisive
  advantage on captchas where the text can be anywhere in the frame and the "background" is often
  other text (chat scenes, map titles, counters).
* CTC trains stably on small data; attention decoders are notoriously unstable with <10 k samples
  without careful warmup and label smoothing.

*Attention wins only in:* long, curved, hard-to-segment scene text (IC15/CUTE80 class benchmarks) where
the LM prior is real. That is not our problem.

*Recommended compromise (PP-OCRv6 does exactly this):* if CTC plateaus on the unseen-style split, add
an attention head on the **same encoder** with a hybrid loss (λ·CTC + (1−λ)·attention, λ=0.7) and
decode with the attention head on low-confidence samples only. Cheap, and it reuses the trained
encoder.

**(c) Per-character vs per-word vocabulary.** **Per-character, unambiguously.** There are 2 880
distinct answers over 4 400 samples (the census of that morning; not re-run over the 46-type tree) —
a word vocabulary would be two-thirds the size of the training set, would never generalise to an
unseen plugin, and would not support the variable-length labels that family A produces. Per-character
also gives the confidence signal for free, handles a 3-char and a 6-char answer with the same head, and
matches what every working captcha model does (`Graf-J`, `confiacompany`, PP-OCRv6).

**(d) The Cyrillic question — and it has a much simpler answer than expected.**
The union charset is 101 symbols, but the Cyrillic is **not** spread across the dataset. Measured:
**only 2 of 44 types contain Cyrillic** — `GalleryCaptcha/ru-symbols` (18-character answer, full 33-letter
alphabet, 250×150) and `GalleryCaptcha/ru-object-swatch` (which is not OCR at all, §0.3.1). The
"Russian number-word" family that the owner has in mind has a **digit** answer for a **word** image —
`ru-numberword` and `ru-numberword-caption` are digits `0-9`, length 2–3.

> **Since then.** The number-word family is no longer "a third thing out of scope for a recogniser":
> the dataset now carries the **spelled-out words** in the `text` field and the digits in the `answer`
> field, so it is an ordinary Cyrillic OCR task plus a 40-line lexicon - exactly the correction the
> review of this plan made (B15). The symbol family is now three characters of the plugin's Cyrillic
> alphabet rather than eighteen, and the number-word types are Cyrillic **in the drawn text** even
> though their answer is digits. Counting the `text` field of the shipped tree, Cyrillic appears in
> **8 of the 46 types** (`GalleryCaptcha/ru-numberword`, `ru-numberword-caption`, `ru-symbols`,
> `ru-object-swatch`, `LimboFilter/{map,symbols,framed2x2,framed3x3}`) - not the "2 of 44" quoted
> above. The built Model A uses the **63**-symbol Latin set (`0-9A-Za-z` + blank); Model B is the
> 34-symbol Cyrillic set (33 letters + blank), plus the ten digits `LimboFilter/symbols` needs.

So the decision is:

> **Do not put Cyrillic in the first model's charset. Train two models.**
> * **Model A (Latin)**: 68 symbols (`,-0123456789A-Z[]_a-z`), 42 types minus the Cyrillic ones.
> * **Model B (Cyrillic)**: 35 symbols (blank + 33 Cyrillic + blank), trained on `ru-symbols` only
>   (100 images) plus, if the owner wants it, a **stage-1 pretraining on a public Cyrillic captcha
>   corpus**. `remiai3/synthetic-captchas-library` has 100 000 images per script across 44 writing
>   systems including Russian, CC BY 4.0 — that is the pretraining set.
> * The **Russian number-word** family is a *third* thing (word→number) and is out of scope for a
>   recogniser; see §2.5.

Why not one union model: 33 extra softmax classes for 2.3 % of the data is a bad trade, and a union
model also forces one input geometry on two visually distinct families. Why not one model per type:
absurd — 44 models, no shared learning, and the whole point of the dataset is that a *style-agnostic*
recogniser should exist. Why not per-charset-family with a shared encoder: the two families do not
share enough visual structure to justify the complexity in v1.

**(e) The `LagBug/XProtect/reverse` and `n1zamu/NCaptcha/anvil` cases.** These are family B: the
image contains the text, but the expected answer is a transformation of it. Put the transformation in
the **solver**, keyed by captcha type, not in the recogniser. The recogniser stays a pure
`image → string` function; the solver is `image → string → answer` with a per-type post-process. This
keeps the recogniser reusable and the per-type logic auditable in one file.

### 1.3 The two runners-up, and why they lose

**Runner-up 1 — PP-OCRv6_medium_rec (19 M params, Apache-2.0, ONNX available).**
Not our first *trained* model, but **the baseline we must have**. Its own numbers: 83.2 % W-Avg over
16 scenario benchmarks; on the **"Confusable"** category (the closest to CAPTCHA) 64.9 %; it beats
PP-OCRv5_server (78.1) by +5.1 and PP-OCRv5_mobile (73.7) by +9.5, while beating Qwen3-VL-235B,
GPT-5.5 and Gemini-3.1-Pro. The architecture is LCNetV4 (MetaFormer-style, structural
reparameterisation) + `EncoderWithLightSVTR` (local-global attention) + a **CTC+NRTR multi-head
decoder** — i.e. exactly the hybrid we recommend as the v2 upgrade.

Why it loses as *our* first model:
1. It is a **PaddlePaddle** model. Training it means the PaddlePaddle stack (not installed; `paddleocr`
   on Windows + Python 3.14 is a real risk), and it is not a `transformers` model, so it does not
   compose with the HF publishing path the owner wants.
2. Its 50-language vocabulary (~18 k classes) is enormous for our 68 classes; the recognition head is
   mostly wasted capacity and the char-dict has to be swapped.
3. It gives a **whole-string** `rec_score`, not a per-character confidence — so it does not satisfy the
   human-in-the-loop requirement on its own.
4. Our own model trained on our data will beat it *on our data*; that is the point of the project.

**But**: `PaddlePaddle/PP-OCRv6_medium_rec_onnx` ships `inference.onnx` + `inference.yml` (the
character dictionary) + `inference.json`, 76.5 MB, 55 342 downloads, Apache-2.0. `onnxruntime` is
already installed. **Adding it to `bench/bench_onnx.py` is ~30 lines and needs no new dependency.**
Do this before writing any training code — it changes what "beating the baseline" means.

**Runner-up 2 — TrOCR (`microsoft/trocr-base-printed`) fine-tuned.**
This is the number to beat: `anuashok/ocr-captcha-v3` is the most-downloaded captcha model on the Hub
(61 323 downloads, 43 likes) and it scores **acc 0.077 / CER 0.785** on our 13-type benchmark.
TrOCR wins on: an ImageNet-pretrained ViT, a strong prior, and *zero* training from scratch (it
fine-tunes in a few epochs). It loses on:
1. **Size:** 334 M params vs 4 600 images.
2. **Compute here:** 384×384 inputs, no GPU ⇒ 20–60 h for 3 epochs. Not viable on the CPU; on the
   1080 Ti it is roughly 1–2 h for 3 epochs, i.e. plausible but still 30× the CRNN.
3. **Exact-match decoding:** autoregressive generation, no CTC posteriors, and `max_new_tokens`
   truncation silently produces a partial string (a real failure mode: it can score a *correct prefix*
   as a wrong answer).
4. **The evidence against it:** its own fine-tune goes from CER 0.0139 (own distribution) to 0.785
   (ours). `arkhabbazan/ocr-digits-captcha` reports 99.93 % exact match on synthetic digits and says
   outright that "real-world accuracy was not measured on a held-out real set, so the scores below do
   not prove it". The pattern is consistent: TrOCR fine-tunes overfit their generation script.

Keep it in the comparison table. Try `trocr-small-printed` (62 M) as a cheap sanity check that the
transformer route is not broken rather than broken, and consider a TrOCR arm of the model *card* for
the lab narrative.

**Runner-up 3 — PARSeq / SATRN / VisionLAN / ABINet.**
PARSeq (ECCV 2022) is still the reference modern STR model: IIIT5K 97.0, SVT 93.6, IC15 86.5,
CUTE80 92.2, and permutation training is worth +3–4 points over left-to-right-only. It is also the
architecture the `awesome-ocr-2026` reference still lists first.
Why it loses *for the first model*:
1. **Wrong problem shape.** Those benchmarks are 20–30 character curved words where a language model
   is a genuine advantage. Our labels are 4–6 random characters.
2. **Compute.** A 12-layer transformer encoder + 12-layer decoder is 3–10× a CRNN for no expected gain.
3. **Packaging.** The reference implementation is `pytorch_lightning` (unmaintained), has no
   `transformers`-native `auto_map` packaging, and would have to be rewritten for transformers 5.x —
   a project of its own.
4. **The evidence is against it in this domain too:** `Graf-J` built a "Convolutional Transformer" that
   beat a CRNN by 0.6 points on the training distribution and 2.2 points on the unseen one — i.e. the
   *architecture* barely matters; the *training data distribution* is what moved the number from 9.65 %
   to 88.42 %.

Keep PARSeq as a **cited, later** slot ("if the CRNN plateaus on unseen styles, try a permutation
AR decoder"), and consider porting `baudm/parseq` to a `trust_remote_code` repo as a v2 contribution —
it would be a genuinely novel HF artefact.

### 1.4 What about the newer 2025-26 things?

| Thing | Verdict |
|---|---|
| **Masked-autoregressive text recognisers** (e.g. the 2025 line of "Accurate Scene Text Recognition with Efficient…" arXiv 2503.16184, SOTA on 10/11 benchmarks using only real data) | Same family as PARSeq — a stronger AR/NAR recogniser for *scene text*. Same objections (problem shape, compute, no HF packaging). Later. |
| **Unified understanding models / end-to-end document models** (DeepSeek-OCR, MinerU 2.5, GLM-OCR, PaddleOCR-VL, Unlimited-OCR, dots.ocr-style models) | **Document parsing**, i.e. page → markdown. Wrong granularity: we need 4 characters, they want a page. Also 0.5 B–9 B params. Wrong tool. |
| **PP-OCRv6** (LCNetV4 + LightSVTR + CTC+NRTR) | The most relevant new thing — a *small* model that is SOTA at OCR. Baseline to beat (§1.3). |
| **Slot-head CNNs** (`confiacompany/confia-captcha-ocr-pt`: 3 conv blocks → 6×20 feature grid → **5 positional slot heads** of ~30 px each, 1.2 M params, 150×50 input, <5 ms CPU) | **Underrated and directly relevant.** For *fixed-length* captchas, a per-slot classifier beats CTC: no alignment ambiguity, exact per-character confidence, and O(1) output length. 20 of our 46 types have a fixed answer length. **Strong v2 candidate: a "CapthaSlot" model for the fixed-length types, alongside the CTC model.** |

---

## 2. The VLM question, answered properly

### 2.1 Are VLMs worth it for 4-6 character strings? **No.**

Evidence, not vibes:
* **PP-OCRv6_medium (19 M) beats Qwen3-VL-235B (74.9 vs 83.2 W-Avg), Gemini-3.1-Pro (71.4),
  Kimi-K2.6 (62.9), GPT-5.5 (64.2), MiniMax-M3 (54.1)** on OCR benchmarks, and does it with
  "orders of magnitude fewer parameters". The gap is *larger* on hard categories: on "Confusable"
  PP-OCRv6 gets 64.9 vs Qwen3-VL-235B's 56.1 — **and "confusable" is exactly captcha territory**.
* **Latency.** The existing EasyOCR baseline already costs **388 ms/image** on CPU in this repo. A 7B
  VLM at a 720² pixel budget is 1–3 s/image on a GPU and *minutes* on this CPU. Captcha solving is a
  latency-sensitive loop (a player waits ~5 s before being kicked).
* **Cost.** 7B–9B params vs 2 M. On the 11.8 GB of a 1080 Ti a 7B model in half precision is a
  squeeze, and it is out of the question on the CPU.
* **Instability.** VLMs *hallucinate* and *refuse* on short strings; a recogniser cannot. A solver that
  says "I can't read this" is worth more than one that confidently returns a wrong 6-character string.

### 2.2 Where VLMs *do* win — and they win big

The VLM wins whenever the task needs **reasoning over the image, not reading text out of it**. That
is precisely family C (§0.3.1) — 15 of our 46 types:

* `GalleryCaptcha/ru-object-swatch`: pick the cell whose colour matches the requested colour name.
  Pure classification, not OCR — a 15-class CNN, not a VLM.
* `LimboFilter/framed2x2` / `framed3x3`: the picture is cut into maps and **each map is turned by a
  multiple of 90°**, so the text lies in turned frames. This needs *spatial reasoning* (which frame is
  where) plus a rotation-aware recogniser. A VLM is the natural tool; a pipeline of detector +
  rotation classifier + recogniser is the cheaper one.
* The GUI/action types (`wool`, `itemslot`, `button`, `colorgui`, `clickblock`, `color`, `different`,
  `drop`, `gui`, `jump`, `picture`, `slot`, `sneak`) need *grounding* (which item, which cell) — a
  detection problem.
* The arithmetic types (`equation`, `math` ×2) need OCR **plus** arithmetic; the OCR half is our model.

> **Note.** The number-word family used to be listed here as well ("read «четыреста семьдесят один»
> and output `471`"). It no longer belongs to the VLM family: the dataset now carries the words in
> `text` and the digits in `answer`, so a **Cyrillic recogniser plus a 40-line lexicon** solves it
> exactly and 1000× cheaper. That is the correction the review of this plan made (B15).

### 2.3 The one serious open system, and what it implies

**`CaptchaKraken/CaptchaKraken-v1.2-GGUF`** (2 996 downloads) is a LoRA on **Qwen3.5-9B**, merged and
quantised, under a *source-available* licence ("CaptchaKraken Source-Available License v1.1": you may
build commercially where captcha solving is an internal component; you may **not** sell the solve or
expose it through a paid/public solving API). Its v1.2 covers **44 puzzle types across 10 vendors**
(reCAPTCHA, GeeTest, NetEase Yidun, BotDetect, Tencent, Prosopo, Yandex, Tencent, Lemin, MTCaptcha),
including **animated** challenges and **typed-text** captchas. Its own eval, on a 1 458-sample
held-out real set, is a **graded score of 0.6155** (reCAPTCHA 0.600, GeeTest 0.780, BotDetect 0.929,
Yandex 0.364), and the GGUF build is ~5 points below the same weights served with vLLM.

What it tells us, concretely:
1. **The VLM approach is already occupied, at scale, for the puzzle/GUI families** — the ones we cannot
   solve with a recogniser. It is *not* occupied for the "read a 4-6 character string" problem, which
   is where our dataset is strongest.
2. **The score is graded, not exact-match.** 0.6155 is not comparable to our 0.115 / 0.077. Do not put
   it in the same table; put it in a "related work" section.
3. **It is prompt- and format-sensitive** — you must send the exact training prompts, leave thinking
   off (otherwise the answer lands in `reasoning` and `content` comes back **empty on every puzzle**),
   and use a flat 720² pixel budget. That fragility is itself an argument for the small model: our
   model has no prompt surface at all.
4. **The licence is a useful precedent for our own release** (§5.5).

`ATH-MaaS/CaptchaMind-7B` (Qwen2.5-VL-7B, Apache-2.0) + the `ATH-MaaS/Captcha` dataset
(CC BY-NC 4.0, 3 153 downloads) is the open-licence analogue, but its model card is empty and its
dataset is non-commercial — a weaker option.

### 2.4 Conclusion on VLMs

* **Not the first model.** Not the second model either, for the text types.
* **Yes, as a second system** for family C. The natural entry point is no longer `ru-numberword`
  (that one is solved by a recogniser plus a lexicon now) but the **framed** captcha
  (`LimboFilter/framed2x2` / `framed3x3`), where the answer lies in turned frames.
* If the owner wants a single artefact that covers more types, the honest framing is: **"a CRNN
  recogniser for the 31 OCR types, plus a VLM for the 15 non-text types"** — and the VLM part is
  exactly what CaptchaKraken does. That is a legitimate, publishable project, but it is the *second*
  paper, not the first model.

---

## 3. Augmentation pipeline

### 3.1 Library choice

**Albumentations 2.0.8** (MIT, Python ≥3.9) as the engine, plus a small custom module for the three
things it does not do.

*Why albumentations and not torchvision:* it is OpenCV-backed (fast), it has exactly the ops we need
(`ElasticTransform`, `GridDistortion`, `GridElasticDeform`, `Perspective`, `PiecewiseAffine`,
`OpticalDistortion`, `ImageCompression`, `GaussNoise`, `ISONoise`, `MultiplicativeNoise`, `ShotNoise`,
`SaltAndPepper`, `Downscale`, `ColorJitter`, `RandomGamma`, `RandomBrightnessContrast`,
`HueSaturationValue`, `Blur`/`Defocus`/`MotionBlur`/`Sharpen`, `ToGray`, `InvertImg`,
`CoarseDropout`/`Erasing`, `ChannelDropout`, `PadIfNeeded`), and it composes them in a single
`A.Compose`. torchvision v2 is for batch-level ops (Mixup/CutMix) — **which we are not using**, see
§3.5. The albumentations docs themselves recommend exactly this split.

*Environment check:* `albumentations==2.0.8` requires `numpy>=1.24.4` ✓, `scipy>=1.10` ✓,
`opencv-python-headless>=4.9.0.80` ✓ (5.0.0.93 installed), `pydantic>=2.9.2` ✓ (2.13.4), `PyYAML` ✓,
`albucore==0.0.24` (pip will fetch it). It installs cleanly into this env on Python 3.14.

*Custom transforms we must write (3, ~150 lines total):*
1. `InterferenceCurves` — draw 1–6 quadratic/bezier strokes **on top** of the text, the way the
   generators do. Highest-value single augmentation in the list (§3.4).
2. `WebPCompression` — `cv2.imencode('.webp', img, [IMWRITE_WEBP_QUALITY, q])` + decode. Albumentations
   has `ImageCompression` (JPEG only).
3. `StrikethroughLines` — 1–3 straight lines across the text band (some plugins draw a strike bar over
   the glyphs; `laforetbrut/are-you-sure` literally draws "a one-pixel translucent strike bar *after*
   the glyphs").

### 3.2 The pipeline, in order, with ranges

> **The generator already distorts.** These augmentations simulate the *deployment* (compression,
> rescaling, screenshotting, colour, polarity), not more distortion. The geometric section is
> deliberately weak; the photometric/noise/compression section carries the weight.

Applied **in this order**, to **training data only**:

| # | Stage | Transform (albumentations / custom) | Range | p |
|---|---|---|---|---|
| 1 | **Whole-image geometry** | `A.Affine` (rotate ±8°, translate ±4 %, scale 0.85–1.15, shear ±5°) | as listed | 0.5 |
| | | `A.Perspective` (scale 0.03–0.10) | | 0.2 |
| | | `A.PiecewiseAffine` (scale 0.01–0.03) | | 0.1 |
| 2 | **Local warp** | `A.ElasticTransform` (alpha 4–8, sigma 2–3) | | 0.12 |
| | | `A.GridDistortion` (num_steps 4, distortion_limit 0.15) | | 0.10 |
| | | `A.OpticalDistortion` (distortion_limit 0.15) | | 0.10 |
| 3 | **Resolution** | `A.Downscale` (scale_range 0.5–1.0) + `A.Resize` back, filter chosen per direction (`INTER_AREA` down, `INTER_LINEAR` up) | | 0.30 |
| 4 | **Occlusion** | **`InterferenceCurves`** (custom): 1–6 quadratic strokes, 1–3 px, black/white/grey or random, alpha 0.55–1.0 | | **0.50** |
| | | **`StrikethroughLines`** (custom): 1–3 straight lines, 1–2 px | | 0.20 |
| | | `A.CoarseDropout` (2–4 holes, each ≤ 8 % of area, **total ≤ 12 %**) | | 0.15 |
| | | `A.Erasing` (1–2 small patches ≤ 5 %) | | 0.10 |
| 5 | **Photometric** | `A.RandomBrightnessContrast` (±0.25) | | 0.4 |
| | | `A.RandomGamma` (70–140) | | 0.3 |
| | | `A.HueSaturationValue` (h ±10, s ±25, v ±25) | | 0.3 |
| | | `A.ColorJitter` (0.2) | | 0.2 |
| | | `A.ToGray` | | 0.15 |
| | | `A.InvertImg` (polarity flip) | | 0.10 |
| | | `A.CLAHE` / `A.Equalize` | | 0.10 |
| 6 | **Noise** | `A.GaussNoise` (σ 2–25) | | 0.30 |
| | | `A.ISONoise` | | 0.10 |
| | | `A.MultiplicativeNoise` | | 0.15 |
| | | `A.ShotNoise` | | 0.10 |
| | | `A.SaltAndPepper` (amount 0.01–0.05) | | 0.10 |
| 7 | **Blur** | `A.GaussianBlur` (σ 0.3–1.2) | | 0.20 |
| | | `A.Defocus` | | 0.08 |
| | | `A.MotionBlur` | | 0.05 |
| 8 | **Compression — the owner's "сжатие"** | `A.ImageCompression(quality_range=(40, 95))` | | 0.30 |
| | | `A.ImageCompression(quality_range=(15, 40))` — the severe tail | | 0.10 |
| | | **`WebPCompression`** (custom, quality 45–90) | | 0.15 |
| 9 | **To tensor** | deterministic resize to the model input (§4.1) + normalise | | 1.0 |

**Validation and test get stage 9 only.** No augmentation, ever. This is non-negotiable: the whole
point of the type-held-out split is that the validation set measures the real distribution.

### 3.3 Why compression goes last, and what quality range to use

*Why last:* JPEG quantises the DCT coefficients of the **final raster**. A real deployment is
`render → encode → serve → client decodes → client scales → screenshot → re-encode`. If you compress
*before* the geometric warps, the 8×8 blocking artefacts get resampled and the model learns a softer,
wrong artefact distribution. Compressing last reproduces the real chain.

*Quality range — the reasoning:*
* **q 40–95, p 0.30** — the common case. At 130×130, q=40 already produces visible blocking on 1–2 px
  glyph strokes.
* **q 15–40, p 0.10** — the severe tail. q=15 on a 130×130 image destroys thin strokes almost
  entirely. A model trained only on q ≥ 70 will fail on this tail; a model trained *on* it will read
  compressed captchas. The owner explicitly asked for compression robustness because "captchas can be
  large / heavily compressed", so the tail has to be in the training distribution.
* **WebP q 45–90, p 0.15** — modern web stacks (and Minecraft clients behind a CDN) often serve WebP.
  Its artefacts differ from JPEG's, so it is not redundant.
* **Do not go below q 12.** At that point the label is not recoverable and the sample is noise.

*One more real-world axis worth adding later:* **PNG→PNG is a no-op**, but **resize-then-recompress**
(the "screenshot at 2× on a HiDPI display") is exactly stage 3 + stage 8, and it is already covered by
running stage 3 before stage 8. Good.

### 3.4 The occlusion section deserves its own note

A large fraction of these captchas have **thick black curves drawn over the text** — that is what the
`LagBug/XProtect` generators do, and it is the defining difficulty of the family. A model that has never
seen a curve through a glyph will fail on the majority of the dataset. So `InterferenceCurves` at
p=0.50 is the **highest-value augmentation in the list**, and it must be drawn **on top of the text**,
after the geometry, so it lands where the generator's curves land.

The constraint: it must be drawn *on top* (over the ink), not under it, and its thickness and opacity
must span the observed range (1–3 px, alpha 0.55–1.0), including the case where it is the *same*
colour as the text and the glyph is genuinely half-hidden. A curve that fully hides a character makes
the label unrecoverable — hence the opacity floor of 0.55 (partial occlusion) and the cap on count.

### 3.5 The forbidden list — what would destroy the label

This is the part of an augmentation plan that is usually wrong. Every item below is banned, with the
reason:

| Banned | Why |
|---|---|
| `A.HorizontalFlip` | **Reverses the character order.** The label becomes the wrong string. (Unless you reverse the label too — for text you never want this.) **Hard no.** |
| `A.VerticalFlip`, `A.RandomRotate90`, `A.Transpose` | Destroys the glyphs outright. **Hard no.** |
| `A.RandomResizedCrop` (real crop) | Can cut a glyph in half or remove it. Use `A.RandomScale` + `A.PadIfNeeded` instead. **No.** |
| **Character dropout / insertion / substitution** | Changes the label. The metric is exact-match and the *plugin* verifies the exact string (ProstoCaptcha is case-sensitive; AnBot verifies by substring). **Hard no — no text-level augmentation at all.** If you want spacing variation, do it *geometrically* (scale the whole image horizontally by 0.9–1.15), never by re-rendering. |
| **Case jitter** | Same reason — several plugins are case-sensitive, and `LagBug/XProtect`'s own charset is mixed-case. **No.** |
| **`A.Mixup`** | Blends two captchas; the target becomes a meaningless mixture of two strings and the CTC alignment is diluted. **No.** |
| **`A.CutMix`** | Splices a patch from another captcha in; the label is then wrong for a variable fraction of the string. **No.** (If you want the effect, use `CoarseDropout` with a tiny patch — a label-preserving occlusion — which is already in the pipeline.) |
| `A.CoarseDropout` with big holes | A hole that fully covers one character makes the sample unanswerable and teaches hallucination. **Cap total erased area at 12 %.** |
| `A.ElasticTransform` with alpha > 15 or sigma > 5 | Makes `8`/`B`, `0`/`O`, `5`/`S` genuinely ambiguous. This is not a label problem, it is a **target-ambiguity** problem: the model is asked to guess an unidentifiable label, which caps the achievable accuracy and injects gradient noise. This is exactly why `Graf-J` used ElasticTransform as one of only *three* augmentations. |
| `A.GridDistortion` with num_steps > 5 | Warps characters into each other. |
| `A.ImageCompression` at q < 12 | The glyphs are gone. |
| Strong `A.Sharpen` | Halos around 1-px strokes, p ≤ 0.1. |

**One thing that *looks* dangerous but is not:** `A.InvertImg`. The dataset genuinely contains both
white-on-black and black-on-white captchas (XProtect's white background with black lines; sonar's dark
backgrounds), so polarity invariance is a real invariance, not a synthetic one. p = 0.10 is right.

### 3.6 Augmentation ramp

Fixed-strength augmentation from step 0 is the default and what most recipes do. But with 4 600 images
and 46 types, the model first needs to learn the alphabet and the per-type layouts; heavy distortion
from step 0 slows that.

**Recommended (and to be A/B'd as an ablation):**
* epochs 0–5: **no augmentation** except the final resize (the model learns the clean renders first);
* epochs 5–15: every probability above ramps linearly from 0 to its full value;
* epochs 15+: full strength.

Ablation to run: *fixed vs ramped*, on the unseen-style split. It costs 25 minutes on this CPU, so
there is no excuse not to.

---

## 4. Training recipe

### 4.1 Input, geometry and the aspect-ratio problem

> **As built (2026-10-21, later the same day).** The rule below normalises the **frame**; the built
> pipeline normalises the **band**. `train/captcha_crnn.py` crops the image to the `roi` of the sample
> and scales it so the **glyph** is 32 px tall, width by aspect, right-padded. That is the correction
> the review of this plan asked for (B4, B5), and it is the difference between a 2.8-px glyph and a
> 32-px one. Everything else below is as written.

* **Height: 32 px, fixed.** The smallest text bands in the dataset are 15–40 px tall inside 128×128 /
  130×130 frames. H=32 preserves a 30-px glyph at 1:1 and upscales the small ones. H=48 doubles the
  compute (measured: 62 vs 150 img/s) for no expected gain on a 6-character string.
* **Width: aspect-preserving, variable.** `W = round(32 * w / h)`, clamped to **[48, 320]**.
  *Why aspect-preserving:* the frame sizes range from 114×174 to 730×84, and the 250×150 / 150×90
  families have a completely different aspect from 128×128. Squashing everything to a fixed 32×128
  distorts glyph aspect ratios (a `5` becomes wide) and the network learns a scale prior that does not
  transfer.
  *Why left-align + right-pad:* the text is left- or centre-anchored per type; centring the string
  inside a padded field makes the CTC alignment position-dependent. Left-align and right-pad.
* **Padding:** pad to the batch maximum with the **per-image background colour** (the modal/median
  colour of the image), not with 0. A 0-pad after normalisation is an extreme value the network has
  never seen. Then normalise.
* **Padding must not reach the decoder.** Record the true width `w_true` per sample; the CTC
  `input_lengths` = `w_true // 4`, and the decoder truncates the argmax path at that length. This is
  what keeps a padded region from being decoded as characters.
* **Bucketed batch sampler:** sort by width within a shuffled buffer so a batch contains similar
  widths. This removes most padding waste. (Worth 10 lines, and it makes the CPU numbers hold.)
* **Channels: 1 (grayscale).** Every text type in this dataset is effectively ink-on-background, and
  both working community CRNNs use grayscale. Colour is only meaningful for the colour-swatch type,
  which is not OCR. Normalise with mean = 0.5, std = 0.5 → [-1, 1].

### 4.2 Model spec (v1, "CapthaCRNN")

```
input   : (B, 1, 32, W)          W ∈ [48, 320], right-padded
conv1   : 3x3  1 → 32   BN ReLU            stride 1
pool1   : 2x2                                     -> 16 x W/2
conv2   : 3x3 32 → 64   BN ReLU
pool2   : 2x2                                     ->  8 x W/4
conv3   : 3x3 64 → 128  BN ReLU
pool3   : 2x1                                     ->  8 x W/4     (keep the width!)
conv4   : 3x3 128→ 256  BN ReLU
pool4   : 2x1                                     ->  8 x W/4
conv5   : 3x3 256→ 256  BN ReLU
pool5   : 2x1  (height only)                      ->  4 x W/4
reduce  : Conv2d(256, 256, 1x1) + BN + ReLU       ->  4 x W/4  (T = W/4)
reshape : (B, T, 4*256 = 1024)
rnn     : BiLSTM(input 1024, hidden 256, layers 2, dropout 0.15) -> (B, T, 512)
head    : Linear(512 -> |V|)                      |V| = 69 (blank + 68)
```

* **The (2,1) pooling is the important detail.** The classic CRNN pools the width by 4 in one go and
  then by 2, giving `T = W/8`; for W=192 that is T=24, which is barely enough for a 6-character label
  with CTC's blank-separated path (CTC needs `T ≥ 2L+1` to be *able* to represent a label with
  repeats). With `T = W/4 = 48` at W=192 there is comfortable room. **If the label is longer than
  `T/2`, the CTC loss goes to infinity** — hence `zero_infinity=True` plus a hard check that
  `T ≥ 2·L + 1` at data-prep time (assert, don't silently pad).
* The architecture is deliberately the shape of `Graf-J/captcha-crnn-base` (MIT, 3.57 M) — 4 conv
  blocks + BiLSTM — with the pooling fixed as above. Reusing a known-good shape is free; the weights
  are what we train.

### 4.3 Loss and decoding

**Loss: `torch.nn.CTCLoss(blank=0, zero_infinity=True)`.**

**Label smoothing on CTC: do not use it.** The published label-smoothing literature is about
cross-entropy and attention seq2seq, not CTC. CTC's objective is a log-likelihood summed over
alignments; smoothing the emission distribution flattens the blank-vs-character competition that CTC
depends on, and the resulting posteriors get *worse*, not better. (There is a "CTC label smoothing"
trick that adds a constant to the blank logit — that is a different hack and mostly a way to
re-implement label smoothing with extra steps.) If you want extra regularisation, use weight decay +
dropout + EMA. If you want a bigger win, use the **hybrid CTC + attention head** (below).

**Hybrid upgrade (v2, do it if CTC plateaus):** keep the CTC head, add an attention decoder on the
same encoder, loss = 0.7·CTC + 0.3·attention, decode with the attention head only on
low-confidence samples. This is exactly what PP-OCRv6_medium does (CTC+NRTR multi-head), so there is
a strong precedent and a reference implementation to crib the shape from.

**Decoding:**
* **Greedy CTC decode** (default): `argmax` over the time axis → collapse repeats → drop blanks.
  O(T), no hyper-parameters. For random 4-6 character strings this is optimal; beam search with a
  character LM has nothing to exploit and can only hurt by steering toward a more frequent wrong
  string.
* **Prefix beam search** (v2, optional, per-family): worthwhile **only** where the label has lexical
  structure — the Cyrillic model (Russian number words) and possibly the hex/uppercase-only types. Not
  for the Latin model. It also gives the sequence posterior for free, which is a nice confidence
  signal.
* **Per-character confidence — required, and here is how to compute it honestly:**
  1. Softmax the logits over the character classes → posteriors `p[t, c]` for each time step.
  2. Run the greedy path; for each emitted character, collect the frames that collapsed into it.
  3. The character's confidence = the **geometric mean of the posteriors of those frames at the
     chosen class**. (Geometric, not arithmetic: CTC posteriors are multiplicative along a path.)
  4. The **sequence confidence** = the geometric mean of the per-character confidences. Equivalently,
     with prefix beam search, `exp(sum log P(path))`.
  5. **Calibrate it.** CTC posteriors are notoriously overconfident. Fit a single temperature `T` on the
     validation set by minimising NLL, and report the *calibrated* confidence. This is ~15 lines and it
     is what makes the number usable for a human-in-the-loop solver and for the ensemble.
  6. Use it three ways: (a) **abstain** below a threshold (e.g. calibrated 0.75) and escalate to a
     human or to a second model; (b) **ensemble** — pick the candidate with the highest sequence
     posterior; (c) report a **selective-accuracy curve** (accuracy vs confidence threshold), which is
     the single most useful chart for an operator.
  *Comparison:* PP-OCRv6 gives a whole-string `rec_score` (their example: 0.9857) — usable, but
  cruder. `confiacompany`'s **slot-head** design gives exact per-character confidence *for free*
  (each slot is an independent softmax) — a strong argument for the slot model in §1.4.

### 4.4 Validation protocol: hold out whole captcha TYPES

**The protocol:**
* **Primary (headline) number — type-held-out k-fold.** Partition the family-A types into k = 4
  folds. For each fold: train on 3 folds of *types*, validate on the held-out *types*. Every type is
  validated exactly once and trained on in 3 folds. Report the mean ± std of the per-fold
  exact-match and CER. This is the number that goes in the model card as "generalisation to an
  unseen captcha style".
* **Secondary (comparison) number — the in-domain 13-type benchmark.** The existing
  `bench/bench_hf.py` set (13 types × 8 images = 104) with the same metrics, so the new model is
  directly comparable to the published baselines (EasyOCR 0.115 / CER 1.861, `anuashok/ocr-captcha-v3`
  0.077 / 0.785, captCHAD and phpwind 0.000). These types *are* in training, so this number is
  optimistic by construction — say so on the card, and label it "in-domain".
* **Third number — the leaderboard.** Keep a small, frozen, *never-trained-on* set of real upstream
  renders (`dataset/out_ru/*/real_shots/`, the `site/captchas/` catalogue) for a final sanity check
  that the model works on pixels it did not generate. `site/captchas/` has 525 real images from 11
  API-version sections.

**Why hold out whole types — the argument:**

1. **The unit of generalisation that matters is a plugin, not an image.** In production the model
   meets a new anti-bot plugin it has never seen. That is exactly what the type-held-out split
   measures, and it is the number an operator needs.
2. **A random image split measures memorisation here, and measurably so.** The dataset's own README
   records that `XProtect/sneak` produces **8 duplicate images per 100** (the challenge is fixed
   upstream; only the surrounding chat varies), `jump` 5–6, `drop` 2–5. And the per-type answer
   diversity is tiny: `drop` has **4 distinct answers** over 100 samples, `jump` 4, `sneak` 5. A
   random split therefore puts the *same answer string* — and sometimes the *same image* — on both
   sides of the split. The reported accuracy would be dominated by those types and would be
   meaningless.
3. **It produces the per-type breakdown for free**, which is what the owner asked for, and it turns
   the model card into a statement about which plugin families the model can and cannot handle
   ("reads 5/5 of the map captchas, 0/5 of the photo-background ones").
4. **It is the only split that yields an honest number for the card.** A random split's number cannot
   be defended when someone points out that `sneak` leaked.
5. **It is a harder, fairer test than the published baselines got.** Those baselines were evaluated on
   the same 13 types; our in-domain number on the same 13 types is directly comparable, and our
   unseen-style number is a *stricter* claim that nobody else has made.

**The cost, stated honestly:** holding out ¼ of the types costs ¼ of the training data, and the
remaining types are heterogeneous, so the unseen-style number is *pessimistic* relative to a model
that has seen everything. k-folding fixes that (every type is trained on in 3 of 4 folds) and gives a
std. Report it as "accuracy on captcha types not seen in training", with the fold count.

**Do not** use a random split for anything except a quick sanity check during development.

### 4.5 Metrics

| Metric | Definition | Where |
|---|---|---|
| **Exact-match accuracy** | fraction of samples where the normalised prediction == the normalised gold | primary |
| **CER** | mean over samples of `levenshtein(pred, gold) / len(gold)` (the existing `bench_hf.py::score`) | primary |
| **Per-type accuracy + CER** | the same, broken down by captcha type | **required** — this is the per-type breakdown the owner asked for |
| **Per-fold accuracy + CER** | across the 4 type-held-out folds | the generalisation table |
| **Length accuracy** | % of samples where `len(pred) == len(gold)` | early-warning signal; a high CER with 100 % length accuracy means substitution, not insertion/deletion |
| **Per-character confusion matrix** | 68×68, published as a PNG | standard artefact; exposes the 0/O, 1/l, 8/B, 5/S confusions that dominate this domain |
| **Oracle@k** | % of samples where the gold string is in the model's top-k beam candidates (k=5) | tells you whether a beam/LM would help at all |
| **Calibration curve + ECE** | reliability of the confidence score | needed for the HITL solver |
| **Selective accuracy** | accuracy as a function of the confidence threshold | the operator-facing chart |
| **Latency** | ms/image on CPU and on GPU | a solver's real cost |

### 4.6 Small-dataset training tricks

* **Pretrained backbone vs scratch — this is the biggest single lever, and it is not ImageNet.**
  * **Stage 1 (pretrain the CNN):** on a large public *generic captcha* corpus, so the charset
    matches. Candidates, all on the Hub:
    * `hammer888/captcha-data` — 1.37 M images, 13.5 GB of parquet, alphanumeric. This is the corpus
      the `Graf-J` models used.
    * `szili2011/captcha-ocr-dataset` — 1.8 M images, **Apache-2.0**, alphanumeric, built explicitly
      for CRNN+CTC.
    * `AvinashRicky/CaptchaOCR-500K` (MIT), `cybertruck32489/captcha_100k`, `lumasik/captcha-25k` (MIT),
      `Hansda/captcha-dataset` (12 k, 4–7 chars, ambiguous chars excluded), `lukman48/captcha-data`.
    * For the Cyrillic model: `remiai3/synthetic-captchas-library` — 44 scripts × 100 000 images,
      including Russian, **CC BY 4.0**.
    * **Recommendation: start from the `Graf-J/captcha-crnn-base` weights** (MIT, 3.57 M, 96.81 % on
      hammer888) rather than running stage 1 yourself — that is ~100 k images of compute you do not
      have to pay for, and the licence permits it with attribution. Fine-tune the whole thing on
      CaptchaOCR. (If we reuse the weights, attribute Graf-J in the model card; if we re-implement the
      architecture from scratch, we do not need to.)
  * **Why this beats the "scratch" argument:** `Graf-J`'s own two-stage result is the cleanest
    available evidence — the same architecture goes from **9.65 %** on an unseen captcha distribution to
    **86.20 %** after fine-tuning on 200 000 images of that distribution. The architecture barely moved
    (96.81 → 92.98 on the original); the *data* moved the number. Our situation is the same, only
    smaller.
  * **Do not use ImageNet pretraining** as the primary lever. A ViT/ResNet's ImageNet features are
    about natural-image semantics; what we need is "shapes of 1-px-wide glyph strokes under JPEG
    artefacts". A captcha corpus is a far better prior. (A ResNet-18 ImageNet stem as the *initial*
    conv stack is a cheap mild bonus, but it is second-order.)
* **Freezing schedule.** Freeze the CNN for the first 3 epochs (or 15 % of steps), then unfreeze the
  whole thing with a **backbone LR of 0.1× the head LR**. Rationale: the early layers learn generic
  edges regardless of the label distribution, and letting them move early on 4 600 images just adds
  noise. Re-freeze only the very first conv block if the validation is still noisy at epoch 10.
* **Augmentation strength ramp** — see §3.6.
* **EMA of weights.** Keep an exponential moving average (decay 0.999) and evaluate/ship the EMA
  weights. On small datasets this reliably buys 1–3 points and, importantly, **stabilises the CTC
  loss**, which is famously spiky (it jumps when the optimiser finds a long alignment). Report both the
  raw and EMA validation numbers; ship the EMA.
* **Schedule.** Cosine with a 5 % linear warmup, down to 3 % of the peak LR. (Graf-J used
  ReduceLROnPlateau, factor 0.5, patience 3 — fine, but cosine needs no extra state and is easier to
  reason about with a fixed epoch budget.)
* **Type-balanced sampling.** The dataset has 100 images per type but wildly different *answer*
  diversity (4 vs 62 distinct answers per 100). A **type-uniform sampler** (sample a type uniformly,
  then an image within it) prevents `XProtect/drop` (4 answers) and `sneak` (5) from dominating the
  gradient through sheer repetition, while `code`/`map` (62) are not over-represented either. This is a
  ~10-line change and a real win.
* **Checkpoint selection by unseen-style exact-match, not by loss.** CTC loss is a poor proxy for
  exact-match: a model can have a low loss and still get the string wrong. Select on the
  type-held-out metric.
* **Seed everything** and log the dataset manifest hash, the git commit, and the resolved config.
* **Do not use:** Mixup, CutMix, label smoothing, heavy dropout (>0.3), and "training tricks" that
  assume 100 k+ samples.

### 4.7 Hyperparameters (v1)

| Parameter | Value | Note |
|---|---|---|
| input | 1×32×W, W ∈ [48, 320], left-aligned, right-padded with the background colour | bucketed sampler |
| normalisation | mean 0.5, std 0.5 → [-1, 1] | |
| model | §4.2, ≈2.2 M params | |
| vocabulary | 69 (blank + 68) for Model A | 35 for the Cyrillic Model B |
| max label length | 8 (assert `T ≥ 2L+1`) | family A is 3–6 |
| optimiser | **AdamW** | |
| LR | **3e-4** (head) / **3e-5** (backbone, ×0.1) | |
| weight decay | 0.01 | |
| schedule | 5 % linear warmup → cosine to 3e-5 | |
| grad clip | 1.0 (global norm) | CTC gradients spike |
| batch size | **32** on CPU, 64 on GPU | CTC needs a decent batch |
| epochs | 60–100, early stop patience 12 on unseen-style exact-match | |
| EMA | decay 0.999 | |
| freeze | CNN frozen for the first 3 epochs | |
| dropout | 0.15 in the LSTM; 0 in the conv stack (BN regularises) | |
| AMP | bf16 on GPU, off on CPU | |
| dataloader | `num_workers=4` on CPU, 8–12 on GPU; `persistent_workers=True`; `pin_memory` if a GPU appears | augmentation is the bottleneck on GPU |
| folds | 4 type-held-out folds | |
| seed | 42, plus 2 extra seeds for the final model | |

### 4.8 Expected wall-clock

Using the measured numbers from §0.2 (2.02 M params, 32×128, batch 32, 8 threads):

| | per epoch (3 400 training images, family A) | 60 epochs | 4-fold experiment |
|---|---|---|---|
| **CPU only (this machine)** | ~23 s compute + augmentation ≈ **30–45 s** | **30–45 min** | **2–3 h** |
| Consumer GPU (RTX 3060/4060, bf16) | ~2–3 s compute, but **augmentation-bound** at ~30–60 s with 8 workers | 30–60 min | 2–4 h |
| Inference (this CPU) | — | — | **451 img/s** → the full 4 600-image dataset in ~10 s |
| TrOCR-base (CPU) | — | **20–60 h for 3 epochs** | not viable |
| TrOCR-base (consumer GPU) | — | 1–2 h for 3 epochs | viable, if a GPU exists |

**The headline:** on this machine the *entire* experimental programme — 4 folds × 60 epochs plus the
ablations — is **a single afternoon of CPU time**. That is what makes the cheap architecture the right
one: the bottleneck is our data and our validation protocol, not the model.

---

## 5. Publishing to Hugging Face

### 5.1 The exact repository layout

```
captha-crnn/                          # Model A
├── README.md                         # model card (YAML front matter + eval-results)
├── LICENSE                           # MIT
├── .gitattributes
├── config.json                       # model_type, architectures, auto_map, hyper-parameters
├── configuration_captha.py           # CapthaConfig(PretrainedConfig)
├── modeling_captha.py                # CapthaCRNN(PreTrainedModel)
├── processing_captha.py              # CapthaProcessor(ProcessorMixin)  <- self-contained, no sub-processor
├── pipeline.py                       # optional convenience pipeline
├── predict.py                        # CLI: predict.py <image> -> text + confidence
├── captha/                           # a standalone, trust_remote_code-free client package
│   ├── __init__.py
│   └── solver.py                     # ~80 lines: load weights, forward, CTC decode, confidence
├── preprocessor_config.json          # for transformers 4.x users
├── processor_config.json             # for transformers 5.x users  (v5 nested-dict format)
├── vocab.json                        # {"0": "", "1": "0", ...} or a plain list  <- NO tokenizer
├── model.safetensors
├── trainer_state.json
├── training_args.json
├── onnx/
│   ├── model.onnx
│   └── README.md                     # how to run it with onnxruntime
└── train/                            # the reproducible training code
    ├── train.py
    ├── dataset.py
    ├── augment.py
    ├── model.py
    ├── evaluate.py
    └── requirements.txt
```

A second repo (or a second folder in the same repo) for the **Cyrillic** Model B, and a **dataset
repo** per licence family (§5.5).

### 5.2 `config.json` and the AutoClass mapping

```json
{
  "model_type": "captha_crnn",
  "architectures": ["CapthaCRNN"],
  "auto_map": {
    "AutoConfig":     "configuration_captha.CapthaConfig",
    "AutoModel":      "modeling_captha.CapthaCRNN",
    "AutoProcessor":  "processing_captha.CapthaProcessor"
  },
  "vocab_size": 69,
  "blank_index": 0,
  "image_height": 32,
  "image_width": 192,
  "max_label_length": 8,
  "width_downsample": 4,
  "initializer_range": 0.02
}
```

**Should we also map `AutoModelForImageTextToText`?**
* *For:* it is the v5-recommended entry point and would make
  `pipeline("image-text-to-text", model=..., trust_remote_code=True)` work.
* *Against:* v5 **removed** the `image-to-text` pipeline and `AutoModelForVision2Seq`, and the
  `image-text-to-text` pipeline no longer accepts an image as a separate argument (the image must be
  inside the chat `content` list) — which is awkward for a pure recogniser that takes no prompt. Worse,
  v5 states that "configurations of non-generative models (any model that doesn't call `model.generate()`)
  will no longer have a `generation_config`", so mapping a CTC model onto a generative auto class
  invites mismatches.
* **Recommendation: map `AutoConfig` + `AutoModel` + `AutoProcessor` as the primary path**, and
  **add `AutoModelForImageTextToText` as an alias to the same class only if** a smoke test confirms
  v5's pipeline accepts it. The model card's headline snippet is the `AutoModel`/`AutoProcessor` path,
  which is the one that works identically on 4.57 and 5.x:

```python
from transformers import AutoModel, AutoProcessor
from PIL import Image

processor = AutoProcessor.from_pretrained("<owner>/captha-crnn", trust_remote_code=True)
model = AutoModel.from_pretrained("<owner>/captha-crnn", trust_remote_code=True).eval()

img = Image.open("captcha.png").convert("RGB")
out = model(processor(img)["pixel_values"])
text, confidence = processor.batch_decode(out.logits, return_confidence=True)[0]
print(text, confidence)
```

  (This is the same shape the `Graf-J` card documents, and it is the shape that survives the v5
  processor refactor — which is exactly what those models *don't* survive.)

### 5.3 The processor: the one decision that fixes the v5 load failures

**Rule: one self-contained `ProcessorMixin` subclass that does the resize and the normalise itself,
with no `image_processor` attribute and no separate feature-extractor class.**

Why this matters, concretely: in transformers v5, PR #41633 **"Refactor subprocessors handling in
processors"** changed how processor attributes are serialised — everything now goes into a single
`processor_config.json` as a nested dict, and `special_tokens_map.json` / `added_tokens.json` are no
longer written. The `hongyusir/trocr-base-printed_captcha_ocr` and `DunnBC22/...` models fail with
**"Processor was loaded, but it is not an instance of ProcessorMixin"** precisely because their
processor predates that refactor and the v5 loader rejects it *before it ever reaches the weights*.
A processor with a sub-processor is exactly the thing that refactor targets. **A processor with no
sub-processor is not.**

Therefore, ship:
* `processor_config.json` — the v5 format, with the attributes nested under the processor's own key;
* `preprocessor_config.json` — the legacy format, so transformers 4.57 users also work;
* the class itself carries the defaults, so a fresh `save_pretrained` on any version round-trips.

Other v5-specific requirements for the custom code:
* **Override `_init_weights`.** v5 now auto-initialises every `nn.Linear` / `nn.Conv2d` with
  `config.initializer_range` (0.02) unless you override it. For a CRNN, Kaiming/normal for convs and
  Xavier for the LSTM is materially better. The migration guide gives the exact override pattern.
* **No `torchscript` / `torch.fx`** — both were dropped in v5.
* **`from_pretrained` now defaults to `dtype="auto"`** — harmless, but be aware `save_pretrained`
  stores the dtype you trained in.
* `apply_chat_template` now returns a `BatchEncoding`; `batch_decode` on a *tokenizer* was unified
  into `decode` (a `ProcessorMixin.batch_decode` is unaffected — our processor defines its own).
* `PreTrainedConfig` subclasses must accept `**kwargs` and pass them to `super().__init__(**kwargs)`.
* `model_type` must be unique across the library; `captha_crnn` is free.

### 5.4 ONNX export — and the `optimum` trap

**The `optimum` route described in the brief is not available with transformers 5.x.** Verified on
this machine and on PyPI:

* `import transformers.onnx` → **ModuleNotFoundError**. The whole `transformers.onnx` package
  (`export`, `FeaturesManager`, `utils.onnx`) was **removed in v5**. (v5.20.0's release notes do
  mention "Transformers exporters now support quantization directly during export across Dynamo, ONNX,
  OpenVINO, and ExecuTorch" — that is the `optimum` exporter path, not `transformers.onnx`.)
* `optimum-onnx` on PyPI is at **0.1.0** and declares `transformers<4.58.0,>=4.36` — it **cannot be
  installed alongside transformers 5.x** without downgrading the whole stack.
* `optimum` itself is at 2.3.0 and declares only `transformers>=4.29` (no upper bound), but its ONNX
  exporter support for a *custom* `trust_remote_code` model is unproven here.

**Recommendation: export with `torch.onnx.export` directly** (torch 2.14 supports the dynamo
exporter). Concretely:
* wrap the model in a thin `nn.Module` that returns `(logits,)` and takes `(pixel_values,
  input_lengths)`;
* dynamic axes on `batch` and `width`; **keep the width dynamic** so aspect-preserving inputs work,
  and pass the true width as `input_lengths` so the decoder can mask the padding;
* publish `onnx/model.onnx` + `vocab.json` + a 20-line `decode_ctc()` helper in the repo;
* add `onnxscript==0.7.2` to the requirements for the dynamo exporter.

**Yes, publish the ONNX.** It is the only form of this model that runs **without `trust_remote_code`,
without torch, and on any runtime with onnxruntime** — and the project already has an ONNX benchmark
harness, so it plugs straight into `bench/bench_onnx.py`. That also gives the model a second, entirely
independent verification path.

**And ship a `trust_remote_code`-free client.** `trust_remote_code=True` is a security prompt; many
organisations ban it. Publishing a small `captha/` package inside the repo (a pure-torch
implementation of the forward pass + CTC decode + confidence, ~80 lines, pulling `model.safetensors`
and `vocab.json` from the same Hub repo) means the model is usable in locked-down environments. This
is a small amount of code with a disproportionate reach.

### 5.5 Licensing — the dataset is the delicate part, not the weights

**Weights and code: MIT.** MIT is the most widely accepted permissive licence for this kind of
artefact and matches the closest prior work (`Graf-J/*`, `confiacompany/*`). Include a one-line
attribution if the `Graf-J` weights or architecture are reused.

**Dataset: do NOT publish one monolithic dataset.** The generators are a mix of *faithful*
reimplementations (upstream licence permits), *clean-room* rewrites, and *reconstructions*, and the
upstream licences are not uniform:

| Upstream | Licence | Consequence for a published render |
|---|---|---|
| `LagBug/XProtect`, `FeelingAlive0/AdvancedCaptcha`, `jSdCool/minecaptcha` (CC0-1.0), `laforetbrut/are-you-sure`, `InstantlyMoist`, `JSH32/Minecaptcha`, `haq/mapcha`, `just-captcha/ProstoCaptcha`, `Z4OLLIEZ4/reCaptcha`, `Joey61021/captcha`, `Mrbysco/Captcha`, `n1zamu/NCaptcha` | MIT / CC0 | permissive → publish freely with attribution |
| `jonesdevelopment/sonar`, `China2B2T/Captcha`, `irootdev/AnBot` | **GPL-3.0** | a derivative dataset must be **GPL-3.0** → publish in a **separate repo with a GPL-3.0 card** |
| `Archy-X/Krypton`, `Yukun99/Captchas` | **no licence** | the project already clean-rooms these; publish the render under a licence the project chooses, and say plainly that the upstream had none |
| `ringoame196-s-mcPlugin/ReproductionCAPTCHA` | **no licence file** | same |
| `Supl1n/CaptchaGUI` (`CaptchaGUI/clickblock`) | **no licence file** | same — the upstream ships no LICENSE file at all |
| `Elytrium/LimboFilter` (`LimboFilter/*`) | **AGPL-3.0** | the strongest copyleft in the set. The generator is a clean-room rewrite, so the renders are the project's own work, but the upstream's terms should be named in the card |
| `Leymooo/BungeeCord` (`BotFilter/map`) | **BSD 2-clause + a non-commercial hosting clause** | the generator is clean-room, so the render is the project's own work; name the upstream's terms in the card |
| `mateita254` / `CaptchaVerifyZ` (`CaptchaVerifyZ/map`) | **all rights reserved** (`LicenseRef-All-Rights-Reserved`) | the generator is clean-room, so the render is the project's own work; name the upstream's terms in the card |
| `GalleryCaptcha/*` (reconstructions from `site/captchas/`) | n/a (reconstructed) | publish as the project's own work, with the reconstruction note |

> **Corrected (2026-10-21, later the same day).** `irootdev/AnBot` was in the MIT/CC0 row; it is
> **GPL-3.0** — the upstream `LICENSE` file says so, and `README.md` has said so all along. That is
> **B6** in `docs/adr/0002-recogniser-architecture-and-data.md`, whose other half is the omission of `Joey61021/captcha`,
> `Mrbysco/Captcha` and `n1zamu/NCaptcha` from the permissive row. The three `dataset/out_ru/` plugins
> the table did not mention at all are added above with the licences recorded in
> `reports/SITE_CAPTCHAS.md` §7.1, §7.3 and §7.5. **B7** — whether the upstream GPL reaches the rendered
> *images* at all, and whether the "one repo per licence family" split is needed — is **still open**
> and is not decided here.

**Recommendation:** publish the dataset as **one repo per licence family** (or one repo per plugin
group), each with:
* a `README.md` carrying the `dataset_info` YAML — `license:`, `task_categories: ["image-to-text"]`,
  `language: ["en"]` / `["ru"]`, `size_categories`, `modality: ["image", "text"]`, `format:
  imagefolder` or `parquet`;
* the **per-row provenance** the project already maintains — `plugin`, `captcha`, `answer`, `text`,
  `prompt`, `roi`, `width`, `height`, `source` (the upstream `file#method`) — exported as a
  `metadata.jsonl` beside the images, so the audit trail survives publication;
* a `mode:` field (faithful / clean-room / reconstructed) and the upstream licence, per type;
* the `sites/captchas` real-shot images **kept out** of the training split and released separately
  with their own note (they are scraped reference material, and the project treats them as ground
  truth for the reconstructions).

**Tags for the dataset repos:** `minecraft`, `captcha`, `ocr`, `image-to-text`, `synthetic`,
`dataset`, plus the language tag.

**Intended use / ethics — write it into the card, do not skip it.** A public "solves Minecraft plugin
captchas" model is dual-use. The legitimate framings are: operating your own server's anti-bot
plugin, authorised security testing, and accessibility tooling. The card should state the intended
use, state that the model is **not** a general-purpose captcha bypass, and list the limitations.
`CaptchaKraken` is the precedent: a source-available licence with an explicit "you may not sell the
solve / may not expose it through a paid or public captcha-solving API" clause. Whether to add an
equivalent clause to a permissive MIT release is **the owner's call**, not ours — flag it and let them
decide. If they want the CaptchaKraken-style protection, use a custom licence; if they want maximum
adoption, MIT plus a clear intended-use section.

### 5.6 Model card metadata

```yaml
---
license: mit
library_name: transformers
pipeline_tag: image-text-to-text
tags:
  - ocr
  - captcha
  - minecraft
  - image-to-text
  - ctc
  - crnn
  - text-recognition
  - pytorch
  - safetensors
language:
  - en
model-index:
  - name: CapthaCRNN
    results:
      - task: image-to-text
        type: image-to-text
        dataset: <owner>/captha-model-dataset-latin
        metrics:
          - type: accuracy        # exact match
            value: <x>
            name: exact_match_unseen_type
          - type: cer
            value: <y>
            name: cer_unseen_type
model-index / eval-results:
  - type: image-to-text
    name: CapthaCRNN
    dataset:
      name: CaptchaOCR (type-held-out, 4 folds)
      type: <owner>/captha-model-dataset-latin
    metrics:
      - type: accuracy
        value: <x>
        name: exact_match
      - type: cer
        value: <y>
        name: cer
---
```

Include in the body: the per-type accuracy table, the confusion matrix, the selective-accuracy curve,
the calibration plot, the CPU/GPU latency, the exact `transformers` version tested, the training
command, the dataset provenance table, and the intended-use / limitation sections.

### 5.7 The transformers 5.x compatibility problem — what exactly changed

This is the problem the project already hit, so it deserves a precise answer rather than a
"just pin an older version".

**What v5 actually did (v5.0.0 shipped 2026-01-26; the project now ships weekly minors — v5.20.2 on
2026-10-19):**

1. **`transformers.onnx` was removed** (verified locally). `transformers.onnx.export` and
   `FeaturesManager` are gone. → §5.4.
2. **`AutoModelForVision2Seq` removed** → `AutoModelForImageTextToText`.
3. **The `image-to-text` and `visual-question-answering` pipelines were removed**, and
   `image-text-to-text` no longer accepts an image as a separate argument (it must be inside the chat
   `content` list). **This is the cause of the "You must provide text for this pipeline." error in
   `reports/CAPTCHA_OCR_REPORT.md` §3** — the v5 `image-text-to-text` pipeline is a *chat* pipeline.
   → For a recogniser, **do not use a pipeline**; call the model directly.
4. **`pipeline("text2text")` removed** (it was a thin wrapper over a chat model).
5. **Processor refactor (PR #41633):** processor attributes are serialised under a single
   `processor_config.json` as a nested dict; `special_tokens_map.json` and `added_tokens.json` are no
   longer written; `use_fast` → `backend` for image processors; `FooImageProcessor` is now the
   *torchvision* backend and `FooImageProcessorPil` the PIL one. **→ This is the direct cause of
   "Processor was loaded, but it is not an instance of ProcessorMixin" for
   `hongyusir/trocr-base-printed_captcha_ocr` and `DunnBC22/...`.** Their repos ship a pre-v5-style
   processor; the v5 loader rejects it before touching the weights.
   *Fix for those two models:* re-save the processor with a v5 `transformers`
   (`TrOCRProcessor.from_pretrained(...).save_pretrained(dir)`), or hand-roll the resize
   (they are just a resize + normalise) and use `VisionEncoderDecoderModel` directly.
6. **Weight-loading rewrite:** dynamic weight loading with `WeightConverter`; `SubConfigSpec`
   centralises nested-config initialisation, so custom configs may need updating; the default
   `from_pretrained` dtype is now `"auto"`.
7. **`safe_serialization=False` removed**; `torchscript` and `torch.fx` support dropped.
8. **Tokenisation:** `batch_decode` → `decode`; `encode_plus` → `__call__`; `as_target_tokenizer`
   removed; `apply_chat_template` returns a `BatchEncoding`.
9. **`huggingface_hub>=1.0.0` required**; the HTTP backend moved from `requests` to `httpx`;
   `hf_transfer` is dropped in favour of `hf_xet`. `TRANSFORMERS_CACHE` / `PYTORCH_PRETFORMED_MODEL_CACHE`
   env vars removed → use `HF_HOME`.
10. **Trainer:** `tokenizer` → `processing_class`; `warmup_ratio` → `warmup_step`; `no_cuda` →
    `use_cpu`; `per_gpu_train_batch_size` → `per_device_train_batch_size`;
    `use_legacy_prediction_loop` removed; `use_cache` defaults to `False`.
11. **TF and JAX are gone** from the library entirely.
12. **AutoModelWithLMHead removed**; `AutoModelForVision2Seq` removed; "any-to-any pipeline and
    auto-mapping" added (PR #40884).

**Why the `Graf-J` models fail to load:** their `configuration_captcha.py` / `processing_captcha.py`
pre-date v5's config and processor handling, and v5's `auto_map` resolution plus the new
`SubConfigSpec` config machinery rejects the old-style custom config. The model code itself is
~50 lines and is fine. **Fix: re-save the config and processor with a v5 `transformers`, or
re-implement the architecture** (which is what this plan does anyway) — *not* "the weights are bad".

**Why `keras-io/ocr-for-captcha` fails:** `from_pretrained_keras` was removed from `huggingface_hub`
(this is a `huggingface_hub` change, not a `transformers` one). The model is a Keras/TF model and can
never be a `transformers` model — TF was also removed from transformers in v5. Load the `.h5`
directly with `tf-keras` if you want it in the comparison table; otherwise skip it.

**Why `04RR/Florence-base-Captcha` fails:** `Florence2LanguageConfig` without `forced_bos_token_id` —
v5 validates configs strictly. Fix: start from `microsoft/Florence-2-base` and fine-tune it yourself
(which is more honest than using a broken fine-tune anyway), or pin transformers 4.x.

**Version policy:**
* **Pin exactly.** v5 now ships **weekly minor releases** (v5.0.0 on 2026-01-26 → v5.20.2 on
  2026-10-19). A floating `transformers>=5` in `requirements.txt` will break the model within weeks.
  Pin **`transformers==5.20.2`** (the version used for the published run) in `requirements.txt` and
  state the tested version on the model card.
* **Should `transformers>=5` support be a goal? Yes — and it is reachable.** A custom
  `PreTrainedModel` + a **sub-processor-free** `ProcessorMixin`, with an explicit `_init_weights`
  override and no `torchscript`/`torch.fx`, is forward-compatible with v5 and backward-compatible with
  4.57. Publish `requirements.txt` (`transformers>=4.57`) and `requirements-v5.txt`
  (`transformers==5.20.2`), and add a CI job that installs 4.57 and runs a 5-image smoke test. That
  covers the widest possible audience without asking anyone to trust a floating dependency.
* **The compatibility checklist for our own code** (each of these is a v4/v5 difference we must not
  trip over): no `special_tokens_map.json`; ship `processor_config.json`; no sub-processor; override
  `_init_weights`; no `torchscript`/`torch.fx`; `PreTrainedConfig.__init__(**kwargs)` →
  `super().__init__(**kwargs)`; unique `model_type`; `auto_map` with `AutoConfig`/`AutoModel`/
  `AutoProcessor`; `processor.batch_decode` (not `tokenizer.batch_decode`).

### 5.8 Reproducibility

* `train/train.py` with a single command; `train/requirements.txt` with **exact pins** (below).
* Ship the **dataset manifest**: the list of files with SHA-256, the generator git commit, and the
  `labels.jsonl` contents, so the run can be reconstructed exactly.
* Ship the seed, the resolved `config.json`, `trainer_state.json`, and the `bench/` harness.
* Log the environment: `python -V`, `torch.__version__`, `transformers.__version__`, and
  `torch.cuda.get_device_name()`.
* Add a `model-index` / `eval-results` block with the type-held-out numbers, so the Hub renders the
  result table.

**Pinned requirements (measured against this environment):**

```
# runtime for training
torch==2.14.1
torchvision==0.29.1
transformers==5.20.2          # or 5.19.0, the version installed here; pin exactly
tokenizers==0.23.2
huggingface_hub==1.33.0
safetensors==0.8.0
accelerate==1.15.0
albumentations==2.0.8         # NOT installed yet; deps already satisfiable
opencv-python-headless==5.0.0.93
numpy==2.4.6
scipy==1.18.1
Pillow==12.2.0

# optional
datasets==5.1.0               # only to build/publish the Hub dataset
evaluate==0.4.6               # only if we use `evaluate`
onnxruntime==1.30.0           # for the ONNX benchmark
onnxscript==0.7.2             # for torch.onnx.export(dynamo=True)
```

Deliberately **absent**: `optimum` / `optimum-onnx` (the ONNX route is incompatible with
transformers 5.x — §5.4), `peft` (not needed for a from-scratch CRNN), `timm` (not needed),
`paddleocr` (not needed; PP-OCRv6 is evaluated via ONNX).

**To install on this machine:**
```powershell
pip install albumentations==2.0.8 onnxscript==0.7.2
# optional
pip install datasets==5.1.0 evaluate==0.4.6
```

---

## 6. Work plan

| # | Step | Size | Depends on |
|---|---|---|---|
| **M0** | **Add PP-OCRv6_medium_rec_onnx to `bench/bench_onnx.py`** (download `inference.onnx` + `inference.yml`, read the char dict, CTC-decode, score with the existing `score()`). Also add `Graf-J/captcha-crnn-base` with a v5-compatible processor re-save, so the two strongest known models are on the same table. | ~60 lines, ~1 h | — |
| **M1** | Write `train/augment.py` (the pipeline in §3.2) + a **visual audit**: render 200 augmented samples into a contact sheet (`dataset/out/index.html` style) and *look at them*. An augmentation you cannot see is an augmentation you cannot trust. | ~300 lines, 1 day | — |
| **M2** | Write `train/dataset.py` (type-held-out k-fold splitter, bucketed sampler, type-uniform sampler, CTC target encoding) + `train/model.py` (the §4.2 CRNN). | ~250 lines, 1 day | M1 |
| **M3** | Write `train/train.py` + `train/evaluate.py` (exact-match, CER, per-type, confusion matrix, confidence + calibration, selective accuracy). | ~300 lines, 1 day | M2 |
| **M4** | **Run the 4-fold experiment** on CPU (~2–3 h). Expect: in-domain exact-match > 0.9, unseen-style exact-match > 0.6. | 3 h | M3 |
| **M5** | Ablations (each ~30 min on CPU): augmentation ramp on/off · elastic on/off · compression on/off · H=32 vs 48 · CTC vs CTC+attention head · type-uniform sampling on/off. | 3 h | M4 |
| **M6** | **v2 candidates**, in order of expected value: (a) stage-1 pretraining on a public captcha corpus if the unseen-style number is below 0.7; (b) the **slot-head model** for the fixed-length types (§1.4); (c) the Cyrillic Model B on `ru-symbols` + `remiai3` Russian; (d) the hybrid CTC+attention head. | | M5 |
| **M7** | Publish: model repo (custom code + ONNX + `captha/` client), dataset repos per licence family, model card with the eval-results block. | 2–3 days | M5/M6 |
| **M8** | (Optional, second paper) The VLM arm for family C: the **framed** captcha (`LimboFilter/framed2x2` / `framed3x3`), where the answer lies in turned frames, is the hardest 200-image target in the whole dataset. | | M7 |

> **Status of the work plan (2026-10-21, later the same day).** **M2 and M3 are done**: the training
> code is `train/captcha_crnn.py` (charset, dataset, model, CTC decoding) and `train/train.py` (the
> training loop, the evaluation and the checkpointing), with `train/README.md`. The augmentation is
> implemented in the dataset class rather than in a separate `augment.py` (JPEG q15-95, WebP q45-90,
> brightness, contrast, applied to the finished raster). The model is **4 623 615 parameters**,
> **63 classes**, and it runs at **920 img/s on the 1080 Ti**. The measured results are in
> `HANDOVER.md` §6.5. M0, M1's visual audit, M4, M5, M6 and M7 are still open.

**The first week, concretely:** M0 + M1 + M2. M0 because it changes what "beating the baseline"
means; M1 because augmentation is the owner's explicit priority and the contact sheet is the only way
to trust it; M2 because everything else depends on the data pipeline.

---

## 7. Sources

**Primary sources used for the claims above**

* PP-OCRv6 — arXiv 2606.13108 (11 Jun 2026), <https://arxiv.org/abs/2606.13108> ·
  model card <https://huggingface.co/PaddlePaddle/PP-OCRv6_medium_rec> ·
  ONNX <https://huggingface.co/PaddlePaddle/PP-OCRv6_medium_rec_onnx> ·
  `PP-OCRv6_medium_det` · `PP-OCRv6_small_det_onnx`
* PaddleOCR-VL — arXiv 2510.14528 · <https://huggingface.co/PaddlePaddle/PaddleOCR-VL>
* Baidu Unlimited-OCR — arXiv 2606.23050 (added in transformers v5.20.0)
* transformers v5 migration guide — <https://github.com/huggingface/transformers/blob/main/MIGRATION_GUIDE_V5.md>
  · v5.0.0 release notes (2026-01-26) · v5.20.0 / v5.20.1 / v5.20.2 release notes ·
  PR #41633 (processor subprocessors) · PR #40884 (any-to-any pipeline and auto-mapping)
* transformers custom-model guide — <https://github.com/huggingface/transformers/blob/main/docs/source/en/custom_models.md>
* `Graf-J/captcha-crnn-base` and `Graf-J/captcha-conv-transformer-finetuned` (MIT) — model cards and
  `modeling_captcha.py` / `processing_captcha.py`, and their two-stage training recipe
* `confiacompany/confia-captcha-ocr-pt` (MIT) — slot-head CNN model card
* `anuashok/ocr-captcha-v3` (Apache-2.0) — model card, claimed CER 0.0139 and training hyper-parameters
* `arkhabbazan/ocr-digits-captcha`, `arkhabbazan/ocr-captcha-router`, `arkhabbazan/ocr-math-captcha` (2026)
* `CaptchaKraken/CaptchaKraken-v1.2-GGUF` — model card (source-available licence v1.1, eval table)
* `ATH-MaaS/CaptchaMind-7B` + `ATH-MaaS/Captcha` (CC BY-NC 4.0)
* PARSeq — ECCV 2022, <https://github.com/baudm/parseq> (Apache-2.0); the `awesome-ocr-2026`
  reference for the modern STR landscape; the 2026 STR survey (*Pattern Recognition*, 2026)
* Albumentations 2.0.8 — <https://albumentations.ai/docs/> and the PyPI metadata (deps verified
  against this environment)
* PyPI metadata for `optimum` 2.3.0, `optimum-onnx` 0.1.0 (`transformers<4.58.0,>=4.36`),
  `onnxscript` 0.7.2, `datasets` 5.1.0, `evaluate` 0.4.6
* Public captcha corpora on the Hub: `hammer888/captcha-data` (1.37 M), `szili2011/captcha-ocr-dataset`
  (1.8 M, Apache-2.0), `AvinashRicky/CaptchaOCR-500K`, `Hansda/captcha-dataset`,
  `remiai3/synthetic-captchas-library` (44 scripts × 100 k, CC BY 4.0),
  `inclusionAI/VenusBench-CAPTCHA`, `ZHEN-04/CaptchaArena`, `OpenCaptchaWorld/Open_CaptchaWorld`,
  `Knight07/Deep_Captcha`, `FlanChanXwO/phpwind-captcha-dataset`
* In-repo: `AGENTS.md`, `README.md`, `reports/CAPTCHA_OCR_REPORT.md` §0 (the measured baselines),
  `bench/bench_hf.py`, `bench/bench_onnx.py`, and the generator sources
  (`dataset/generator_ru/dev/captcha/gens/RussianCaptcha.java`, `ObjectCaptcha.java`)
* Measured on this machine: the dataset label census (§0.3), the CPU throughput benchmark (§0.2),
  the `transformers.onnx` import check (§5.4), and the installed-package list (§0.2)

**Not found, and worth saying so:** no Minecraft anti-bot-plugin captcha model and no `CaptchaOCR`
dataset exists on the Hugging Face Hub. *The evidence for that claim was corrected by the review of
this plan* (`docs/adr/0002-recogniser-architecture-and-data.md`, B8): it is not true that "both API queries return empty" -
`api/models?search=captcha` returns 100+ rows and `api/models?search=minecraft` returns 100+ rows
(none of them captcha models); what is empty is `api/models?search=minecraft captcha` and
`api/datasets?search=captha`. The **niche** this project occupies is unoccupied; the **query** is not.
The closest existing work is `Graf-J/captcha-*` (generic web captchas, hammer888 corpus),
`confiacompany/confia-captcha-ocr-pt` (fixed 5-char web captchas) and `CaptchaKraken/*` (commercial
web puzzle captchas).
