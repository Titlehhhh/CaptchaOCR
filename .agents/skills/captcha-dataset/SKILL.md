---
name: captcha-dataset
description: Use when building, regenerating, validating or inspecting the CaptchaOCR captcha dataset — compiling the Java 21 generators, running dev.captcha.Gen / dev.captcha.Validate, checking labels and text bands with the Python checkers, or restoring the real_shots reference images after a regeneration. Carries the inline-PowerShell commands (the .ps1 build script cannot be executed on this machine), the dataset path contract, and the band rule.
---

# CaptchaOCR dataset — build, validate, inspect

The dataset is a **generated artefact**. The PNGs depend on the fonts of *this* machine (Java resolves
logical AWT families through the platform font configuration), so **generate once, on this machine, and
train from that folder**. Regenerating for every run means a "continuation" sees different pixels.

## Machine facts (verified on this box)

- **Java 21**: `I:\ForAndroid\Java\21` → `bin\javac.exe`, `bin\java.exe`. `Test-Path` it before use.
- **No `pwsh`** — Windows PowerShell 5.1 only. Use `powershell`-style syntax; never invoke `pwsh`.
- **Executing a `.ps1` file is blocked** ("AuthorizationManager check failed"), even for a file in the
  workspace and even with an execution-policy flag. **Never run `build.ps1`** — run the equivalent logic
  inline in the tool call (the block below is exactly what `build.ps1` does).

## The path contract

```
dataset/out/<owner>/<repo>/<captchaType>/NNN.png     001.png .. 100.png
dataset/out/<owner>/<repo>/<captchaType>/labels.jsonl
dataset/out_ru/<Plugin>/<captchaType>/NNN.png        001.png .. 100.png
dataset/out_ru/<Plugin>/<captchaType>/labels.jsonl
```

`dataset/out/` uses the upstream `owner/repo` string (so the plugin is **two** path levels and the type is
the third). `dataset/out_ru/` uses **flat** plugin names. One `labels.jsonl` per type, one JSON object per
sample: `file`, `plugin`, `captcha`, `answer` (what the player types), `text` (what is **drawn**), `prompt`,
`roi`, `width`, `height`, `source`.
## Build (inline — `build.ps1` cannot be executed here)

```powershell
$java = "I:\ForAndroid\Java\21\bin"
$core = Get-ChildItem -File dataset\generator\dev\captha\*.java | % FullName

# --- tree 1: the 18 upstream plugins -> dataset/out ---
& "$java\javac.exe" -encoding UTF-8 -d build\classes -sourcepath dataset\generator $core (Get-ChildItem -Recurse -Filter *.java dataset\generator | % FullName)
& "$java\java.exe" "-Djava.awt.headless=true" -cp build\classes dev.captcha.Gen      dataset\out    100
& "$java\java.exe" "-Djava.awt.headless=true" -cp build\classes dev.captcha.Validate dataset\out

# --- tree 2: the catalogue families + identified plugins -> dataset/out_ru ---
& "$java\javac.exe" -encoding UTF-8 -d build\classes_ru -sourcepath dataset\generator_ru $core (Get-ChildItem -Recurse -Filter *.java dataset\generator_ru | % FullName)
& "$java\java.exe" "-Djava.awt.headless=true" -cp build\classes_ru dev.captcha.Gen      dataset\out_ru 100
& "$java\java.exe" "-Djava.awt.headless=true" -cp build\classes_ru dev.captcha.Validate dataset\out_ru
```

`Gen <outDir> <count>` renders every generator `count` times, writes the PNGs, one `labels.jsonl` per type
and `<outDir>/index.html`. `Validate <outDir>` prints the per-type `n / minColors / blank / dupes / labels`
table. `Stats <png|dir>` prints a colour histogram. All three are headless. `index.html` is the intended
review surface: the automation cannot look at an image, so eyeballing the contact sheet is part of using
the dataset.

## The checkers

```powershell
python tools\check_labels_and_roi.py dataset\out_ru   # labels re-derived, bands inside the canvas
python tools\check_labels_and_roi.py dataset\out
python tools\check_band_vs_answer.py dataset\out_ru   # per type: band carries answer / text / nothing
python tools\check_bands_against_labels.py dataset\out dataset\out_ru   # add --verbose for details
```

- `check_labels_and_roi.py` — the main checker. The path argument is optional (it defaults to
  `dataset/out_ru`). It ends with `RESULT: OK` or `RESULT: <-- CHECK` and exits non-zero on a problem.
- `check_band_vs_answer.py` — the path argument is **required**. One row per type: `n`, `band`, whether
  `text == answer`, and a note. Types with no band are reported as *not a recogniser's training target*.
- `check_bands_against_labels.py` — takes one or more roots, `--verbose` for per-sample detail.

## Restore the reference images after a regeneration

```powershell
python tools\restore_real_shots.py
```

`Gen` writes into the same tree, so a clean rebuild of a plugin folder **wipes the `real_shots/`
reference images** — the ground truth for the reconstructions. **`build.ps1` does not call this script**;
it has to be run by hand after every regeneration. Never delete `dataset/out_ru/*/real_shots/`.

## The band rule

**A band that does not fit inside the frame is not a band.** `roi()` returns `null` rather than a
rectangle that holds only part of the answer. A *wrong* band is worse than no band: the label cannot be
fitted, the loss never comes down, and `dev.captcha.Validate` does not catch it — the Python checkers do.

`text != answer` in exactly **8 of the 46 types**: the Russian number words (`GalleryCaptcha/ru-numberword`,
`GalleryCaptcha/ru-numberword-caption`, `LimboFilter/map`, and the same words inside the rotated
`LimboFilter/framed2x2` / `framed3x3` frames) and the arithmetic types (`LagBug/XProtect/equation`,
`FeelingAlive0/AdvancedCaptcha/math`, `Mrbysco/Captcha/math`). A recogniser is trained on `text`; the
conversion to `answer` is the solver's job.

**Generators: faithful over pretty.** Re-implement the upstream algorithm exactly; **upstream defects are
reproduced and documented, never "fixed"**; record the upstream `file#method` in `source()`; a plugin that
renders no image gets no generator. Full rules: `AGENTS.md` §5.

## Never

- run `build.ps1` or any other `.ps1` file;
- delete or overwrite `real_shots/`, `dataset/out/`, `dataset/out_ru/` or `site/captchas/`;
- edit a measured result JSON in `reports/` to make something look better — re-run the measurement;
- invent a GitHub URL or a method name to fill in a `source()` field.