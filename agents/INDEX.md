# INDEX — CaptchaOCR

**Agent-facing index of the whole repository.** One file to read to know where everything is, what state it
is in, and what not to touch.

Everything below was **measured on this machine on 2026-10-21**, not copied from `AGENTS.md` /
`HANDOVER.md`. Where the documents and the measured reality disagree, the discrepancy is written down
here explicitly (see [§9 Discrepancies](#9-discrepancies-docs-vs-measured-reality)).

- Companion files: [`agents/AGENT_LOG.md`](AGENT_LOG.md) (who owns what, the subagent protocol),
  [`agents/INDEX.json`](INDEX.json) (the machine-readable version of this file).
- The authoritative documents remain `AGENTS.md` (rules) and `HANDOVER.md` (state). This file does not
  replace them; it points at them.

---

## Кратко по-русски (резюме)

Репозиторий состоит из двух половин: **генератор датасета** (Java 21, `dataset/generator` и
`dataset/generator_ru`) и **модели** (`bench/` — бенчмарки готовых OCR, `train/` — CRNN+CTC с нуля).
Датасет — **46 типов капч, 4600 размеченных PNG** (34 типа в `dataset/out/`, 12 типов в
`dataset/out_ru/`, по 100 на тип) плюс **1240 референсных** картинок в `real_shots/`. Типы делятся
на три группы: **A** — чистый OCR (20), **B** — OCR + шаг solver'а (11), **C** — вообще не OCR (15).
Полоса `roi` в `labels.jsonl` важнее самой модели: полоса, которая не помещается в кадр, — это не
полоса (`roi = null`). Три ловушки, которые уже стоили проекту времени: CTC висит в **all-blank
плато** (лосс на `ln(63) = 4.14` и ползёт вниз тысячи шагов — плоский лосс это не баг), **дефекты
апстрима не «чинят»** (воспроизводят и документируют), **датасет — артефакт** (шрифты зависят от
машины), поэтому генерируют один раз и учат с этой папки. На машине **нет `pwsh`**, а **запуск
`.ps1` заблокирован** — логику `build.ps1` выполняют inline. Подробности ниже на английском.

---

## 1. What this project is

**CaptchaOCR** is a laboratory for building captcha-solving models that will eventually be published
on Hugging Face. Two halves, deliberately separated:

| Half | What it is | Where |
|---|---|---|
| **Dataset** | A Java 21 generator that re-renders, pixel-faithfully, the captchas that real open-source Minecraft anti-bot plugins produce. | `dataset/generator/`, `dataset/generator_ru/`, output in `dataset/out/` and `dataset/out_ru/` |
| **Models** | Benchmark harnesses that run existing OCR / captcha models over the dataset, and training code that produces our own checkpoints. | `bench/`, `train/` |

The dataset exists because no off-the-shelf OCR model handles this domain. The measured baselines are
bad: the best of them sit around **acc 0.077–0.115 / CER 0.785–1.835** (the 0.077 figure is measured on the
whole frame and the 0.115 on the `roi` crop — they are **different protocols**, see
`reports/CAPTCHA_OCR_REPORT.md` and `reports/bench_results*.json`). That gap is the reason the project
exists.

The owner is doing exploratory lab work: breadth of model comparison is wanted, and the dataset is the
lever that makes those comparisons meaningful.

---

## 2. Repository map

Every top-level entry that actually exists in the working tree. `git ls-files` tracks only:
`.gitignore`, `AGENTS.md`, `CONTINUE.md`, `HANDOVER.md`, `README.md`, `build.ps1`, `llms.txt`, `paths.py`,
`bench/`, `dataset/`, `docs/`, `reports/`, `research/`, `tools/`, `train/`, `agents/`. Everything
else is either git-ignored or an empty leftover.

| Path | What it holds | Owner(s) / who touches it | Regen or hand-written |
|---|---|---|---|
| `dataset/` | The Java generators **and** the generated dataset (two trees). | dataset agents (generators); main agent (regeneration) | **mixed** — `generator*/` hand-written source, `out*/` generated |
| `train/` | CRNN+CTC model, training loop, HF export, README, nested `AGENTS.md`. | trainer agent | hand-written |
| `tools/` | 35 helper scripts (34 Python + 1 PowerShell): checkers, site analysis, report builders, one-off probes. | tools agent | hand-written |
| `reports/` | Measured results (JSON — **never edit them**), Markdown/HTML reports, the big overview, and `research2/` (10 research reports). | bench / review / research agents | hand-written; **the JSONs are measured results — never edit them** |
| `research/` | Upstream jars, decompiled sources, reference renders, and `runtime/` (the C# runtime source + its config). | research agents | **mixed** — `jars/`, `decompiled/`, `cvz*/` are downloaded and git-ignored; the `.md`/`.py`/`.cs` findings are hand-written |
| — | **Сайт-атлас и каталог референсов удалены из публичного репозитория** (2026-10-22). Эталонные скриншоты остались в `dataset/out_ru/*/real_shots/` и не публикуются. | — | — |
| `docs/` | Human-facing documentation: `ONBOARDING.md`, `GLOSSARY.md`, `adr/` (three decisions), `pipeline-design.md`. | docs agent | hand-written |
| `build/` | `javac` output (`classes/`, `classes_ru/`) **and** all scratch experiments. | nobody — scratch space | regenerable, git-ignored |
| `.venv-gpu/` | The CUDA Python env: `torch 2.14.1+cu126`, numpy, pillow, transformers 5.19.0, onnxruntime 1.30. | nobody — environment | regenerable, git-ignored (one command, see `train/README.md`) |
| `agents/` | **This directory.** The agent-facing index, the agent log, the harness notes, the repository-conventions research. | index agent (this file's author) | hand-written |
| `AGENTS.md` | The briefing: the orchestrator contract, the map, the commands, the machine's traps, the safety rules. **18.6 KB, budget 64 KiB.** | main agent | hand-written |
| `HANDOVER.md` | The handover note: state of the project, what to train on, the measured journal (§6.5). | main agent | hand-written |
| `README.md` | The dataset's own documentation, plugin by plugin, incl. the upstream-defect table. | dataset agent | hand-written |
| `CONTINUE.md` | **The next-session prompt**: what the project is, where we stopped, every measured number, what to do next, the open decisions of the owner. | main agent | hand-written |
| `llms.txt` | The machine-readable map of the repository (llms.txt format). | main agent | hand-written |
| `build.ps1` | One-shot: compile → generate → validate, both trees. **Cannot be executed on this machine** (see §5). | main agent | hand-written |
| `paths.py` | Shared repo-relative path resolution for `bench/` and `tools/` (`REPO`, `OUT`, `OUT_RU`, `REPORTS`, `SITE`, `results()`, `dataset_type()`). | main agent | hand-written |
| `.gitignore` | Ignore rules: `build/`, `.venv-gpu/`, `__pycache__/`, `*.pt/.pth/.onnx`, `train/run/`, `tmp/`, `pip-*`, `torchinductor_*`, `research/{cfr.jar,cvz*/,jars/,decompiled/}`. | main agent | hand-written |
| `tmp/` | Scratch images and helper scripts. | nobody | git-ignored scratch |

### 2.1 `dataset/` — the two generators and the two trees

| Path | What it holds |
|---|---|
| `dataset/generator/dev/captcha/Cg.java` | The generator interface every captcha implements: `plugin()`, `id()`, `answer()`, `image()`, `source()`, optional `prompt()`, optional `roi()`. |
| `dataset/generator/dev/captcha/Img.java` | Canvas / font / random helpers, distortion warps, PNG normalisation. |
| `dataset/generator/dev/captcha/McUi.java` | The Minecraft UI surfaces: chat frame, window title, inventory, anvil. (This file carries the two bugs that cost the most — see §6.) |
| `dataset/generator/dev/captcha/Gen.java` | Reflective registry + batch runner + `index.html` writer. |
| `dataset/generator/dev/captcha/Stats.java` | Colour-histogram diagnostic for one PNG or a directory. |
| `dataset/generator/dev/captcha/Validate.java` | Per-type `n / minColors / blank / dupes / labels` table. |
| `dataset/generator/dev/captcha/gens/` | 16 files, 34 captcha types from 18 upstream plugins: `XProtect.java` (12 types), `Sonar.java` (3), `FabricCaptcha.java` (2), `Krypton.java` (2), `AdvancedCaptcha.java` (2), `ForgeCaptchas.java` (2 — `laforetbrut/are-you-sure` + `Mrbysco/Captcha`), `GuiChecks.java` (2 — `Yukun99/Captchas` + `China2B2T/Captcha`), `GuiPlugins.java` (2 — `Z4OLLIEZ4/reCaptcha` + `Joey61021/captcha`), plus one type each: `InstantlyMoist.java`, `Minecaptcha.java`, `Mapcha.java`, `Prosto.java`, `AnBot.java`, `NCaptcha.java`, `ReproCaptcha.java`, and the shared helper `TextBand.java`. |
| `dataset/generator_ru/dev/captcha/gens/` | 8 files, 12 captcha types for the GalleryCaptcha type group and the plugins identified from it: `LimboFilter.java` (map, symbols, framed2x2, framed3x3), `RussianCaptcha.java` (ru-numberword, ru-numberword-caption), `WebCaptcha.java` (ru-web), `ObjectCaptcha.java` (ru-object-swatch), `BotFilter.java` (map), `CaptchaVerifyZ.java` (map), `Supl1nCaptchaGui.java` (clickblock), `MapPalette.java` (shared palette, not a type). |
| `dataset/generator_ru/dev/captcha/` (core) | **Empty on purpose.** The core (`Cg`, `Img`, `McUi`, `Gen`, `Stats`, `Validate`) is compiled from `dataset/generator` and shared by both trees — that is what `build.ps1` does. |
| `dataset/out/` | **Generated.** 18 owner/repo dirs → 34 type dirs → 3400 PNGs + 34 `labels.jsonl` + `index.html`. **The PNGs are no longer tracked by git** (`.gitignore`: `dataset/out/**/*.png`) — the full set lives on Hugging Face; the labels stay in the index. |
| `dataset/out_ru/` | **Generated.** 8 plugin dirs (5 of them carry samples) → 12 type dirs → 1200 PNGs + 12 `labels.jsonl` + `index.html`, plus 8 `real_shots/` folders with 517 reference images. The PNGs (and the `real_shots/`) are **not tracked**; only the labels and `index.html` are. |
| `dataset/samples/` | **The showcase that stays in git.** 5 PNGs per type — `dataset/samples/<plugin>/<type>/001.png … 005.png`, 230 files, 2.21 MB — plus `README.md` (the type table) and `index.html` (a filterable contact sheet with the answers). The PNGs are byte-identical copies of the generated ones, never re-drawn. |

### 2.2 `train/`

| Path | What it holds |
|---|---|
| `train/captcha_crnn.py` | Charset (`CHARSET` = 62 latin, `CYRILLIC` = 33, blank = 0), `CaptchaDataset` (crop to `roi`, scale so the **glyph** is 32 px, `T >= 2L+1` widening), `CRNN` (3 pools `(2,2),(2,2),(2,1)`, BiLSTM(256, 2, bidirectional), CTC head), `greedy_decode` with per-character posterior, `levenshtein`/`cer`. |
| `train/train.py` | The training loop: flags (see §5), the built-in `EXCLUDE` list (13 types), the type-held-out split, the checkpointing (model + optimiser + scheduler + CPU/CUDA RNG + augmentation RNG), the per-type evaluation and `val_report.json`. |
| `train/export_hf.py` | HF repo exporter: `config.json`, `configuration_captha.py`, `modeling_captha.py`, `processing_captha.py` (**one** processor, no sub-processor), `vocab.json`, `model.safetensors`, `onnx/model.onnx`, model card, LICENSE. **Not verified end to end** — `CONTINUE.md` says the agent was stopped; the file parses cleanly (checked 2026-10-21) but was never executed. |
| `train/README.md` | How to run it, the three hour-wasting traps, and the per-type inference knowledge (charset mask, length prior, post-processing). |
| `train/run/` | Where a run writes its checkpoints and `val_report.json` (git-ignored). Currently absent — no run has ever been left in place. |

### 2.3 `bench/`

| Path | What it holds |
|---|---|
| `bench/bench_hf.py` | The HF harness. `TEXT_TYPES` = 13 types × `N_PER_TYPE = 8` = **104 test items**, all from `dataset/out`. `load_image`/`load_band` crop to `roi`. `MODELS` = 10 HF repos, overridable with `sys.argv[1:]`. Writes `reports/bench_results.json`. |
| `bench/bench_onnx.py` | Raw ONNX captcha models (captCHAD, phpwind-captcha-ocr). Writes `reports/bench_results_onnx.json`. |
| `bench/bench_others.py` | EasyOCR, custom-code CRNN / conv-transformer (Graf-J, with the `AutoModel` fallback), Florence. Writes `reports/bench_results_others.json`. |
| `bench/bench_easyocr.py` | EasyOCR only — the `readtext` API needs a path, not a PIL image. |
| `bench/show_bench.py` | Pretty-prints `reports/bench_results.json`. |
| `bench/test_models.py` | Ad-hoc multi-model tester against the project images (sets `PYTHONIOENCODING=utf-8` itself). |

### 2.4 `tools/` — every script

| Script | What it does |
|---|---|
| `tools/check_labels_and_roi.py` | **The main checker.** Re-derives the Russian number spellings independently of the generator, checks that every band fits inside the canvas and is not a flat colour. |
| `tools/check_band_vs_answer.py` | Per type: does the band carry the answer, the text, or is there no band at all? |
| `tools/check_bands_against_labels.py` | Does every `roi` band carry the answer and nothing else? |
| `tools/check_caption_outside_roi.py` | The gallery caption's ink must never be inside the text band of a composite. |
| `tools/check_composite_scale.py` | Is a gallery composite really a rescaled Minecraft map (not a palette image)? |
| `tools/audit_sources.py` | Prints the distinct `source` strings per type — the audit trail. |
| `tools/summarise_roi.py` | Per type: how many samples have a band, how many cover the whole picture, median band size. |
| `tools/measure_glyphs.py` | Measures the real glyph heights and band sizes of the generated maps (the input for the H=32 scaling plan). |
| `tools/count_colors.py` | Distinct colours per sample, per type (the cheapest check that a composite is not palette-quantised). |
| `tools/restore_real_shots.py` | **Puts the reference images back** into `dataset/out_ru/` after a regeneration (from `<gallery-refs>/`, `research/refout/`, `research/jars/bf_dataset/`, `research/`). |
| `tools/fetch_dataset.py` | **Downloads the full dataset back from Hugging Face** (`Titlehhhh/captchaocr-dataset` → `dataset/full/`). Flags: `--dry-run` (prints the plan, no network), `--types`, `--dest`, `--repo-id`, `--revision`, `--cache-dir`. The type list is read from the `labels.jsonl` files that stay in git, so the plan needs no network. |
| `tools/contact_sheet.py` | Generated samples of a type next to a reference image, with per-cell colour counts. |
| `tools/match_site_to_dataset.py` | For every site image, the nearest dataset image — evidence that a catalogue version is served by a plugin. |
| `tools/cluster_site_captchas.py` | Clusters the 525 catalogue images into visual families (`<gallery-refs>/clusters/`). |
| `tools/alpha.py` | Alpha-channel statistics of the catalogue images. |
| `tools/analyze_cells.py`, `tools/analyze_green2.py`, `tools/analyze_grid.py` | Cell / grid / green-channel probes of the catalogue images. |
| `tools/colors.py` | Colour histogram of a catalogue image. |
| `tools/crop_grid.py`, `tools/down150.py`, `tools/tile.py`, `tools/zoom.py` | Crop / resize / tile / zoom one-offs on the catalogue (write into `tmp/`). |
| `tools/fix_b64.py` | Regenerates `reports/image_b64.json` (the embedded-image payload of the HTML report). |
| `tools/generate_pdf_html.py` | Builds `reports/captcha_pdf_embedded.html` from `reports/image_b64.json`. |
| `tools/glyphs.py` | Connected-component glyph extraction from the catalogue images. |
| `tools/jigsaw2.py`, `tools/jigsaw3.py` | Jigsaw-tile matching over the catalogue (the puzzle family hunt). |
| `tools/links.py`, `tools/urls.py`, `tools/strip_html.py` | HTML / URL scraping helpers. |
| `tools/man.py` | Groups `<gallery-refs>/manifest.json` by section. |
| `tools/png_meta.py` | PNG chunk reader. |
| `tools/seam.py` | Detects the seams of a jigsaw image. |
| `tools/sg.ps1` | Sourcegraph code search. **A `.ps1` file — cannot be executed on this machine.** |

(13 of these carry a UTF-8 BOM: `alpha.py`, `analyze_green2.py`, `down150.py`, `fix_b64.py`, `jigsaw3.py`,
`links.py`, `man.py`, `seam.py`, `strip_html.py`, `tile.py`, `urls.py`, `zoom.py`, and `bench/show_bench.py`.
Python reads them fine; an editor that does not expect a BOM may show a stray character.)

### 2.5 `reports/` — every committed file

| File | What it is |
|---|---|
| `reports/bench_results.json` | Measured HF benchmark results. Currently **one** model: `anuashok/ocr-captcha-v3` — acc 0.0769, CER 0.7853, n=104. |
| `reports/bench_results_onnx.json` | Measured ONNX benchmark results (captCHAD, phpwind). |
| `reports/bench_results_others.json` | Measured results for EasyOCR, Graf-J crnn, Graf-J conv-transformer, Florence. |
| `reports/subagent_results.json` | The results of the six early generator subagents (labels-only, no image re-reading). Note: it records `LagBug/XProtect/different` with `count: 30` — the shipped tree has 100. Stale. |
| `reports/CAPTCHA_OCR_REPORT.md` | The report on the search for ready-made captcha/OCR models, with the measured baselines. |
| `reports/SITE_CAPTCHAS.md` | The GalleryCaptcha type group analysis, version → plugin mapping. |
| `reports/LIMBOFILTER_IDENTIFICATION.md` | The identification of the Russian number-word family as Elytrium/LimboFilter (AGPL-3.0). |
| `reports/RU_PLUGINS_CAPTCHA_VERIFYZ_SMARTCAPTCHA.md` | Upstream research on CaptchaVerifyZ and SmartCaptcha. |
| `reports/PUZZLE_OBJECT_FAMILIES.md` | The puzzle (V4/V5/V52/V53) and object (V8) families — upstream hunt. |
| `reports/MODEL_PLAN.md` | The model plan: architecture, augmentation, training, publishing. |
| `docs/adr/0001-dataset-is-kept-in-git.md` | Review of `dataset/generator_ru/…/gens/` (B1–B7, N1–N16) + a status table of what was fixed since. |
| `docs/adr/0002-recogniser-architecture-and-data.md` | Review of `reports/MODEL_PLAN.md`. |
| `docs/adr/0003-plugin-identification-method.md` | Fact-check of the Russian / GalleryCaptcha-type research reports (F1–F14, C1–C7). |
| `reports/captcha_report.html` | The HTML report (small). |
| `reports/captcha_pdf_embedded.html` | The PDF/HTML report with the images embedded (321 KB). |
| `reports/image_b64.json` | The base64 image payload for the above (310 KB). |

### 2.6 `research/`, `build/`

| Path | What it holds |
|---|---|
| `<gallery-refs>/` | The GalleryCaptcha type group: 525 PNGs in 11 sections (`s00`…`s10`; `s09_API_V7_Пазл_капчи` exists but is **empty**), plus `manifest.json` (image → source URL → section) and `download.ps1` / `montage.ps1` (**`.ps1`, not executable here**). |
| `<gallery-refs>/clusters/` | 22 cluster contact sheets + `clusters.json` (the visual-family clustering of the 525). |
| `<gallery-refs>/site_matches.json`, `<gallery-refs>/cluster_report.txt` | The output of the catalogue→dataset matching and of the clustering. |

> **Легенда.** `<gallery-refs>/` — каталог эталонных скриншотов GalleryCaptcha, `<atlas>/` — сайт-атлас.
> Оба каталога **удалены из публичного репозитория** (2026-10-22); в документах они оставлены как
> указатели на то, где лежали данные, из которых сделан тот или иной вывод. |
| `research/` | Upstream jars (`jars/`, 526 files), decompiled sources (`decompiled/`, `cvz1.2/` 2687 files), reference renders (`refout/`, `myout/`, `reassembled/`), the pixel-diff probe `DiffCaptchaVerifyZ.java`, the web-research scratch (`.py`, `.html`, `.ps1`), and the findings `RU_CAPTCHA_SOURCES.md`, `WEB_CAPTCHA_V6_FINDINGS.md`. |
| `research/jars/bf_dataset/` | The 510 real upstream BotFilter renders (file name = answer). The source of `dataset/out_ru/BotFilter/real_shots/`. |
| `build/classes/`, `build/classes_ru/` | The compiled generators (regenerable). |
| `build/scratch/roilabel.py` | The colour-level band rule that `tools/` does not yet own. |
| `build/review/`, `build/*/` | Scratch from the review and training experiments (contact sheets, probe scripts, `ckpt/`, `val_report.json`). |

---

## 3. The dataset contract

### 3.1 Path scheme

```
dataset/out/<owner>/<repo>/<captchaType>/NNN.png      001.png .. 100.png
dataset/out/<owner>/<repo>/<captchaType>/labels.jsonl

dataset/out_ru/<Plugin>/<captchaType>/NNN.png         001.png .. 100.png
dataset/out_ru/<Plugin>/<captchaType>/labels.jsonl
```

- `dataset/out/` uses the upstream **`owner/repo` string**, which contains a `/`. The plugin is
  therefore **two** path levels and the type is the third:
  `dataset/out/jonesdevelopment/sonar/standard/001.png`.
- `dataset/out_ru/` uses **flat** plugin names (`LimboFilter`, `BotFilter`, `CaptchaVerifyZ`,
  `CaptchaGUI`, `GalleryCaptcha`), because that is what the reserved plugin folders are called. The
  `GalleryCaptcha/` prefix is the **gallery's presentation**; the renderer output of the same family lives
  under `LimboFilter/`.
- Each tree also has a top-level `index.html`: a contact sheet of the first 16 samples per type with
  their ground-truth answers. **This is the intended review surface** — no automation in this repo can
  look at an image, so eyeballing the contact sheet is part of using the dataset, not an extra.

**The PNGs of the dataset are not in git** (ADR 0004): `.gitignore` carries
`dataset/out/**/*.png` and `dataset/out_ru/**/*.png`, so only the `labels.jsonl` and the two
`index.html` files stay tracked. The full dataset — 4600 PNG, 43.57 MB — is on Hugging Face
(`Titlehhhh/captchaocr-dataset`); `python tools/fetch_dataset.py` pulls it back into
`dataset/full/`. What stays visible in git is the **showcase**: 5 PNGs per type under
`dataset/samples/<plugin>/<type>/` (230 files, 2.21 MB) and its contact sheet
`dataset/samples/index.html`. The 517 `real_shots/` reference images are excluded too — they are
other people's screenshots and are never published.

### 3.2 `labels.jsonl` — one JSON object per sample, in `NNN.png` order

Measured: **all 4600 rows carry exactly these ten keys**, in this set. No row has a null `prompt`;
1701 rows have `roi = null`.

| Field | Meaning |
|---|---|
| `file` | The PNG filename inside the type directory, e.g. `001.png`. |
| `plugin` | The upstream `owner/repo` string (in `out/`) or the flat plugin name (in `out_ru/`). Matches the directory. |
| `captcha` | The captcha type id. Matches the directory name. |
| `answer` | The ground truth a legitimate player would produce. **Case and format are significant** — some plugins verify case-sensitively, some do not. |
| `text` | The string that is **drawn in the picture**. |
| `prompt` | The challenge text shown to the player, colour codes stripped. Never null in the shipped tree. |
| `roi` | The bounding box `[x, y, w, h]` of the text band that carries the answer, or `null` when the whole frame is the text (or there is no text at all). |
| `width`, `height` | The pixel dimensions of the PNG. |
| `source` | The upstream class and method the algorithm was taken from — the audit trail. |

A real row:

```json
{"file":"001.png","plugin":"LimboFilter","captcha":"map","answer":"690",
 "text":"шестьсот девяносто","prompt":"ВВЕДИТЕ ТОЛЬКО ЦИФРЫ","roi":[4,36,107,46],
 "width":128,"height":128,"source":"net.elytrium.limbofilter.captcha.painter.CaptchaPainter#drawCaptcha; ..."}
```

### 3.3 `answer` vs `text` — precisely

- `text` is what the **recogniser must read**. `answer` is what the **player must type**. They differ
  only where a *solver* step is needed between reading and answering.
- Measured: `text != answer` in **8 of the 46 types** (all 100 rows of each), in two semantic families:
  - **Russian number words** — the picture shows «шестьсот девяносто», the player types `690`:
    `GalleryCaptcha/ru-numberword`, `GalleryCaptcha/ru-numberword-caption`, `LimboFilter/map`,
    `LimboFilter/framed2x2`, `LimboFilter/framed3x3` (in the last two the words sit inside rotated
    frames).
  - **Arithmetic** — the picture shows `19 - 11`, the answer is `8`:
    `LagBug/XProtect/equation`, `FeelingAlive0/AdvancedCaptcha/math`, `Mrbysco/Captcha/math`.
- In the other 38 types `text == answer` exactly.
- Consequence for training: the recogniser is trained on **`text`** (`build_items` uses
  `label_field="text"`), and the conversion to `answer` is the solver's job. The end-to-end metric
  compares against `answer`.
- Two more cases that look like a solver step but are not: `LagBug/XProtect/reverse` (the player must
  reverse the string; `text` is the drawn string and `answer` is the same string — the reversal is
  applied by the player, not by the picture) and `n1zamu/NCaptcha/anvil` (the upstream prints the
  answer twice in ordinary digits — an upstream defect that is reproduced, so `text == answer`).

### 3.4 `roi` — the band

- `roi` is the bounding box of the **text band that carries the answer**. It exists because **29 of
  the 46 types are scenes** — a chat log, an inventory window, an anvil dialog, a gallery composite —
  where the answer is one line among several. Measured: 29 types carry a band on every sample except
  `haq/mapcha/map`, which carries one on 99 of 100 (1701 of the 4600 rows have `roi = null`).
- **The rule the bands were computed with: a band that does not fit inside the frame is not a band.**
  `roi()` returns `null` rather than a rectangle that holds only part of the answer.
- The band is cropped **before** the recogniser sees the image, in both the training code
  (`CaptchaDataset._load`) and the benchmark harnesses (`load_band`). The plugin is known at inference
  time, so the cropper is a per-plugin constant — nothing to learn.
- **A wrong band is worse than no band**: the label cannot be fitted, the loss does not come down, and
  the validator does not catch it. `tools/check_band_vs_answer.py` is the standing checker; the
  colour-level rule still lives only in `build/scratch/roilabel.py`.

---

## 4. The 46 captcha types

Derived by counting the PNGs and reading the `labels.jsonl` files, **not** by copying the list from
`HANDOVER.md` §2. The group letters follow `HANDOVER.md` §2 (A = pure OCR, B = OCR + a solver step,
C = not OCR at all).

**Totals measured on 2026-10-21:** `dataset/out/` = **3400** labelled PNGs in **34** types;
`dataset/out_ru/` = **1200** labelled PNGs in **12** types + **1240** reference PNGs in `real_shots/`.
Grand total: **4600** labelled images, **46** types, **100** samples each; **5840** PNG files in the two
trees altogether.

### Group A — pure OCR (20 types, 2000 images)

The answer is literally drawn in the picture, 3–8 characters, recoverable by reading.

| # | Plugin / captcha | Plugin field | Captcha | Canvas | Group | Samples |
|---|---|---|---|---|---|---|
| 1 | `Archy-X/Krypton/map` | `Archy-X/Krypton` | `map` | 128×128 | A | 100 |
| 2 | `InstantlyMoist/Captcha/textcaptcha` | `InstantlyMoist/Captcha` | `textcaptcha` | 128×128 | A | 100 |
| 3 | `JSH32/Minecaptcha/map` | `JSH32/Minecaptcha` | `map` | 130×130 | A | 100 |
| 4 | `LagBug/XProtect/code` | `LagBug/XProtect` | `code` | 130×130 | A | 100 |
| 5 | `LagBug/XProtect/map` | `LagBug/XProtect` | `map` | 130×130 | A | 100 |
| 6 | `LagBug/XProtect/picture` | `LagBug/XProtect` | `picture` | 114×174 | A | 100 |
| 7 | `haq/mapcha/map` | `haq/mapcha` | `map` | 128×128 | A | 100 |
| 8 | `irootdev/AnBot/captcha` | `irootdev/AnBot` | `captcha` | 128×128 | A | 100 |
| 9 | `jonesdevelopment/sonar/standard` | `jonesdevelopment/sonar` | `standard` | 128×128 | A | 100 |
| 10 | `jonesdevelopment/sonar/legacy` | `jonesdevelopment/sonar` | `legacy` | 128×128 | A | 100 |
| 11 | `jonesdevelopment/sonar/complex` | `jonesdevelopment/sonar` | `complex` | 128×128 | A | 100 |
| 12 | `just-captcha/ProstoCaptcha/map` | `just-captcha/ProstoCaptcha` | `map` | 128×128 | A | 100 |
| 13 | `laforetbrut/are-you-sure/code` | `laforetbrut/are-you-sure` | `code` | 480×270 | A | 100 |
| 14 | `ringoame196-s-mcPlugin/ReproductionCAPTCHA/map` | `ringoame196-s-mcPlugin/ReproductionCAPTCHA` | `map` | 128×128 | A | 100 |
| 15 | `GalleryCaptcha/ru-web` | `GalleryCaptcha` | `ru-web` | 150×90 | A | 100 |
| 16 | `GalleryCaptcha/ru-symbols` | `GalleryCaptcha` | `ru-symbols` | 250×150 | A | 100 |
| 17 | `BotFilter/map` | `BotFilter` | `map` | 128×128 | A | 100 |
| 18 | `CaptchaVerifyZ/map` | `CaptchaVerifyZ` | `map` | 128×128 | A | 100 |
| 19 | `LimboFilter/symbols` | `LimboFilter` | `symbols` | 128×128 | A | 100 |
| 20 | `jSdCool/minecaptcha/text` | `jSdCool/minecaptcha` | `text` | 550×356 | A | 100 |

### Group B — OCR + a solver step (11 types, 1100 images)

The same recogniser reads the text; a conversion produces the answer.

| # | Plugin / captcha | Plugin field | Captcha | Canvas | Group | Samples | What the solver does |
|---|---|---|---|---|---|---|---|
| 21 | `LagBug/XProtect/reverse` | `LagBug/XProtect` | `reverse` | 582×136 | B | 100 | reverse the string |
| 22 | `GalleryCaptcha/ru-numberword` | `GalleryCaptcha` | `ru-numberword` | 250×150 | B | 100 | Russian words → digits (40-line lexicon) |
| 23 | `GalleryCaptcha/ru-numberword-caption` | `GalleryCaptcha` | `ru-numberword-caption` | 250×150 | B | 100 | same |
| 24 | `LimboFilter/map` | `LimboFilter` | `map` | 128×128 | B | 100 | same, per-line block |
| 25 | `LagBug/XProtect/equation` | `LagBug/XProtect` | `equation` | 478×114 | B | 100 | evaluate the expression |
| 26 | `FeelingAlive0/AdvancedCaptcha/math` | `FeelingAlive0/AdvancedCaptcha` | `math` | 300×84 | B | 100 | evaluate the expression |
| 27 | `Mrbysco/Captcha/math` | `Mrbysco/Captcha` | `math` | 520×560 | B | 100 | evaluate the expression |
| 28 | `n1zamu/NCaptcha/anvil` | `n1zamu/NCaptcha` | `anvil` | 420×150 | B | 100 | nothing — the answer is printed twice in ordinary digits (upstream defect, reproduced) |
| 29 | `LagBug/XProtect/gui` | `LagBug/XProtect` | `gui` | 380×260 | B | 100 | nothing, but a 3–20 character string — a different length regime |
| 30 | `Archy-X/Krypton/menu` | `Archy-X/Krypton` | `menu` | 380×346 | B | 100 | same |
| 31 | `Yukun99/Captchas/itemslot` | `Yukun99/Captchas` | `itemslot` | 622×296 | B | 100 | same |

### Group C — not OCR at all (15 types, 1500 images)

Nothing here is a recogniser's job; do **not** put these into a recogniser's training set.

| # | Plugin / captcha | Plugin field | Captcha | Canvas | Group | Samples | Why it is not OCR |
|---|---|---|---|---|---|---|---|
| 32 | `LagBug/XProtect/drop` | `LagBug/XProtect` | `drop` | 590×180 | C | 100 | constant answer (`drop`) — 1 unique answer in 100 samples |
| 33 | `LagBug/XProtect/jump` | `LagBug/XProtect` | `jump` | 430×146 | C | 100 | constant answer (`jump`) |
| 34 | `LagBug/XProtect/sneak` | `LagBug/XProtect` | `sneak` | 438×146 | C | 100 | constant answer (`sneak`) |
| 35 | `LagBug/XProtect/different` | `LagBug/XProtect` | `different` | 398×202 | C | 100 | constant answer — 1 unique answer in 100 samples |
| 36 | `China2B2T/Captcha/wool` | `China2B2T/Captcha` | `wool` | 414×314 | C | 100 | constant answer (`LIME_WOOL`) |
| 37 | `jSdCool/minecaptcha/image` | `jSdCool/minecaptcha` | `image` | 640×398 | C | 100 | the answer is 63–70 characters and is unreadable by construction |
| 38 | `LimboFilter/framed2x2` | `LimboFilter` | `framed2x2` | 256×256 | C | 100 | the answer sits in **rotated** frames — a solver step, not a recogniser's |
| 39 | `LimboFilter/framed3x3` | `LimboFilter` | `framed3x3` | 384×384 | C | 100 | same |
| 40 | `GalleryCaptcha/ru-object-swatch` | `GalleryCaptcha` | `ru-object-swatch` | 250×150 | C | 100 | no text at all — the answer is a colour name (5 classes) |
| 41 | `LagBug/XProtect/color` | `LagBug/XProtect` | `color` | 420×92 | C | 100 | the answer is a colour name, 11 unique answers |
| 42 | `Joey61021/captcha/colorgui` | `Joey61021/captcha` | `colorgui` | 186×104 | C | 100 | the answer is a colour name, 6 unique answers |
| 43 | `Z4OLLIEZ4/reCaptcha/captchasx` | `Z4OLLIEZ4/reCaptcha` | `captchasx` | 186×122 | C | 100 | the answer is a colour name, 13 unique answers |
| 44 | `LagBug/XProtect/slot` | `LagBug/XProtect` | `slot` | 470×183 | C | 100 | the answer is a slot number, 8 unique answers |
| 45 | `CaptchaGUI/clickblock` | `CaptchaGUI` | `clickblock` | 186×68 | C | 100 | the answer is a slot index; 100 samples over **7** unique images (93 duplicates) |
| 46 | `FeelingAlive0/AdvancedCaptcha/button` | `FeelingAlive0/AdvancedCaptcha` | `button` | 730×84 | C | 100 | 18–27 characters, a different regime — deferred |

### 4.1 Measured facts about the 46 types

| Measurement | Value |
|---|---|
| Types / labelled images | 46 / 4600 |
| Samples per type | exactly 100 in every one of the 46 types |
| `dataset/out` | 34 types, 3400 PNGs, 3400 label rows, 18 `owner/repo` plugin dirs |
| `dataset/out_ru` | 12 types, 1200 PNGs, 1200 label rows, 9 plugin dirs (5 of them carry samples) |
| Types with a `roi` band | **29** (28 on all 100 samples, `haq/mapcha/map` on 99) |
| Rows with `roi = null` | 1701 (= 17 types × 100 + 1) |
| Types with `text != answer` | **9** (3 arithmetic + 5 Russian number words + `LagBug/XProtect/reverse`) |
| Types with a constant answer (1 unique answer / 100) | **5** (`drop`, `jump`, `sneak`, `different`, `wool`) |
| Types containing Cyrillic | **8** (`ru-numberword`, `ru-numberword-caption`, `ru-symbols`, `ru-object-swatch`, `LimboFilter/{map,symbols,framed2x2,framed3x3}`) |
| Reference images in `real_shots/` | **517** (third-party screenshots — not published) |
| PNG files in the two trees | 5840 (4600 labelled + 517 references) |
| Tree sizes | `dataset/out/` 34.2 MB · `dataset/out_ru/` 44.8 MB |

---

## 5. Commands

> **Machine note first.** There is **no `pwsh` binary** on this machine — only Windows PowerShell 5.1.
> **Executing a `.ps1` file is blocked** ("AuthorizationManager check failed"), even for a script inside
> the workspace, and even with an execution-policy flag. Do **not** try to run `build.ps1`; run its
> logic **inline** in the tool call (the inline form is given below).

### 5.1 Java: compile, generate, validate

```powershell
# --- generator 1 (the 18 upstream plugins) ---
$java = if ($env:JAVA_HOME) { "$env:JAVA_HOME\bin" } else { "java" }   # JDK 21 in PATH or JAVA_HOME
$core = Get-ChildItem -File dataset\generator\dev\captha\*.java | % FullName
& "$java\javac.exe" -encoding UTF-8 -d build\classes -sourcepath dataset\generator $core (Get-ChildItem -Recurse -Filter *.java dataset\generator | % FullName)
& "$java\java.exe" "-Djava.awt.headless=true" -cp build\classes dev.captcha.Gen      dataset\out    100
& "$java\java.exe" "-Djava.awt.headless=true" -cp build\classes dev.captcha.Validate dataset\out
& "$java\java.exe" "-Djava.awt.headless=true" -cp build\classes dev.captcha.Stats    dataset\out\LagBug\XProtect\code\001.png

# --- generator 2 (the catalogue families + the identified plugins) ---
& "$java\javac.exe" -encoding UTF-8 -d build\classes_ru -sourcepath dataset\generator_ru $core (Get-ChildItem -Recurse -Filter *.java dataset\generator_ru | % FullName)
& "$java\java.exe" "-Djava.awt.headless=true" -cp build\classes_ru dev.captcha.Gen      dataset\out_ru 100
& "$java\java.exe" "-Djava.awt.headless=true" -cp build\classes_ru dev.captcha.Validate dataset\out_ru
```

`build.ps1` does exactly this, with `-Count` (default 100), `-Out`, `-OutRu`, `-JavaHome` and `-SkipRu`.
Its logic, if you ever need it inline, is: compile `generator` → `Gen` → `Validate` → compile
`generator_ru` → `Gen` → `Validate`. **It does not call `tools/restore_real_shots.py`** — after a
manual clean of a plugin folder, restore the references yourself (see §6).

| CLI | Purpose |
|---|---|
| `dev.captcha.Gen <outDir> <count>` | Renders every generator `count` times, writes the PNGs, one `labels.jsonl` per type, and `<outDir>/index.html`. |
| `dev.captcha.Validate <outDir>` | Per-type `n / minColors / blank / dupes / labels` table. |
| `dev.captcha.Stats <png\|dir>` | Colour histogram of a PNG, or of the first PNG in a directory. |

### 5.2 The dataset checkers

```powershell
python tools\check_labels_and_roi.py dataset\out_ru     # labels re-derived, bands inside the canvas
python tools\check_labels_and_roi.py dataset\out
python tools\check_band_vs_answer.py dataset\out_ru     # per type: band carries the answer, the text, or nothing
python tools\check_bands_against_labels.py dataset\out dataset\out_ru
python tools\summarise_roi.py dataset\out_ru
python tools\audit_sources.py dataset\out_ru            # the source() audit trail
python tools\count_colors.py dataset\out_ru
python tools\restore_real_shots.py                      # put the 517 references back after a regen
```

The system Python (3.14.5) has `pillow 12.2.0`, `numpy 2.4.6` and `transformers 5.19.0`, so these run
as-is.

### 5.3 The benchmarks

```powershell
python bench\bench_hf.py        # 10 HF image-to-text models -> reports/bench_results.json
python bench\bench_onnx.py      # raw ONNX captcha models   -> reports/bench_results_onnx.json
python bench\bench_others.py    # EasyOCR, Graf-J, Florence   -> reports/bench_results_others.json
python bench\show_bench.py      # pretty-print reports/bench_results.json
```

`bench_hf.py` skips a model that is already in the results JSON, and appends after every model, so a
run is resumable. `bench_hf.py` accepts model ids as `sys.argv[1:]`.

### 5.4 The site analysis

```powershell
python tools\match_site_to_dataset.py    # nearest dataset match per site image
python tools\cluster_site_captchas.py     # visual families of the 525-image catalogue
```

### 5.5 Training

```powershell
# the CUDA build lives in its own venv; the system python is untouched
.venv-gpu\Scripts\python.exe train\train.py --quick --epochs 150

# the real thing: every training type, four held out
.venv-gpu\Scripts\python.exe train\train.py --charset latin --trees both --epochs 80 --batch-size 32 `
    --workers 6 --lr 1e-3 --val-types "haq/mapcha/map" "LagBug/XProtect/sneak" "CaptchaVerifyZ/map" "jSdCool/minecaptcha/text"

# continue where it stopped
.venv-gpu\Scripts\python.exe train\train.py --resume
```

The flags, as implemented in `train/train.py`:

| Flag | Default | Meaning |
|---|---|---|
| `--quick` | off | the six-type smoke run, two of them held out |
| `--epochs N` | 60 | |
| `--batch-size N` | 32 | |
| `--lr`, `--head-lr` | 3e-3, `lr/10` | OneCycleLR, 5 % warmup |
| `--glyph-height N` | 32 | the **glyph**, not the frame |
| `--charset latin\|cyrillic` | `latin` | Model A = 63 classes, Model B = 34 |
| `--types`, `--val-types` | — | substring filters on the type id |
| `--limit-per-type N` | — | |
| `--trees out\|out_ru\|both` | `both` | |
| `--allow-no-roi` | off | also train on types without a band (ill-posed task) |
| `--exclude-types` | — | on top of the built-in 13 |
| `--no-augment` | off | |
| `--save-every N`, `--log-every N` | 200, 50 | |
| `--out DIR` | `train/run` | checkpoints + `val_report.json` |
| `--resume` | off | picks up the newest `step_*.pt` |
| `--device auto\|cuda\|cpu\|cuda:0` | `auto` | |
| `--amp` / `--no-amp` | amp on | mixed precision on the GPU |
| `--workers N` | 0 | dataloader workers — the image decoding is the bottleneck |
| `--threads N`, `--seed N` | 0, 1234 | |

Two types are dropped from every run automatically and printed: a type with **no band** (the
ill-posed "find the string somewhere in this picture" task) and a type whose label does not survive the
charset (poison: an empty CTC target).

### 5.6 The HF export

```powershell
.venv-gpu\Scripts\python.exe train\export_hf.py --checkpoint train\run\ckpt\step_0001234.pt --out build\hf_export --charset latin
```

**Never executed.** `CONTINUE.md` records that the agent that wrote it was stopped.

### 5.7 Environment warnings (this machine)

| | |
|---|---|
| **No `pwsh`** | Only Windows PowerShell 5.1. Use `powershell`-style syntax; never invoke `pwsh`. |
| **`.ps1` execution is blocked** | "AuthorizationManager check failed", even for a workspace script and even with an execution-policy flag. Run the logic **inline** in the tool call. This affects `build.ps1`, `tools/sg.ps1`, `<gallery-refs>/download.ps1`, `<gallery-refs>/montage.ps1` and the `research/*.ps1` probes. |
| **Java 21** | JDK 21 in `PATH` (`java -version` → 21) or the `JAVA_HOME` variable. |
| **GPU** | NVIDIA GeForce GTX 1080 Ti, 11.8 GB, sm_61. The system Python carries `torch 2.14.1+cpu`; the CUDA build is in `.venv-gpu` (`torch 2.14.1+cu126`, because the newer wheels dropped the sm_61 kernels). Verified: `torch.cuda.get_arch_list()` contains `sm_61`, `torch.cuda.is_available()` is True. The system environment is untouched. |
| **`ddgs` and Cyrillic** | Set `$env:PYTHONIOENCODING="utf-8"` first, or it crashes on Cyrillic output. |
| **Web search** | The built-in `web_search` tool is disabled in this setup. Use the **`web-search` skill** (`ddgs`). |
| **GitHub API** | 60 unauthenticated requests/hour — batch the calls and sleep between them. |
| **Fonts** | Java resolves logical families through the platform font configuration, so the generated pixels are **not reproducible on another machine or JDK** (open finding N14). |

---

## 6. Gotchas that cost the project real time

These are the ones the repository already documents. Read them before you "fix" anything.

### 6.1 The CTC all-blank plateau — a flat loss is not a bug

CTC sits in an **all-blank plateau** for thousands of steps: the loss sits at `ln(63) = 4.14` (the model
emitting nothing but blanks) and creeps down very slowly.

| Run | Result |
|---|---|
| 4 samples, 300 steps | loss 12.76 → **0.001**, argmax gives the right letters |
| 600 images, 152 steps | loss stuck at **4.12**, accuracy 0.000 — **not a bug** |
| 600 images, 2850 steps | loss **0.57** — the plateau is over |

**Do not read a flat loss as a bug before you have run a few thousand steps.** Before "fixing" the
model, wait for CTC to leave the plateau.

### 6.2 The band matters more than the model

On the first real run, a held-out type (`InstantlyMoist/Captcha/textcaptcha`) scored **accuracy 1.000,
CER 0.000** while another held-out type (`haq/mapcha/map`) scored **0.000** — and the only difference
was that the first one's `roi` pointed at the answer and the second one's did not exist yet, so the
model was shown a whole map with a title, two counters and the code, and it read the wrong line.

**A missing or wrong band silently destroys a type, and the validator does not catch it.**
`dev.captcha.Validate` only checks blanks, duplicates and the *number* of label lines (open finding
N12). The standing checkers are `tools/check_labels_and_roi.py` and `tools/check_band_vs_answer.py`.

**The rule the bands were computed with: a band that does not fit inside the frame is not a band** —
`roi()` returns `null`, not a rectangle that holds only part of the answer.

Two bugs came out of this area and cost the most:

1. **`McUi.drawColored` did not move the pen.** Every coloured run of a string was drawn on top of the
   previous one, and all the chat scenes of the dataset were an unreadable mess. The EasyOCR baseline
   of 0.115 was measured on garbage. Fixed: the pen follows the measured run width, `&l` and `&r` are
   handled. From the same fix came two more changes without which the dataset would be unusable:
   `McUi.scene` now widens the chat frame so the plugin's message fits on one line (the XProtect frame
   grew from 420 to ~580 px — before that the answer was not in the picture at all), and
   `McUi.inventory` now fits the window title into the panel.
2. **The `roi` bands were computed from the broken pen.** While the pen did not move, the text sat in
   one place; after the fix it moved and the bands stayed stale. For `LagBug/XProtect/drop` the band
   pointed at `rote` — the tail of the prefix "XProtect" — instead of the answer `drop`. Such a label
   is **unfittable by construction**, and it alone dragged the loss down. The bands were recomputed —
   twice — from the fixed pen.

### 6.3 No `pwsh`, no `.ps1` execution

See §5.7. Run the logic inline. Do not waste a turn on it.

### 6.4 The `real_shots/` reference images must never be deleted

They are the ground truth for the reconstructions. `Gen` writes into the same tree, and a clean rebuild
of a plugin folder wipes them. After a regeneration, put them back:

```powershell
python tools\restore_real_shots.py
```

**`build.ps1` does not call this script** (open finding N13) — it has to be run by hand.

### 6.5 Upstream defects are reproduced, never "fixed"

A charset that makes a letter unreachable, a dead kick branch, a substring-match verification, a title
bar that prints the answer — reproduce it and document it. A solver is only useful against the plugins
it will meet in production. The table is in `docs/UPSTREAM_DEFECTS.md`.

The licensing vocabulary: `Faithful` = a line-by-line re-implementation from upstream (only where the
licence permits). `Clean-room` = the algorithm was read from upstream and rewritten independently: no
code, comments, identifiers or copyright headers carried over. `Reconstructed` = no upstream source was
found; the generator is driven by the reference screenshots in `real_shots/` and says so in its
javadoc and in `source()`. The table of the reproduced defects is in `docs/UPSTREAM_DEFECTS.md`.

### 6.6 The dataset is an artefact, not a function

The PNGs are generated deterministically, but **the fonts depend on the machine** (logical AWT
families). So: **generate the dataset once, on one machine, and train from that folder.** Do not
regenerate it for every run — a "continuation" would then see different pixels. Regenerating costs
about a minute, so the cheapest way to continue is often to start over.

### 6.7 Never fabricate a source location

If a plugin's upstream source cannot be found, say so plainly and reconstruct the captcha from the
reference screenshots in `real_shots/`, marking it clean-room / reconstructed. Do not invent a
GitHub URL or a method name to make a record look complete. `source()` and `labels.jsonl` are the audit
trail; `tools/audit_sources.py` prints it.

### 6.8 Never edit a measured result

`reports/` holds measured results. Do not edit a result JSON to make a model look better — re-run the
benchmark instead.

### 6.9 The dataset has no image-aware verification

None of the automation behind this dataset can look at an image. Every verification pass was
histogram- and pixel-level: colour counts, distinct-colour sets, duplicate digests, and constants read
off the source. That catches a blank render, a missing noise pass, an unreachable character or a wrong
canvas size — and it **cannot** tell you whether a sample looks right. Eyeballing
`dataset/out/index.html` and `dataset/out_ru/index.html` is an expected part of using this dataset.

---

## 7. What is NOT here

Documented in the repository, but not built. Do not write a report claiming any of these exist.

| Missing thing | State | Why |
|---|---|---|
| **Hugging Face export / release** | **Not started.** `train/export_hf.py` exists (72 KB) and parses cleanly, but it was **never executed** — the agent that wrote it was stopped. There is no `reports/HF_RELEASE.md` and no `requirements-train.txt`. | `HANDOVER.md` §7 "Not started"; `CONTINUE.md` step 6–7 |
| **Per-family dataset repos** | **Not started.** A single monolithic dataset must not be published: sonar, China2B2T and AnBot are GPL-3.0, LimboFilter is AGPL-3.0, three plugins have no licence, the rest are MIT/Apache/BSD. Each row needs a `mode` (faithful / clean-room / reconstructed) and the upstream licence. Whether GPL reaches the rendered pictures is still open (B7 in `docs/adr/0002-recogniser-architecture-and-data.md`). | `HANDOVER.md` §7, `CONTINUE.md` step 6 |
| **`dataset/out_ru/Captcha/`** | **Evidence only.** No generated samples; `real_shots/README.md` only. | The name is ambiguous: six SpigotMC resources carry it, and only one of them draws an image at all. |
| **`dataset/out_ru/SmartCaptcha/`** | **Evidence only.** `README.txt` + `real_shots/README.md`, no PNGs. | The plugin renders **no image** — a GUI captcha. |
| **`dataset/out_ru/WeatherActionCaptcha/`** | **Evidence only.** `real_shots/README.txt` + 2 PNG frames from a video. | It renders no image. |
| **The V6 150×90 web captcha has no single generator** | `GalleryCaptcha/ru-web` is a **reconstruction** of the style from the 70 V6 references, not a reimplementation of an upstream algorithm. The 70 references are a corpus of real web captchas. There is no plugin behind them. | `AGENTS.md` §6 "In progress"; `HANDOVER.md` §1.2 |
| **The V8 photo object captcha is not generated** | Only the **flat colour** variant exists (`GalleryCaptcha/ru-object-swatch`). The photo variant's source photographs could not be recovered with reliable category labels, and inventing labels would be fabricating ground truth. | `AGENTS.md` §6 "In progress" |
| **`PP-OCRv6_medium_rec` in the benchmark** | Not present. It is the strongest ready-made model for this task (19 M, Apache-2.0, 83.2 % W-Avg) and its absence makes the "we are better than everything" claim incomplete. | `HANDOVER.md` §7 M0 |
| **A cross-machine reproducible dataset** | Not possible without a pinned font list. | open finding N14 |
| **A `Validate` that catches label bugs** | `dev.captcha.Validate` only counts labels; the label-level checks live in two separate Python tools. | open finding N12 |
| **`build.ps1` calling the restore script** | Not done — run `tools/restore_real_shots.py` by hand after a clean rebuild. | open finding N13 |
| **A 4-fold type-held-out benchmark result** | Not run. The split logic exists (`train/train.py`), the numbers do not. | `HANDOVER.md` §7 M4 |
| **`train/run/`** | Does not exist — no training run has been left in the repository. | measured 2026-10-21 |

---

## 8. Start here (for a brand-new agent)

### 8.1 The reading order

1. **`AGENTS.md`** — the rules: the orchestrator role (§0), the project, the layout, the commands, the
   house rules for generators (§5), the current state (§6), the environment notes (§7), the safety and
   honesty rules (§8).
2. **`HANDOVER.md`** — the state: what exists, **what to train on and what to leave out** (§2 — the
   A/B/C split), the three decisions that define the model (§3), the measured journal (§6.5), and the
   order of work (§7).
3. **This file** (`agents/INDEX.md`) — where everything is, the dataset contract, the measured type
   table, the commands, the gotchas.
4. **The file you were asked to change** — and only that one (see `agents/AGENT_LOG.md` for who owns
   what).

### 8.2 The hard rules

- **The main agent is an orchestrator only.** It writes the task, accepts and checks the result,
  resolves conflicts between agents (who owns which file), rebuilds the dataset, commits and answers the
  user. Substantive work goes to a subagent with a complete brief.
- **One file — one agent.** Two agents editing one file overwrite each other; this already happened
  with `dataset/generator_ru/`. The ownership is fixed **before** the task is handed out.
- **Never fabricate a source location.** No invented GitHub URL, no invented method name.
- **Never edit a measured result JSON.** Re-run the benchmark instead.
- **Never delete the `real_shots/` reference images.**
- **Never "fix" an upstream defect** in a generator — document it.
- **Do not modify any file you do not own**, and do not commit. The main agent commits.
- **Report honestly**: what you verified, what you did not, what is broken. "Unverified" is a valid
  answer; a guess is not.
- **The dataset and the `real_shots/` trees are precious.** Do not delete, move or rewrite anything
  under `dataset/out/` or `dataset/out_ru/`.

### 8.3 Before you hand a task to a subagent

Check that the previous work is in place: does the generator tree compile, does `dev.captcha.Validate`
pass, is no agent left half-way through an edit? An agent stopped mid-edit leaves the tree inconsistent
— compilation catches it.

---

## 9. Discrepancies (docs vs measured reality)

Everything here was measured on 2026-10-21 and is **not** fixed in the source documents — the proposed
patches are in §10.

| # | Document claim | Measured reality | Severity |
|---|---|---|---|
| 1 | `HANDOVER.md` §1.1 and `AGENTS.md` §6: "4600 labelled images, 46 types, 100 samples per type" | **Correct.** 3400 + 1200 = 4600; 34 + 12 = 46 types; every type has exactly 100 PNGs and 100 label rows. | — |
| 2 | `HANDOVER.md` §1.1: "1240 real reference images" | **Correct.** 1240 PNGs in the `real_shots/` folders. | — |
| 3 | `HANDOVER.md` §3.1 / `README.md`: "29 of the 46 types carry a band", "17 types have `roi = null`" | **Correct.** 29 types carry a band (28 on all 100 samples, `haq/mapcha/map` on 99 of 100); 1701 rows have `roi = null`. | — |
| 4 | `AGENTS.md` §3 / `README.md`: "`answer` differs from `text` in exactly two families" | **Right at family level, incomplete at type level.** 8 concrete types have `text != answer`: 3 arithmetic + **5** Russian-number-word types — the framed types `LimboFilter/framed2x2` and `framed3x3` carry the Russian words inside rotated frames and are not named anywhere. | low |
| 5 | `AGENTS.md` §4: "4 benchmark harnesses" | **Six files** in `bench/`: `bench_hf.py`, `bench_onnx.py`, `bench_others.py`, `bench_easyocr.py`, `show_bench.py`, `test_models.py`. The §4 command list names only four of them. | low |
| 6 | `AGENTS.md` §4 / `README.md` §"Build and run": the javac command compiles `dataset\generator\dev\captha\*.java` **plus** all `*.java` under `dataset\generator` | `dataset\generator` contains **no** `*.java` outside `dev/captcha/`, so the second part of the command is a no-op there. It is **not** a no-op for `generator_ru`, which has no core files of its own and relies on the shared core from `dataset/generator`. The `AGENTS.md` command for generator 2 does include it — correct. | low |
| 7 | `HANDOVER.md` §1.1: "the trainer prints what it dropped" — `train.py` has `--require-roi` mentioned in `CONTINUE.md` | **The flag does not exist.** `CONTINUE.md` says "Сейчас исключены флагом `--require-roi`"; the real flag is `--allow-no-roi` (default **off**, i.e. types without a band are excluded by default). | medium |
| 8 | `reports/subagent_results.json`: `LagBug/XProtect/different` `count: 30` | The shipped tree has **100** samples. The JSON is stale from an earlier stage of the work. | low |
| 9 | `HANDOVER.md` §3.4: "Model B — 34 classes (blank + 33 Cyrillic)" | `train/captcha_crnn.py` defines `CYRILLIC` = 33 letters and `Charset.num_classes = len + 1` = **34** for the Cyrillic model — but `CONTINUE.md` §"what is broken" item 4 says Model B is **44 classes** (blank + 33 letters + 10 digits), because `LimboFilter/symbols` answers contain digits. The **code** produces 34 classes; the digits are silently dropped from the label. | **medium — a real inconsistency between the code and the plan** |
| 10 | `HANDOVER.md` §1.1: "`tools/check_labels_and_roi.py` — 0 problems" | The checker exists and the tree passes it (the arithmetic "mismatches" it reports are by design — 300 rows in the three arithmetic types). But the **colour-level** band rule is not in `tools/` at all; it lives only in `build/scratch/roilabel.py`. Open finding N12. | medium |
| 11 | `AGENTS.md` §4: `python bench\bench_hf.py` is listed as the HF harness | `bench_hf.py`'s own `predict_trocr` calls `load_image(p)` **without** the `roi`, so the HF/TrOCR path is measured on the **whole frame**, while `bench_others.py` / `bench_onnx.py` use `load_band` (cropped). `CONTINUE.md` claims "the benchmark now crops by the `roi` band". The stored `bench_results.json` (acc 0.0769) was produced by the uncropped path. | **medium — the baselines are not all measured on the same input** |
| 12 | `AGENTS.md` §6 "Not started": "checkpoint export" | `train/export_hf.py` exists (72 369 bytes), parses cleanly, and documents its design decisions in detail. It was **never executed**. "Not started" overstates; "written but unverified" is accurate. | low |
| 13 | `<gallery-refs>/`: "525 images across 11 API-version sections" | **525 images in 11 section directories — but `s09_API_V7_Пазл_капчи` is empty (0 files).** Ten sections hold images. | low |
| 14 | `README.md` §"Dataset at a glance": "`dataset/out/` tree 33.1 MB" | **34.2 MB** measured on 2026-10-21 (the PNG payload alone is 32.4 MB, so the rest is consistent — the tree grew slightly with the last regeneration). | trivial |
| 15 | `README.md` §"Plugins covered": 18 plugins, 34 types | **Correct** — 18 `owner/repo` dirs, 34 type dirs, 100 samples each. | — |
| 16 | `AGENTS.md` §6: "517 reference images in the `real_shots/` folders" | **Correct**, but three of the eight `real_shots/` folders hold **0** PNGs (`GalleryCaptcha`, `Captcha`, `CaptchaGUI`, `LimboFilter` top level, `SmartCaptcha`); the LimboFilter references live in its `framed2x2/` and `framed3x3/` sub-folders. | low |
| 17 | `CONTINUE.md`: "`dev.captcha.Validate`: 0 remarks on both trees" | Not re-verified in this session (running Java is out of scope for the index task). The claim is from the repository's own history, not from a measurement taken here. | unverified |

---

## 10. Proposed changes to `AGENTS.md` / `HANDOVER.md` (NOT applied)

These are **proposals only**. The index agent owns `agents/` and did not touch any other file.

**`AGENTS.md`**

1. §4: add the two missing benchmark commands (`python bench\bench_easyocr.py`, `python bench\test_models.py`)
   or change "4 benchmark harnesses" to "6 scripts in `bench/`".
2. §3, dataset contract: name the framed types explicitly in the `answer` vs `text` sentence —
   "…differs in exactly two families (the Russian number words — including the two framed types, where
   the words sit in rotated frames — and the arithmetic types)".
3. §4 / `bench/bench_hf.py`: either crop to `roi` inside `predict_trocr` (so the HF baselines are
   measured on the same input as the other harnesses) or state in `bench_hf.py` and in
   `reports/CAPTCHA_OCR_REPORT.md` that the TrOCR numbers are whole-frame numbers.
4. §6 "Not started": rephrase to "the export script exists (`train/export_hf.py`) but was never
   executed; no HF release, no per-family dataset repos".
5. §7: add "the `train/` tree contains an unexecuted `export_hf.py`" to the environment notes, so a
   fresh agent does not mistake it for a working feature.

**`HANDOVER.md`**

6. §1.1: replace the `--require-roi` reference with `--allow-no-roi` (the real flag, default off), or
   drop the flag name.
7. §3.4: reconcile the Model B class count — the code builds **34** classes
   (`CYRILLIC` = 33 letters + blank) while the plan says 44 (with digits). Either extend `CYRILLIC` to
   include `0-9` or state explicitly that the digits of `LimboFilter/symbols` are dropped today.
8. §1.1: note that the colour-level band rule is **not** in `tools/` (it is `build/scratch/roilabel.py`)
   and that `dev.captcha.Validate` still cannot catch label bugs (finding N12).
9. §2: add a line stating that the group assignment was **re-verified against the shipped
   `labels.jsonl`** on 2026-10-21: 20 / 11 / 15 types, 2000 / 1100 / 1500 images, 8 types with
   `text != answer`, 5 types with a constant answer.
10. §6.5: add the index agent's session to the journal, and point at `agents/INDEX.md`,
    `agents/AGENT_LOG.md` and `agents/INDEX.json` from §8 "Где что лежит".

---

*Index generated 2026-10-21 21:31 (Asia/Yekaterinburg, +05:00) by the index agent. Every number in
this file was measured on this machine; see §9 for the ones that disagree with the other documents.*
