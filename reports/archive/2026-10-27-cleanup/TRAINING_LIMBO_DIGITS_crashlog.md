# Training report — PP-OCRv6 fine-tune on `out_ru/LimboFilter/digits`

- **Date / window:** 2026-10-26, run window ~16:00–16:13 (MSK)
- **Machine:** Windows, NVIDIA GeForce GTX 1080 Ti (11.8 GB, sm_61), torch 2.14.1+cu126 (CUDA OK), transformers 5.19.0

## 1. The command (exact, one line)

```
.venv-gpu\Scripts\python.exe train\finetune_ppocr.py --out train\runs\ppocrv6\limbo_digits --init-from train\runs\ppocrv6\all20\soup_best.pt --epochs 2 --batch-size 32 --lr 5e-6 --head-lr 5e-6 --workers 6 --limit-per-type 2000 --holdout-per-type 200 --eval-every 1 --save-every 400 --max-minutes 45
```

## 2. Wall-clock time and outcome

- Attempt 1: launched 2026-10-26 ~16:00:07 (python up 16:00:02) — **crashed ~16:11**, before any training step.
- Attempt 2: `--resume` variant (permitted: attempt 1 crashed before `result.json`) launched ~16:03:30 — **crashed ~16:13**, same place.
- Both crashed before the training loop; `train\runs\ppocrv6\limbo_digits\` holds only an empty `ckpt\` + `log.txt`. **No `result.json`, no `best.pt`, no `final.pt`.**

## 3. What broke

Zero-step evaluation crashed:

```
PermissionError: [WinError 5] Access is denied
  torch/utils/data/dataloader.py:500  -> _MultiProcessingDataLoaderIter
  torch/utils/data/dataloader.py:438  -> _MultiProcessingDataLoaderIter
  torch/utils/data/dataloader.py:1134 -> multiprocessing_context.Queue()
  multiprocessing/queues.py:40     -> connection.Pipe(duplex=False)
  multiprocessing/connection.py:617 -> _winapi.CreateFile(...)
PermissionError: [WinError 5] Отказано в доступе
```

Minimal reproduction in a fresh foreground process:

```
.venv-gpu\Scripts\python.exe -c "import multiprocessing as mp; mp.Queue()"
→ PermissionError: [WinError 5] Access is denied  (same named-pipe path)
```

So the Windows session can no longer create multiprocessing named pipes (IPC) at all right now;
torch itself initialised fine on the GTX 1080 Ti (sm_61). Training could not start.

## 4. TRAIN / HELD-OUT / DROPPED lists (as printed)

TRAIN (6):

```
   out/Archy-X/Krypton/map                          n=10000 alphabet=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcd
   out/haq/mapcha/map                               n=9984 alphabet=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYabcde
   out/just-captcha/ProstoCaptcha/map               n=10000 alphabet=23456789ABCDEFGHIJKLMNPQRSTUVWXYZabcdefg
   out/ringoame196-s-mcPlugin/ReproductionCAPTCHA/map n=10000 alphabet=0123456789ABCDEF
   out_ru/GalleryCaptcha/ru-web                     n=10000 alphabet=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcd
   out_ru/LimboFilter/digits                        n=10000 alphabet=0123456789
```

HELD-OUT (6): `out/JSH32/Minecaptcha/map` (band=10000), `out/jonesdevelopment/sonar/complex|legacy|standard` (band=0),
`out_ru/BotFilter/map` (band=0), `out_ru/CaptchaVerifyZ/map` (band=10000) — n=10000 each.

DROPPED (9): 4 types without band (`out/InstantlyMoist/Captcha/textcaptcha`, `out/LagBug/XProtect/code`,
`out/LagBug/XProtect/map`, `out/irootdev/AnBot/captcha`); 5 Cyrillic labels outside the latin dictionary
(`out_ru/GalleryCaptcha/ru-numberword`, `ru-numberword-caption`, `ru-symbols`, `out_ru/LimboFilter/map`,
`out_ru/LimboFilter/symbols`).

**`out_ru/LimboFilter/digits` IS in the TRAIN list** (Latin digits, alphabet=0123456789, n=10000) — the
required condition was met; the run did not stop for that reason.

Printed split sizes: train items 10794; eval items 13200; held-out items 13200; held-out samples 1200 over 6 types.

## 5. Per-type table, comparison, digits number

- **Per-type table (last eval): NOT PRODUCED** — the eval crashed before finishing, so there is no per-type
  exact_match/CER table and no `final` block in `result.json`.
- **Digits number (`out_ru/LimboFilter/digits` exact match): NOT MEASURED** (run never reached eval/training).
- **Comparison vs all20 `final` per_type: NOT COMPUTABLE** (no new `final` numbers exist).

## 6. Self-check

`python -c "import json; d=json.load(open(r'train\runs\ppocrv6\limbo_digits\result.json',encoding='utf-8')); print(d['final']['held_out'])"`
→ **NOT EXECUTABLE**: `train\runs\ppocrv6\limbo_digits\result.json` does not exist (run never finished).

## 7. Files touched by this session

- Written: `reports\TRAINING_LIMBO_DIGITS.md` (this report)
- Written by the trainer (owned run dir): `train\runs\ppocrv6\limbo_digits\` (`log.txt`, empty `ckpt\`)
- Read-only for me: `train\runs\ppocrv6\all20\`, `train\published\`

## 8. What was NOT verified

- Any training loss / checkpoint / final accuracy numbers (run never started training).
- The LimboFilter/digits behaviour at inference time (not measured).
- Comparison against the previous run's numbers (no new final numbers).

## 9. Anything broken

- Windows named-pipe creation is denied in the current session (`WinError 5` / `ERROR_ACCESS_DENIED`), which
  kills torch DataLoader worker queues (`--workers 6`). Reproduced minimally. No source change was made (not
  permitted); a fallback (`--workers 0`) exists in `train/finetune_trocr.py` but not in `train/finetune_ppocr.py`.
