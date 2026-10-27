# Training report — PP-OCRv6 fine-tune including `out_ru/LimboFilter/digits`

- **Date / window:** 2026-10-26, three runs 16:00–19:00 (Asia/Yekaterinburg), GTX 1080 Ti (11.8 GB, sm_61), torch 2.14.1+cu126, transformers 5.19.0
- **Part 1 (flint subagent, obsolete):** the first session crashed with the named-pipe sandbox denial (§3) and never trained; its verbatim crash log is preserved in `reports/archive/2026-10-27-cleanup/TRAINING_LIMBO_DIGITS_crashlog.md`.
- **Part 2 (final numbers):** runs `limbo_digits` and `limbo_digits3` by the orchestrator with `--workers 0` (the sandbox workaround).

## 0. What was achieved (the short version)

| run | recipe | digits | held-out median | micro |
|---|---|---|---|---|
| `all20` (baseline, 24 Oct) | soup weights, 20 types | — | 0.9100 | 0.7517 |
| `limbo_digits` (run 1) | from `all20/soup_best.pt`, all types **+ digits**, lr 5e-6, 2 ep | 0.500 | 0.9218 | 0.8489 |
| `limbo_digits2` (run 2, **discarded**) | digits only, lr 8e-6 | — | **0.0039** — catastrophic forgetting; its `best.pt` deleted | |
| `limbo_digits3` (run 3, **final**) | from run-1 best, all types again, lr 8e-6, 2 ep | **0.795** | **0.9255** | 0.8269 |

Full 16-type eval of run 3 (`limbo_digits3_eval/zero_step.json`, 500/type, one pipeline, `--zero-step`):

| type | all20 | run3 | Δ |
|---|---|---|---|
| out/Archy-X/Krypton/map | 0.980 | **1.000** | +0.020 |
| out/InstantlyMoist/Captcha/textcaptcha | 0.240 | 0.238 | = |
| out/JSH32/Minecaptcha/map | 0.930 | 0.934 | = |
| out/LagBug/XProtect/code | 0.095 | 0.028 | −0.067 |
| out/LagBug/XProtect/map | 0.065 | 0.036 | −0.029 |
| out/haq/mapcha/map | 0.930 | **0.972** | +0.042 |
| out/irootdev/AnBot/captcha | 0.995 | 0.990 | = |
| out/jonesdevelopment/sonar/complex | 0.835 | 0.660 | −0.175 |
| out/jonesdevelopment/sonar/legacy | 0.800 | 0.804 | = |
| out/jonesdevelopment/sonar/standard | 0.805 | 0.640 | −0.165 |
| out/just-captcha/ProstoCaptcha/map | 0.770 | **0.948** | +0.178 |
| out/ringoame196-s-mcPlugin/ReproductionCAPTCHA/map | 0.985 | 0.996 | = |
| out_ru/BotFilter/map | 0.935 | 0.936 | = |
| out_ru/CaptchaVerifyZ/map | 1.000 | 0.998 | = |
| out_ru/GalleryCaptcha/ru-web | 0.910 | **0.962** | +0.052 |
| **out_ru/LimboFilter/digits (new)** | — | **0.795** | new |

**All-16 aggregate: median 0.9350 (was 0.9100), micro 0.7442, CER median 0.0156.**

- `digits` (the new real-server style: 4 digits, custom TTF, photo backplate, 5 curves) went **0.500 → 0.795** exact (CER 0.055).
- Median over types grew; the big winners are ProstoCaptcha (+17.8 pp) and haq (+4.2 pp).
- The honest cost: sonar complex/standard dropped ~17 pp each (frame-trained types; run 1 already showed the drift at 0.653/0.730 — it started with the first fine-tune, not with run 3).
- WiSE-FT sweep on run 3 (α ∈ {0, 0.25, 0.4, 0.5, 0.6, 0.75, 1}, 500/type): **best α = 1.0** (median 0.869 on the 6 default held-out types) — no base anchor needed this time; `limbo_digits3/soup_best.pt` written.
- Caveat carried over from `all20`: per-type numbers for *types the model trains on* are sample-level hold-out numbers (first 200 per type held out of training), not unseen-plugin numbers. The 5 Cyrillic types stay outside the model dictionary (dropped, listed in every log).
- The owner's real screenshots (`test/image1-6.png`, the pattern-mode 4-digit style) match this model's training class; a dedicated scoring of those 6 images is **not** part of this report (no gold labels on file — they are owner-supplied).

## 1. The commands (exact, one line each)

```
# run 1 (mixed, from the published soup)
.venv-gpu\Scripts\python.exe train\finetune_ppocr.py --out train\runs\ppocrv6\limbo_digits --init-from train\runs\ppocrv6\all20\soup_best.pt --epochs 2 --batch-size 32 --lr 5e-6 --head-lr 5e-6 --workers 0 --limit-per-type 2000 --holdout-per-type 200 --eval-every 1 --save-every 400 --max-minutes 50

# run 2 (digits-only - DISCARDED, kept only as the forgetting exhibit)
.venv-gpu\Scripts\python.exe train\finetune_ppocr.py --out train\runs\ppocrv6\limbo_digits2 --init-from train\runs\ppocrv6\limbo_digits\best.pt --epochs 3 --batch-size 32 --lr 8e-6 --head-lr 8e-6 --workers 0 --include-types "LimboFilter/digits" --limit-per-type 10000 --holdout-per-type 200 --eval-every 1 --save-every 400 --max-minutes 40

# run 3 (mixed again, from run-1 best)
.venv-gpu\Scripts\python.exe train\finetune_ppocr.py --out train\runs\ppocrv6\limbo_digits3 --init-from train\runs\ppocrv6\limbo_digits\best.pt --epochs 2 --batch-size 32 --lr 8e-6 --head-lr 8e-6 --workers 0 --limit-per-type 3000 --holdout-per-type 200 --eval-every 2 --save-every 400 --max-minutes 45

# WiSE-FT sweep on run 3
.venv-gpu\Scripts\python.exe train\soup_eval.py --run-dir train\runs\ppocrv6\limbo_digits3 --workers 0 --limit-per-type 500

# full 16-type eval of run 3 (zero-step; 15 types in --val-types so train stays non-empty)
.venv-gpu\Scripts\python.exe train\finetune_ppocr.py --out train\runs\ppocrv6\limbo_digits3_eval --init-from train\runs\ppocrv6\limbo_digits3\best.pt --zero-step --workers 0 --limit-per-type 500 --max-minutes 30 --holdout-per-type 200 --val-types out/InstantlyMoist/Captcha/textcaptcha out/JSH32/Minecaptcha/map out/LagBug/XProtect/code out/LagBug/XProtect/map out/haq/mapcha/map out/irootdev/AnBot/captcha out/jonesdevelopment/sonar/complex out/jonesdevelopment/sonar/legacy out/jonesdevelopment/sonar/standard out/just-captcha/ProstoCaptcha/map out/ringoame196-s-mcPlugin/ReproductionCAPTCHA/map out_ru/BotFilter/map out_ru/CaptchaVerifyZ/map out_ru/GalleryCaptcha/ru-web out/Archy-X/Krypton/map
```

## 2. Wall-clock

- run 1: 22.03 min (98–102 img/s); run 2: 2 wasted epochs, killed (the exhibit); run 3: 22.02 min (128 img/s); soup sweep: ~14 min; 16-type eval: ~7 min.

## 3. The named-pipe sandbox denial (why `--workers 0`)

Both the subagent and the orchestrator session cannot create multiprocessing named pipes:

```
PermissionError: [WinError 5] Отказано в доступе
  torch\utils\data\dataloader.py:500 -> _MultiProcessingDataLoaderIter
  multiprocessing\connection.py:617 -> _winapi.CreateFile(...)
```

Minimal reproduction: `.venv-gpu\Scripts\python.exe -c "import multiprocessing as mp; mp.Queue()"` → the same error in both the system python and the GPU venv. This is a harness-sandbox boundary, not a torch bug: past runs with `--workers 6` (`all20`) ran in other conditions. Workaround: `--workers 0` (in-process loading; 100–128 img/s here — acceptable).

## 4. Dataset facts of the new type

- `dataset/out_ru/LimboFilter/digits/` — 10 000 PNG + `labels.jsonl` (copied from the `build/gen_limbo_full` render of the updated generator; `real_shots/` untouched — LimboFilter never had any).
- Labels: `answer == text`, 4 chars from `0123456789`, `prompt` = `ВВЕДИТЕ ЦИФРЫ`, non-null `roi`, `source` = CaptchaPainter#drawCaptcha + CaptchaGenerator#randomAnswer.
- `tools/check_labels_and_roi.py dataset/out_ru` after the copy: **90 000 samples, 0 label mismatches, 0 roi problems, RESULT: OK**; `check_band_vs_answer.py`: digits 10000/10000 "the band holds the answer".

## 5. Generator change (one file)

`dataset/generator_ru/dev/captcha/gens/LimboFilter.java` — all comments stripped except one clean-room header; new nested class `Digits`: TYPE_DIGITS layout (4 glyphs of 128 px map), custom `font.ttf` (lazy-loaded, SANS_SERIF fallback), backplates `bg1..bg4.png` stretched and palette-quantised, solid colour from the real config's rgb-color-list, 5 curves, `strikethrough/underline` threaded through `glyphs()`. Assets live in `dataset/generator_ru/assets/limbofilter/`. Accepted after independent verification: both trees compile (javac 21.0.8), smoke `Validate` clean, `map`/`symbols` images eyeballed unchanged, diff −433/+134 in the one owned file.

## 6. What was NOT verified

- The published HF model is unchanged — the new weights are local only; export/upload is a separate decision.
- `test/image1-6.png` (the owner's server screenshots) are not scored (no gold labels on file).
- The `--eval-only` flag of `finetune_ppocr.py` is broken (it only skips the zero step and then trains anyway) — discovered and worked around with `--zero-step`; the flag itself is still unfixed (a one-line fix, left for a later brief).

## 7. Run directory map

- `train/runs/ppocrv6/limbo_digits/` — run 1 (best.pt, result.json, log.txt)
- `train/runs/ppocrv6/limbo_digits2/` — the discarded digits-only exhibit (ckpt only)
- `train/runs/ppocrv6/limbo_digits3/` — best mixed run of the digits phase (best.pt, soup.json, soup_best.pt, result.json, log.txt)
- `train/runs/ppocrv6/limbo_digits3_eval/` — the 16-type zero-step eval (zero_step.json)

## 8. The Cyrillic continuation (evening of 2026-10-26) — from `digits` to a universal model

Part 1 of this report ends at `limbo_digits3` (16 Latin types, digits 0.795). The evening session then added Cyrillic and converged on `universal_v1`:

| run | recipe | what it proved |
|---|---|---|
| `limbo_cyr` | `--expand-charset` (+52 rows → 18 762), all cyr types, lr 8e-6, 2 ep | short Cyrillic learns from zero (symbols 0.535, ru-symbols 0.660); long number-words stay 0.00; Latin degrades (no replay) |
| `limbo_cyr2` | digits/symbols-only, head-lr 5e-5 | **discarded** — hot head-lr destroyed the pretrained head (Latin → 0.00–0.35); checkpoint quarantined |
| `limbo_cyr3` | **replay mix**: 3 short cyr + digits + 5 Latin types, 1 500/type, lr 8e-6, 4 ep | **replay works**: symbols 0.765, ru-symbols 0.860, digits 0.890, Latin held (median 0.9075 over 14 types) |
| `universal_v1` | **all 12 trainable types** (Latin replay + short cyr + `--train-frames`), 5 ep, 34 min | **the final universal checkpoint** (table below) |

**`universal_v1` per-type (n=200 held-out per type, n=1500 for the 6 default val types):**

| type | all20 | universal_v1 |
|---|---|---|
| out/Archy-X/Krypton/map | 0.980 | **1.000** |
| out/InstantlyMoist/Captcha/textcaptcha | 0.240 | 0.240 |
| out/JSH32/Minecaptcha/map | 0.930 | **0.937** |
| out/LagBug/XProtect/code | 0.095 | **0.360** |
| out/LagBug/XProtect/map | 0.065 | **0.270** |
| out/haq/mapcha/map | 0.930 | **0.955** |
| out/irootdev/AnBot/captcha | 0.995 | 0.995 |
| out/jonesdevelopment/sonar/complex | 0.835 | 0.625 |
| out/jonesdevelopment/sonar/legacy | 0.800 | 0.769 |
| out/jonesdevelopment/sonar/standard | 0.805 | 0.571 |
| out/just-captcha/ProstoCaptcha/map | 0.770 | **0.915** |
| out/ringoame196-s-mcPlugin/ReproductionCAPTCHA/map | 0.985 | **1.000** |
| out_ru/BotFilter/map | 0.935 | 0.814 |
| out_ru/CaptchaVerifyZ/map | 1.000 | 0.978 |
| out_ru/GalleryCaptcha/ru-symbols | — | **0.885** (new) |
| out_ru/GalleryCaptcha/ru-web | 0.910 | **0.925** |
| out_ru/LimboFilter/digits | — | **0.890** (new) |
| out_ru/LimboFilter/symbols | — | **0.800** (new) |
| **3 numberword types (map, ru-numberword, ru-numberword-caption)** | — | excluded, scheduled for a length-curriculum run |

**Median over 18 types: 0.8875, micro 0.7797, CER median 0.0344.** The dictionary now covers 18 762 classes (18 710 + 52 Cyrillic), carried inside the checkpoint as `character_list`.

Fixes made to the code during the evening (small, verified by the runs themselves):
- `finetune_ppocr.py`: `--init-from` now grows the head to match a checkpoint with an expanded head before `load_state_dict` (the bug killed two attempts before the fix).
- `soup_eval.py`: vocab is taken from the checkpoint's `character_list` when present; tensors are interpolated only when the base has the same shape; the model head is grown before loading; `soup_best.pt` now stores `character_list`.
- `webapp/app.py`: `PPOCRBackend` grows the head and prefers the checkpoint's `character_list`; the default checkpoint is pinned to a single `DEFAULT_CHECKPOINT` constant.

**WiSE-FT verdict for an expanded head:** the α-sweep on `limbo_cyr3` (best α = 0.6, held-out median 0.644 → 0.772 on the 6 Latin val types) **destroys the Cyrillic classes** (symbols 0.765 → 0.016, ru-symbols 0.860 → 0.002, digits 0.890 → 0.666) — the appended rows have no base to interpolate towards while the encoder is pulled back. The soup is kept as an exhibit (`limbo_cyr3/soup_best.pt`), not used. Replay, not interpolation, is the recipe for vocabulary expansion on this model.

Research basis: `reports/RESEARCH_CYRILLIC_VOCAB.md` (PaddleOCR fine-tune docs, WiSE-FT, replay 10:1–5:1, curriculum for long CTC targets) and the per-language fact that PaddleOCR ships cyrillic_PP-OCRv5 as separate models.

Next steps (agreed with the owner): more epochs of the same replay recipe, more samples per Limbo type (1 500 → 3 000–5 000), a length-curriculum run for the 3 numberword types, TTA in eval, and a scoring pass on the owner's 6 real screenshots.
