# train/ — the captcha recognisers

Three models are trained here from the same dataset and the same split:

| model | the script | what it is |
|---|---|---|
| **CRNN + CTC**, from scratch | `train.py` | CNN + BiLSTM + a CTC head, 4 623 615 parameters |
| **PP-OCRv6_medium_rec**, fine-tuned | `finetune_ppocr.py` | the pretrained PaddleOCR model, fine-tuned on our bands |
| **TrOCR-small-printed**, fine-tuned | `finetune_trocr.py` | ViT encoder + transformer decoder |

The published model is the PP-OCRv6 one (`Titlehhhh/captchaocr-ppocrv6`).

```
train/
  captcha_crnn.py      the CRNN: charset, dataset, model, CTC decoding
  train.py             the CRNN training loop, the evaluation and the checkpointing
  ppocr_data.py        the dataset, the crop, the normalisation and the metrics of the PP-OCR line
  finetune_common.py   what the two fine-tunes share: the split, the metrics, the bookkeeping
  finetune_ppocr.py    the PP-OCRv6 fine-tune (entry point)
  ppocr_core.py        its model-specific pieces: the logits, the decoding, the split, the metrics
  ppocr_run.py         its training loop
  finetune_trocr.py    the TrOCR fine-tune (entry point, the same split, so the two are comparable)
  trocr_core.py        its model-specific pieces: the model id, the metrics, the split
  trocr_data.py        its dataset, its collator and its evaluation
  trocr_report.py      its report (the TrOCR numbers next to the PP-OCRv6 ones)
  trocr_run.py         its training loop
  soup_eval.py         the weight interpolation (WiSE-FT) between the base and the fine-tuned model
  export_hf.py         the CRNN exporter to a Hugging Face repository (entry point)
  hf_export/           the body of the CRNN exporter
  export_ppocr_hf.py   the PP-OCRv6 exporter - the one that built the published weights
  make_report.py       builds the measured reports of the runs from their artefacts
  report_builders/     the three report builders
  audit_types.py  aug_sheet.py  band_clip_check.py  band_tightness.py
  bench_per_type.py  bench_pipeline.py  compare_baselines.py  eval_ckpt.py  roi_sheet.py
                      the nine measuring scripts
```

**Git-ignored, on disk only:** `train/runs/**` (the run directories: checkpoints,
`result.json`, `log.txt`, the exports) and `train/published/**` (the copies of the
published artefacts). The *scripts* that used to live inside those directories now
live in `train/` - `make_report.py` is the successor of the three `make_report*.py`
copies, and `export_ppocr_hf.py` of `runs/ppocrv6/export_hf.py`.

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

### The CRNN

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

### The PP-OCRv6 fine-tune

```
# the run that produced the published weights
python train\finetune_ppocr.py --out train\runs\ppocrv6\universal_v1 --epochs 5

# measure the pretrained model and stop
python train\finetune_ppocr.py --zero-step --out train\runs\ppocrv6\zero

# the weight interpolation (WiSE-FT) that the export uses
python train\soup_eval.py --run-dir train\runs\ppocrv6\big --alphas 0,0.25,0.4,0.5,0.6,0.75,1
```

The flags that matter: `--model`, `--epochs`, `--batch-size`, `--lr` / `--head-lr`,
`--val-types` / `--exclude-types` / `--include-types`, `--limit-per-type`, `--workers`,
`--norm paddle|imagenet`, `--glyph-scale band|glyph`, `--no-roi-mode frame|content|skip`,
`--train-frames`, `--holdout-per-type N`, `--expand-charset` (grow the CTC head with the
characters the pretrained dictionary lacks - the Cyrillic ones), `--init-from`, `--resume`,
`--max-minutes`, `--zero-step`, `--eval-only`.

### The TrOCR fine-tune

The same dataset, the same split (`--val-types` defaults to the same seven types as the
PP-OCRv6 run), a different model and a different loss (the decoder's own cross-entropy).

```
python train\finetune_trocr.py --out train\run\trocr_big --epochs 4 --batch-size 8 --max-minutes 18
```

### The exports

```
# the CRNN -> a self-contained Hugging Face repository (config, model, processor, ONNX)
python train\export_hf.py --checkpoint <run>\ckpt\step_0001234.pt --out build\hf_export --charset latin

# the PP-OCRv6 -> a Hugging Face folder (this is what built the published weights)
python train\export_ppocr_hf.py --ckpt train\runs\ppocrv6\universal_v1\best.pt --out <dir> --soup-alpha 1.0
```

`export_hf.py` verifies itself: it runs the *training* code and the *exported* code on the same
images and compares the decoded strings, re-loads the repository in a **fresh process** through
`AutoModel` / `AutoProcessor`, and runs the ONNX through `onnxruntime`. All three must agree, and
the script fails loudly instead of writing a model card. `export_ppocr_hf.py` writes
`finetune_meta.json` - the provenance of the export (checkpoint, epoch, step, alpha, classes).

### The reports

```
python train\make_report.py crnn           # reports/TRAINING_CRNN_BIG.json
python train\make_report.py ppocr-result   # reports/TRAINING_PPOCR_V6_BIG.json
python train\make_report.py ppocr-log      # reports/TRAINING_PPOCR_V6.json
```

Every number in those reports is read out of a file that a run wrote. The reports are
**measured results**: they are written by the command above and are never edited by hand.

### The measuring scripts

| script | what it measures |
|---|---|
| `audit_types.py` | which dataset types survive the band filter and the charset filter |
| `band_clip_check.py` / `band_tightness.py` | does the band cut the glyph it carries? |
| `roi_sheet.py` / `aug_sheet.py` | contact sheets of the bands and of the augmented samples |
| `eval_ckpt.py` | a trained checkpoint on whole types, with an optional band correction |
| `bench_per_type.py` / `compare_baselines.py` | our model against the measured baselines, per type |
| `bench_pipeline.py` | the data pipeline and the GPU step, separately |

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

The PP-OCRv6 line has its own pipeline (`ppocr_data.py`): the band crop, 48 px tall, the width
capped at 320, the PaddleOCR normalisation `(x / 255 - 0.5) / 0.5` and the RGB -> BGR swap, and
the metrics are exact match and CER per type, aggregated as the **median over the types**.

## The per-type knowledge that makes it work

The plugin and the captcha type are known at inference time, so the decoder can be **constrained**
instead of the model having to guess:

* the allowed characters per type (`BotFilter` is digits only, `CaptchaVerifyZ` is `0-9A-Z`, ...),
* the allowed length per type (`CaptchaVerifyZ` is exactly 5, `ru-web` exactly 5, `BotFilter` 4 or 5),
* the per-type post-processing (reverse the string, turn Russian number words into digits, compute
  an arithmetic expression).

The charset table, the length priors and the mask are all derivable from `labels.jsonl`.
