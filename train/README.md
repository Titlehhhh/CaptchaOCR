# train/ — the captcha recogniser

A CRNN (CNN + BiLSTM) + CTC trained from scratch on the generated dataset.

```
train/
  captcha_crnn.py   charset, dataset, model, CTC decoding
  train.py          the training loop, the evaluation and the checkpointing
```

## The GPU is there - it just was not installed

The machine has an **NVIDIA GeForce GTX 1080 Ti (11.8 GB, sm_61)**, but the system Python had
**`torch 2.14.1+cpu`** - the CPU build. A CUDA build is now installed in a separate virtual
environment, so the system environment is untouched:

```
.venv-gpu/            torch 2.14.1+cu126, numpy, pillow
```

`cu126` was chosen because it still ships the **sm_61** kernels the 1080 Ti needs - the newer
wheels have dropped Pascal. Verified: `torch.cuda.get_arch_list()` contains `sm_61`, and a 4096³
matmul runs at 7.5 TFLOP/s.

```
.venv-gpu\Scripts\python.exe train\train.py --quick --epochs 150
```

If the virtual environment is ever lost, it is one command:

```
python -m venv .venv-gpu
.venv-gpu\Scripts\python.exe -m pip install torch==2.14.1+cu126 --index-url https://download.pytorch.org/whl/cu126
.venv-gpu\Scripts\python.exe -m pip install numpy pillow
```

## Running it

```
# a smoke run: six types, two of them held out
python train\train.py --quick --epochs 150

# the real thing: every training type, four held out
python train\train.py --epochs 60 --val-types "haq/mapcha/map" "LagBug/XProtect/code" ...

# continue where it stopped
python train\train.py --resume
```

Useful flags: `--device auto|cuda|cpu`, `--workers N` (the image decoding is the bottleneck, so
give it workers), `--lr`, `--batch-size`, `--glyph-height`, `--charset latin|cyrillic`,
`--types` / `--val-types` (substring filters), `--no-augment`, `--augment-affine` (a small
rotation/shift/scale on top of the JPEG/WebP pass - see `reports/TRAINING_MINIMAL_LATIN.md`),
`--save-every`, `--out`.

**There is no `--require-roi`.** Types **without** a band are dropped **by default**; `--allow-no-roi`
is the opposite of what its name suggests to some: it *allows* those ill-posed types in.

## Three things that will waste an hour if you do not know them

**1. CTC needs a lot of steps before it leaves the all-blank plateau.** The loss sits at
`ln(63) = 4.14` - the model emitting nothing but blanks - and creeps down for a long time. A
first run of 8 epochs over 600 images (152 steps) stayed at 4.12 with 0.000 accuracy; at 2850 steps
it was down to 0.57 and learning. **Do not read a flat loss as a bug before you have run a few
thousand steps.**

**2. The band matters more than the model.** On the first real run, a held-out type
(`InstantlyMoist/Captcha/textcaptcha`) scored **accuracy 1.000, CER 0.000** while another held-out
type (`haq/mapcha/map`) scored **0.000** - and the only difference was that the first one's
`roi` in `labels.jsonl` pointed at the answer and the second one's did not exist yet, so the
model was shown a whole map with a title, a "Tries Left" counter, a "Time Left" counter and the
code, and it read the wrong line. The `roi` field is what makes this work; a missing one is
silent, and the validator does not catch it.

**3. The `T >= 2L + 1` constraint has to be enforced per sample.** The dataset widens a sample
until the time steps satisfy it, and the model checks that the feature rows match the height it
was built for. Both of those guards exist because getting either wrong makes the loss plateau
instead of erroring.

## What is in the box

| | |
|---|---|
| Model | CRNN, 3 pools `(2,2), (2,2), (2,1)`, 4 feature rows, BiLSTM(256, 2, bidirectional), CTC head |
| Parameters | 4 623 615 at glyph height 32, 63 classes |
| Input | grayscale, cropped to `roi`, scaled so the **glyph** is 32 px tall, width by aspect, right-padded |
| Normalisation | (x/255 - 0.5) / 0.5 |
| Loss | `CTCLoss(blank=0, zero_infinity=True)`, no label smoothing |
| Optimiser | AdamW, OneCycle, 5 % warmup, grad clip 1.0, weight decay 1e-2 |
| Augmentation | JPEG q15-95, WebP q45-90, brightness, contrast - applied to the finished raster, because the generator already distorts the glyphs |
| Decoding | greedy CTC, with the per-character posterior as a confidence |
| Checkpointing | every `--save-every` steps, keeping the two newest; the model, the optimiser, the scheduler, the step, the CPU and CUDA RNG states and the augmentation RNG state are all saved, so a run resumes exactly |

## The per-type knowledge that makes it work

The plugin and the captcha type are known at inference time, so the decoder can be **constrained**
instead of the model having to guess:

* the allowed characters per type (`BotFilter` is digits only, `CaptchaVerifyZ` is `0-9A-Z`, ...),
* the allowed length per type (`CaptchaVerifyZ` is exactly 5, `ru-web` exactly 5, `BotFilter` 4 or 5),
* the per-type post-processing (reverse the string, turn Russian number words into digits, compute
  an arithmetic expression).

The charset table, the length priors and the mask are all derivable from `labels.jsonl`.
