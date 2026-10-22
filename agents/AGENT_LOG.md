# AGENT LOG — CaptchaOCR

The index of the agents that worked in this repository, their areas of ownership, and the protocol the
main orchestrator follows.

Companion files: [`agents/INDEX.md`](INDEX.md) (where everything is),
[`agents/INDEX.json`](INDEX.json) (the machine-readable index).

This file is **append-only**. It records what an agent was told to do, what it owns, what it returned
and whether the work was accepted. It does not replace the git history — it is the human/agent-readable
index of it.

---

## 1. Protocol for subagents

This is the protocol the **main agent** (the orchestrator) follows when it hands work out, and the
contract every **subagent** must honour.

### 1.1 The main agent is an orchestrator only

The main agent does **not** do the work itself. It does exactly five things:

1. writes the task,
2. accepts and checks the result,
3. resolves conflicts between agents (who owns which file),
4. rebuilds the dataset,
5. commits and answers the user.

A code edit by the main agent on its own is not allowed beyond a few lines. The one documented
exception: an emergency edit to unblock a stuck agent, when it must be stated explicitly in the
message to that agent (the two cases in this repository's history are `McUi.drawColored` and
`TextBand`).

### 1.2 How a subagent is briefed

Every brief must be self-contained — the subagent does not share the orchestrator's context. It must
state, explicitly:

| Element | What it must contain |
|---|---|
| **Goal** | What "done" looks like, in one or two sentences. |
| **Input** | Exactly which files / directories / URLs are the inputs, with paths relative to the repo root. |
| **Ownership** | Which files the agent may write. Anything outside that list is off-limits, explicitly. |
| **Do not touch** | The precious things: `dataset/out/`, `dataset/out_ru/`, `site/captchas/`, the `real_shots/` reference images, the result JSONs in `reports/`, and the files owned by other agents. |
| **Result** | What the agent must return, and in what form. |
| **How to verify** | The exact command that proves the work, and what its output should look like. |
| **Constraints** | The house rules that apply (faithful over pretty, upstream defects are reproduced not fixed, never fabricate a source location, the dataset is an artefact). |
| **Environment** | The machine facts the agent needs (no `pwsh`, `.ps1` execution is blocked, Java 21 at `I:\ForAndroid\Java\21`, the GPU venv at `.venv-gpu`, `PYTHONIOENCODING=utf-8` for `ddgs`). |

Before the brief is handed out, the orchestrator checks that the previous work is in place: does the
generator tree compile, does `dev.captcha.Validate` pass, is no agent left half-way through an edit.
An agent stopped mid-edit leaves the tree inconsistent — compilation catches it.

### 1.3 What a subagent must return

A subagent's final message is the result. It must contain, in this order:

1. **Files touched** — the exact list of paths it wrote, and nothing else. If it wrote a file it was
   not given, it says so explicitly and loudly.
2. **What was verified** — the commands that were run and what they printed. "Compiled clean", "0
   problems", "the band points at the answer for 100/100 samples".
3. **What was NOT verified** — everything the agent could not check, and why. This section must not be
   empty by default; if everything was verified, say so explicitly.
4. **What is broken** — the problems the agent found, including in files it does not own. It does not
   fix another agent's file; it reports it.
5. **Discrepancies** — where the documentation and the measured reality disagree. The agent states
   both numbers and does not silently "fix" the document.

### 1.4 Honest reporting

- **"Unverified" is a valid answer. A guess is not.** If an agent could not measure something, it says
  so and says why.
- **Never fabricate a source location.** If the upstream source cannot be found, say so plainly and
  reconstruct from the reference screenshots, marking it clean-room / reconstructed. No invented GitHub
  URL, no invented method name, to make a record look complete.
- **Never edit a measured result** to make something look better. Re-run the measurement.
- **Report the problem, not just the fix.** A fix without a reproducible command is a claim, not a
  result.
- **Disagreement is data.** If a measurement contradicts a document, the agent reports the
  discrepancy explicitly rather than quietly aligning one to the other.

### 1.5 The ownership rules

- **One file — one agent.** Two agents editing one file overwrite each other; this already happened
  with `dataset/generator_ru/`. Ownership is fixed **before** the task is handed out and written into
  the brief. It is mirrored in §2 below.
- **A subagent must not commit.** The main agent commits. A subagent that commits steals the
  orchestrator's ability to review the diff and to attribute the work.
- **A subagent must not touch a file it does not own**, even to "fix a small typo". It reports the
  problem instead. The only exception is a change explicitly authorised in the brief.
- **The orchestrator resolves ownership conflicts before the next round**, not after.

### 1.6 The result of a round

The orchestrator checks the returned result against the brief, confirms the "what was verified"
commands really were run, and only then records the row in §3 and hands out the next brief.

---

## 2. Ownership table

**Current ownership.** `owned by` is the agent role that owns the area today; `status` is the state of
the work, not of the ownership.

| Area / file | Owner (role) | Status |
|---|---|---|
| `AGENTS.md` | main agent (orchestrator); §0 rewritten this session by the harness agent | maintained; §0 is now the orchestrator contract (MAY/MUST NOT, the 8-part brief, the §0.3 acceptance checklist) |
| `HANDOVER.md` | main agent (orchestrator) | maintained; the state of the project, refreshed at each handover |
| `CONTINUE.md` | main agent (orchestrator) | maintained; the short continuation prompt |
| `README.md` | dataset agent (plugin-by-plugin documentation) | maintained; the upstream-defect table is the sensitive part |
| `build.ps1` | main agent (orchestrator) | maintained; **known gap: it does not call `tools/restore_real_shots.py`** (finding N13) |
| `paths.py` | main agent (orchestrator) | stable; shared by `bench/` and `tools/` |
| `.gitignore` | main agent (orchestrator) | stable |
| `dataset/generator/dev/captcha/Cg.java` | core agent (the shared core) | stable — the interface every type implements |
| `dataset/generator/dev/captcha/Img.java` | core agent | stable |
| `dataset/generator/dev/captcha/McUi.java` | core agent | **historically the hottest file** (the `drawColored` pen bug); shared by both trees |
| `dataset/generator/dev/captcha/Gen.java` | core agent | stable — the reflective registry, the batch runner, `index.html` |
| `dataset/generator/dev/captcha/Stats.java` | core agent | stable |
| `dataset/generator/dev/captcha/Validate.java` | core agent | **known gap: it cannot catch label bugs** (finding N12) |
| `dataset/generator/dev/captcha/gens/XProtect.java` | generator author (LagBug/XProtect) | done — 12 types |
| `dataset/generator/dev/captcha/gens/Sonar.java` | generator author (jonesdevelopment/sonar) | done — 3 types |
| `dataset/generator/dev/captcha/gens/Krypton.java` | generator author (Archy-X/Krypton) | done — 2 types |
| `dataset/generator/dev/captcha/gens/FabricCaptcha.java` | generator author (jSdCool/minecaptcha) | done — 2 types |
| `dataset/generator/dev/captcha/gens/AdvancedCaptcha.java` | generator author (FeelingAlive0/AdvancedCaptcha) | done — 2 types |
| `dataset/generator/dev/captcha/gens/ForgeCaptchas.java` | generator author (laforetbrut/are-you-sure, Mrbysco/Captcha) | done — 2 types |
| `dataset/generator/dev/captcha/gens/GuiChecks.java` | generator author (Yukun99/Captchas, China2B2T/Captcha) | done — 2 types |
| `dataset/generator/dev/captcha/gens/GuiPlugins.java` | generator author (Z4OLLIEZ4/reCaptcha, Joey61021/captcha) | done — 2 types |
| `dataset/generator/dev/captcha/gens/{InstantlyMoist,Minecaptcha,Mapcha,Prosto,AnBot,NCaptcha,ReproCaptcha}.java` | generator author (one plugin each) | done — 1 type each |
| `dataset/generator/dev/captcha/gens/TextBand.java` | core agent | done — the shared text-band helper (patched directly by the main agent once) |
| `dataset/generator_ru/dev/captcha/gens/LimboFilter.java` | research/generator author (the catalogue) | done — 4 types, two measured type profiles |
| `dataset/generator_ru/dev/captcha/gens/RussianCaptcha.java` | research/generator author | done — 2 types (ru-numberword, ru-numberword-caption) |
| `dataset/generator_ru/dev/captcha/gens/WebCaptcha.java` | research/generator author | done — 1 type (ru-web, reconstructed); **open findings N4, N5** |
| `dataset/generator_ru/dev/captcha/gens/ObjectCaptcha.java` | research/generator author | done — 1 type (ru-object-swatch); B2/N6 fixed |
| `dataset/generator_ru/dev/captcha/gens/BotFilter.java` | research/generator author | done — 1 type, pixel-verified against 510 real renders |
| `dataset/generator_ru/dev/captcha/gens/CaptchaVerifyZ.java` | research/generator author | done — 1 type, pixel-identical to the upstream; **open finding N8** |
| `dataset/generator_ru/dev/captcha/gens/Supl1nCaptchaGui.java` | research/generator author | done — 1 type (clickblock); N7 fixed (relabelled clean-room) |
| `dataset/generator_ru/dev/captcha/gens/MapPalette.java` | research/generator author | done — the shared palette, not a type |
| `dataset/out/` | **generated artefact** — owned by the main agent (it regenerates) | generated, 3400 PNGs / 34 types |
| `dataset/out_ru/` | **generated artefact** — owned by the main agent (it regenerates) | generated, 1200 PNGs / 12 types |
| `dataset/out_ru/*/real_shots/` | **precious** — nobody may delete or rewrite them; the main agent restores them via `tools/restore_real_shots.py` | 1240 reference images |
| `dataset/out_ru/Captcha/`, `.../SmartCaptcha/`, `.../WeatherActionCaptcha/` | research agent (evidence only) | documentation and evidence only — no generated samples |
| `bench/bench_hf.py` | benchmark agent | done — 10 HF models, 13 types × 8 |
| `bench/bench_onnx.py` | benchmark agent | done |
| `bench/bench_others.py` | benchmark agent | done — EasyOCR, Graf-J, Florence |
| `bench/bench_easyocr.py` | benchmark agent | done |
| `bench/show_bench.py` | benchmark agent | done |
| `bench/test_models.py` | benchmark agent | done (ad-hoc) |
| `train/captcha_crnn.py` | trainer agent | done — the model, the charset, the dataset, the decoding; **modified this session** (the charset check now looks at more than the first 5 rows of a type) |
| `train/train.py` | trainer agent | done — the loop, the split, the checkpointing, the evaluation; **modified this session** (`select()` no longer crashes without `--val-types`; samples without a band are no longer shown as the whole frame; `--augment-affine` added) |
| `train/export_hf.py` | export agent | **written but never executed** — the agent was stopped |
| `train/README.md` | trainer agent | done |
| `train/run/` | trainer agent | generated output (git-ignored); currently absent |
| `tools/check_labels_and_roi.py` | tools agent | done — the main checker |
| `tools/check_band_vs_answer.py` | tools agent | done |
| `tools/check_bands_against_labels.py` | tools agent | done |
| `tools/check_caption_outside_roi.py` | tools agent | done |
| `tools/check_composite_scale.py` | tools agent | done |
| `tools/audit_sources.py` | tools agent | done |
| `tools/summarise_roi.py` | tools agent | done |
| `tools/measure_glyphs.py` | tools agent | done |
| `tools/count_colors.py` | tools agent | done |
| `tools/restore_real_shots.py` | tools agent | done — **the one script that must be run after a clean rebuild** |
| `tools/match_site_to_dataset.py` | research/tools agent | done |
| `tools/cluster_site_captchas.py` | research/tools agent | done |
| `tools/contact_sheet.py` | tools agent | done |
| `tools/fix_b64.py`, `tools/generate_pdf_html.py` | tools agent | done — the report builder |
| `tools/*.py` (the remaining probes) | research/tools agent | done — one-off site analysis helpers |
| `tools/sg.ps1` | research/tools agent | done but **not executable on this machine** |
| `reports/bench_results*.json` | benchmark agent | **measured results — never hand-edited** |
| `reports/CAPTCHA_OCR_REPORT.md` | benchmark agent | done |
| `reports/SITE_CAPTCHAS.md` | research agent | done |
| `reports/LIMBOFILTER_IDENTIFICATION.md` | research agent | done |
| `reports/RU_PLUGINS_CAPTCHA_VERIFYZ_SMARTCAPTCHA.md` | research agent | done |
| `reports/PUZZLE_OBJECT_FAMILIES.md` | research agent | done |
| `reports/MODEL_PLAN.md` | model-plan agent | done — "partly implemented since" |
| `docs/adr/0001-dataset-is-kept-in-git.md` | reviewer agent (dataset) | done — B1–B7, N1–N16 + a status table |
| `docs/adr/0002-recogniser-architecture-and-data.md` | reviewer agent (model plan) | done |
| `docs/adr/0003-plugin-identification-method.md` | fact-check agent | done — F1–F14, C1–C7 |
| `reports/subagent_results.json` | generator agents | done — **stale** (`different` count 30 vs the shipped 100) |
| `reports/captcha_report.html`, `reports/captcha_pdf_embedded.html`, `reports/image_b64.json` | tools agent | done — generated from the JSONs above |
| `site/captchas/` | research agent | downloaded reference images — **precious** |
| `site/clusters/` | research/tools agent | generated by `cluster_site_captchas.py` |
| `research/` | research agent | the upstream sources, the decompilations, the web-research scratch |
| `build/` | nobody | scratch — javac output + experiments; regenerable |
| `.venv-gpu/` | nobody | the CUDA environment; regenerable with one command |
| `agents/INDEX.md`, `agents/INDEX.json` | index agent | done (this session) |
| `agents/AGENT_LOG.md` | index agent | done (this session) — append-only |
| `agents/DSH_HARNESS.md` | harness agent | done (this session) — what the DeepSeek Harness reads from this repository, and what it does **not** read |
| `.agents/skills/captcha-dataset/SKILL.md`, `.agents/skills/captcha-train/SKILL.md` | harness agent | done (this session) — the two project skills; their appearance in the live session catalog proves `<projectRoot>/.agents/skills` is scanned in the `web` profile |
| `reports/TRAINING_MINIMAL_LATIN.md` | training agent | in progress — the measured report of the minimal Latin model |
| `train/audit_types.py`, `train/aug_sheet.py`, `train/band_clip_check.py`, `train/band_tightness.py`, `train/bench_per_type.py`, `train/bench_pipeline.py`, `train/compare_baselines.py`, `train/eval_ckpt.py`, `train/roi_sheet.py` | training agent | done (this session) — the nine measuring scripts |

**Добавлено 2026-10-22 (см. журнал, строки 20–26):**

| файл | владелец | статус |
|---|---|---|
| `reports/research2/A..G_*.md` | research wave (7 агентов) | done — семь отчётов по направлениям |
| `reports/research2/T1_models_test.md`, `T2_onnx_runtime.md` | test wave (2 агента) | done — 12 моделей по единому протоколу + рантайм-прототип |
| `reports/research2/H_v1_family.md` | research agent | done — семейство «стандартных капч V1» группы GalleryCaptcha: что это, кто делает (не найден, `UCRAFTS/CaptchaPlugin` опровергнут), чего у нас нет |
| `bench/bench_models.py`, `bench/export_onnx.py` | test wave | done — единый харнесс и экспорт/квантизация |
| `site/index.html`, `site/style.css`, `site/app.js`, `site/data/*.js`, `site/README.md` | site agent | done — атлас капч; картинки берутся из `dataset/`, копий нет |
| `docs/ONBOARDING.md`, `docs/GLOSSARY.md`, `docs/adr/0001..0003`, `docs/pipeline-design.md` | migration agent | done — перенесено из `reports/` и создано |
| `dataset/generator/AGENTS.md`, `train/AGENTS.md` | migration agent | done — вложенные правила (ближайший AGENTS.md выигрывает) |
| `agents/REPO_CONVENTIONS_RESEARCH.md` | conventions agent | done — исследование практик организации репозитория для ИИ-агентов с источниками и вердиктами |
| `agents/REPO_STRUCTURE.md` | migration + conventions agents | done — карта, план миграции и раздел «выполнено» |
| `research/runtime/README.md`, `research/runtime/csharp/Program.cs`, `research/runtime/native/config.json` | conventions agent | done — исходники рантайма без Python; сборки (.dll, .exe, .onnx) в git не кладутся |
| `llms.txt` | main agent + conventions agent | done — машинная карта репозитория |

### 2.1 The next open work, and who should take it

| Work item | Where it is documented | Suggested owner |
|---|---|---|
| Check the bands by eye (a contact sheet of the crops of every type) and fix the ones that point at the wrong text | `CONTINUE.md` step 1; `docs/adr/0001-dataset-is-kept-in-git.md` N12 | band agent + `tools/` |
| A real 4-fold type-held-out training run with per-type accuracy and the **median** | `HANDOVER.md` §3.3, §7 M4 | trainer agent |
| Add `PP-OCRv6_medium_rec` to the benchmark | `HANDOVER.md` §7 M0 | benchmark agent |
| A per-line cropper for the number family (3 types, 300 images) | `CONTINUE.md` step 3 | trainer agent |
| Model B with 44 classes (letters **and** digits) | `CONTINUE.md` "what is broken" item 4; `HANDOVER.md` §3.4 | trainer agent |
| Verify `train/export_hf.py` end to end; write `reports/HF_RELEASE.md` and `requirements-train.txt` | `CONTINUE.md` step 7 | export agent |
| Decide the licence-per-family dataset repo layout | `HANDOVER.md` §7, `CONTINUE.md` step 6 | main agent (a policy decision) |
| Close N4, N5, N8, N12, N13, N14, N15 | `docs/adr/0001-dataset-is-kept-in-git.md` | generator agent / tools agent / main agent |
| Add `build.ps1` → `tools/restore_real_shots.py` | finding N13 | main agent |

---

## 3. Session log

One row per agent session. **Seeded from this repository's own history** — the git log, the journal in
`HANDOVER.md` §6.5, and the reports themselves. Agent ids are **not** invented: the historic sessions
are identified by role, because the ids are not recorded anywhere in the repository.

**Legend for the status column:** `done` · `done (partly)` · `stopped / unverified` ·
`unverified` (the row is inferred, the evidence for it is circumstantial).

| # | Date | Agent (role) | Task | Files owned | Result | Status |
|---|---|---|---|---|---|---|
| 1 | 2026-10-21 | generator authors (6 parallel subagents) | Write the plugin generators from the upstream sources | one file each under `dataset/generator/dev/captcha/gens/` | Six generator groups landed; their results were collected in `reports/subagent_results.json` (labels-only, no image re-reading) | done — the JSON is **stale**: it records `LagBug/XProtect/different` with 30 samples, the shipped tree has 100 |
| 2 | 2026-10-21 (generator file mtimes 17:23–18:16) | research / generator author | Identify the GalleryCaptcha type group families and the plugins behind them; write the `out_ru` generators | `dataset/generator_ru/dev/captcha/gens/*`, `research/*` | `reports/SITE_CAPTCHAS.md`, `reports/LIMBOFILTER_IDENTIFICATION.md`, `reports/PUZZLE_OBJECT_FAMILIES.md`, `reports/RU_PLUGINS_CAPTCHA_VERIFYZ_SMARTCAPTCHA.md`; 5 plugins identified, 2 of them render no image and got no generator | done |
| 3 | 2026-10-21, ~18:00 | reviewer agent (dataset) — *referred to as "Agent A"; the report also mentions "Agent B"'s reassembly* | Review `dataset/generator_ru/dev/captcha/gens/` plus the shared core | `docs/adr/0001-dataset-is-kept-in-git.md`; scratch only in `build/review/` | B1–B7 blocking issues and N1–N16 non-blocking issues, each tied to a file revision | done — B1, B2, B6, B7, N2, N6, N7, N9, N11 later **fixed**; B3, B4, B5, N1, N10 **obsolete** (the puzzle types were replaced by LimboFilter's framed captcha); **N4, N5, N8, N12, N13, N14, N15 still open** |
| 4 | 2026-10-21, 18:03–18:25 | fact-check agent | Fact-check the research reports against the code and the images | `docs/adr/0003-plugin-identification-method.md` | F1–F14 (fabricated / unverifiable claims) and C1–C7 (contradictions) | done — C7 fixed the same day; some of the F/C items remain open, see the report |
| 5 | 2026-10-21 | reviewer agent (model plan) | Review `reports/MODEL_PLAN.md` | `docs/adr/0002-recogniser-architecture-and-data.md`; scratch in `build/review/` | The review of the architecture, the augmentation, the training and the publishing plan | done |
| 6 | 2026-10-21 | main agent (orchestrator), **acting outside the protocol once** | Unblock the stuck agents | `dataset/generator/dev/captcha/McUi.java`, `dataset/generator/dev/captcha/gens/TextBand.java` | `McUi.drawColored` did not move the pen, so every chat scene was an unreadable mess — and the EasyOCR baseline of 0.115 had been measured on that garbage. Fixed: the pen follows the measured run width. The same fix widened the chat frame (the answer was not in the picture at all before) and made the inventory title fit the panel. | done — the only documented exception to "the main agent does not write code" |
| 7 | 2026-10-21 | band / ROI agent | Recompute the `roi` bands after the pen fix | the `roi()` implementations in the generator files; `tools/check_band_vs_answer.py` | The bands were recomputed **twice**, from the fixed pen. Before that, `LagBug/XProtect/drop`'s band pointed at `rote` (the tail of the prefix "XProtect") instead of the answer `drop` — a label that is unfittable by construction. The rule: a band that does not fit inside the frame is not a band. | done |
| 8 | 2026-10-21 | trainer agent | Build and debug the CRNN+CTC training pipeline | `train/captcha_crnn.py`, `train/train.py`, `train/README.md` | 4 623 615 parameters, 63 classes, greedy CTC decoding with a per-character posterior, checkpointing that restores every RNG. The all-blank plateau was measured and documented: 152 steps → loss 4.12; 2850 steps → 0.57. A held-out clean type reached **accuracy 1.000 / CER 0.000**; the type with a missing band reached 0.000. | done — the model overfits 10–16 usable types; the 4-fold run is still open |
| 9 | 2026-10-21 | GPU-environment agent | Install the CUDA build for the GTX 1080 Ti | `.venv-gpu/` | `torch 2.14.1+cu126` (cu126 still ships the sm_61 kernels the 1080 Ti needs), numpy, pillow. Verified: `get_arch_list()` contains `sm_61`, 4096³ matmul at 7.5 TFLOP/s, training at **920 img/s** against 99 on the CPU. The system Python keeps `torch 2.14.1+cpu` and was not touched. | done |
| 10 | 2026-10-21 | benchmark agent | Measure the ready-made models against the dataset | `bench/*.py`, `reports/bench_results*.json`, `reports/CAPTCHA_OCR_REPORT.md` | Baselines measured: `anuashok/ocr-captcha-v3` acc 0.077 / CER 0.785, EasyOCR 0.115 / 1.861, the ONNX models 0.000, and several that do not load under transformers 5.x. The Graf-J `AutoModel` fallback was added. | done — see discrepancy #11 in `agents/INDEX.md`: the HF path is measured on the whole frame, the other harnesses on the `roi` crop |
| 11 | 2026-10-21 | export agent | Write the Hugging Face export | `train/export_hf.py` | 72 369 bytes: one processor with no sub-processor, `vocab.json` instead of a tokenizer, `torch.onnx.export` instead of optimum, and a three-way verification (training code vs exported code vs ONNX in a fresh process). | **stopped / unverified** — the agent was stopped before it was ever executed. The file parses cleanly (checked 2026-10-21) but has never run |
| 12 | 2026-10-21, 20:58:44 +05:00 | main agent (orchestrator) | Commit the tree | the whole repository | commit `cfb7c7b` "CaptchaOCR: dataset, generators, benchmark and training pipeline" | done |
| 13 | 2026-10-21, 21:15:05 +05:00 | main agent (orchestrator) | Regenerate the dataset with the fixed rendering, fix the benchmark harness, correct the docs | `dataset/out/`, `dataset/out_ru/`, `bench/*.py`, `HANDOVER.md`, `README.md` | commit `7ffd0b8` "Regenerate the dataset with the fixed rendering, fix the benchmark harness, correct the docs" | done |
| 14 | 2026-10-21, 21:16:46 +05:00 | main agent (orchestrator) | Update the continuation prompt to the measured state | `CONTINUE.md` | commit `8845049` | done |
| 15 | 2026-10-21, 21:25–21:29 +05:00 | index agent | Build the agent-facing index of the repository | `agents/INDEX.md`, `agents/AGENT_LOG.md`, `agents/INDEX.json` — **and nothing else** | `agents/INDEX.md`: the repository map, the dataset contract, the 46 types measured from the shipped `labels.jsonl`, the commands, the gotchas, what is not here, the start-here rules, and 17 measured discrepancies against `AGENTS.md` / `HANDOVER.md` / `CONTINUE.md`. `agents/INDEX.json`: the machine-readable form. | done |
| 16 | 2026-10-21, 21:25–21:31 +05:00 (journal appended 22:42–22:48) | index agent | Recount the 46 captcha types from the shipped `labels.jsonl` and audit the documents against the measured reality | `agents/INDEX.md`, `agents/INDEX.json`, `agents/AGENT_LOG.md` — **and nothing else** | The 46 types were **re-derived**, not copied: 3400 PNG / 34 types in `dataset/out`, 1200 PNG / 12 types + 1240 reference PNGs in `dataset/out_ru`, exactly 100 per type, 4600 label rows, all carrying the same ten keys. Groups **A=20 / B=11 / C=15** (2000 / 1100 / 1500 images). 29 types carry a `roi` band (28 on all 100 samples, `haq/mapcha/map` on 99), 1701 rows have `roi = null` = 17 types. **17 discrepancies** between the documents and the measured reality were recorded; the four that matter: (1) `train/captcha_crnn.py` builds **34** classes for Model B (`CYRILLIC` = 33 letters + blank) while the plan says 44 — the digits of `LimboFilter/symbols` are dropped from the label silently; (2) the HF/TrOCR line of the benchmark was measured on **whole frames** (`bench/bench_hf.py::predict_trocr` calls `load_image(p)` without the band) while `bench_others.py` / `bench_onnx.py` crop by `roi`, so the baselines are not on the same input; (3) the flag `--require-roi` named in `CONTINUE.md` **does not exist** — the real one is `--allow-no-roi`, default off; (4) `text != answer` in **8** types, not "two families" — the two framed types `LimboFilter/framed2x2` / `framed3x3` (the Russian words inside the rotated frames) were named by nobody. The markdown table and `agents/INDEX.json` were cross-checked by script: **0 mismatches** on plugin / captcha / size / group / count. Proposed (not applied) changes for `AGENTS.md` and `HANDOVER.md` are in `agents/INDEX.md` §10. | done |
| 17 | 2026-10-21 (exact time unverified) | harness agent | Work out what the DeepSeek Harness reads from this repository, and turn the orchestrator role into a contract | `AGENTS.md` §0, `agents/DSH_HARNESS.md`, `.agents/skills/captcha-dataset/SKILL.md`, `.agents/skills/captcha-train/SKILL.md` | `AGENTS.md` §0 was rewritten into the orchestrator contract: §0.1 MAY / MUST NOT, §0.2 the 8-part subagent brief, §0.3 the acceptance checklist, §0.4 the conflict protocol (one file — one agent), §0.5 the emergency exception, §0.6 the entry points for a new agent. `agents/DSH_HARNESS.md` (435 lines, 31 193 bytes) records the harness facts with `path:line` references into the harness sources. Two project skills were created — they **appeared in the live session catalog**, which proves that `<projectRoot>/.agents/skills` **is** scanned in the `web` profile. Key conclusion: **the repository cannot define its own subagents** (there is no workspace role loader), so the `agents/` directory is *our* convention, not a harness feature. Instruction budget: `maxBytes = 65536` for the whole rendered text; `AGENTS.md` is 25 899 bytes — there is room. | done |
| 18 | 2026-10-21, still running at the time of writing | training agent | Fix the training pipeline and measure the minimal Latin model honestly | `train/captcha_crnn.py`, `train/train.py`, `train/README.md`, 9 new measuring scripts under `train/`, `reports/TRAINING_MINIMAL_LATIN.md` | Three bugs fixed in `train/`: `select()` crashed without `--val-types`; the charset check looked at only the first 5 rows of a type; samples without a band were shown as the whole frame. Added `--augment-affine` and nine measuring scripts (`audit_types.py`, `aug_sheet.py`, `band_clip_check.py`, `band_tightness.py`, `bench_per_type.py`, `bench_pipeline.py`, `compare_baselines.py`, `eval_ckpt.py`, `roi_sheet.py`). **Measured result**: a minimal model on 10 Latin types (digits + letters), type-held-out — **0.000 on unseen types, CER 0.95–1.06**; 0.997 on its own types (memorisation). It **loses to the baseline** `Graf-J/captcha-crnn-finetuned` (0.156 acc / 0.559 CER on the same 64 items with the same input). Two dataset bugs found: the `Archy-X/Krypton/map` band is **4 px too narrow** (it cuts the 5th character), and `LagBug/XProtect/reverse` has the **reversed** string in `text`. Report: `reports/TRAINING_MINIMAL_LATIN.md` (31 067 bytes). 4-fold: foldA 0.000, foldB 0.000, foldC in progress. | **in progress** — the numbers above are the measured ones reported by the agent, not re-measured here |
| 19 | 2026-10-21, 21:30–22:40 +05:00 | main agent (orchestrator) | Run the session: brief the agents, accept their results, own the files, rebuild and publish | `AGENTS.md`, the git history, `origin/main` | Three briefs were set and the results were accepted against the §0.3 checklist; file ownership was resolved (one file — one agent); the generators were rebuilt and checked — `javac` on **both** trees compiles clean, `dev.captcha.Validate` reports 3400 and 1200 images with **2 false "blank"** on two types — and the tree was committed and pushed to `origin/main`. | done |
| 20 | 2026-10-22, 10:15–10:50 | research wave — 7 parallel subagents (A–G) | Find out what already exists: ready-made projects, ready-made models on Hugging Face, how recognition works inside, how the commercial services are built, the training methods, what of the llama.cpp recipe transfers, and how to test it all | `reports/research2/A..G_*.md` — one report each, and nothing else | Seven reports, 55–78 KB each. Headlines: **PP-OCRv5 is a 5M-parameter model** and beats billion-parameter VLMs on OCR; its ablations show **diversity beats volume** (+5.38 pp from 200→1000 CLIP clusters at a constant 600k samples, +11.3 pp from 1→5M) and a 20 % label-noise costs only 1.33 pp; the corpus `szili2011` is Apache-2.0 while `hammer888/captcha-data` declares **no licence**; there is no LSTM op in ggml; three ready-made "llama.cpp for OCR" already exist. | done |
| 21 | 2026-10-22, 10:50–11:05 | test wave — 2 parallel subagents | Test the ready-made models on our dataset under one protocol, and build the runtime prototype | `reports/research2/T1_models_test.md`, `reports/research2/T2_onnx_runtime.md`, `bench/bench_models.py`, `bench/export_onnx.py`, `reports/bench_models/*.json` | **Twelve models re-scored on 46 types × 20 = 920 items** (band input, exact match + CER, per type and median): PP-OCRv6_medium_rec **0.4043** (0.5517 on the 29 banded types), cyrillic_PP-OCRv5 0.3217, PP-OCRv5 0.3152, anuashok-v3 0.2098, docTR-ru 0.1804, Graf-J 0.04–0.05, txtcaptcha-crnn 0.0022. **The old "Graf-J 0.156" was an artefact of 64 items** (reproduced exactly on the legacy set). The runtime prototype: ONNX export with a dynamic width axis, parity with PyTorch **5.7e-6**, dynamic int8 4.7 MB with **no accuracy loss**, static int8 worse. | done |
| 23 | 2026-10-22, 11:05–11:35 | site agent (two passes) | Build the captcha atlas site and make it navigable | `site/index.html`, `site/style.css`, `site/app.js`, `site/data/*.js`, `site/README.md` | A self-contained atlas (no server, no CDN, no npm): 46 type cards, **all 100 samples per type** referenced from `dataset/`, a type view with the frame, the frame with the `roi` rectangle drawn on it and the cropped band, a 46 × 28 percentages table, the pipeline on one of our own pictures, and a section that says where the answer is known and where nothing was ever verified. Style taken from `impeccable.style`. The visual language of the impeccable reference: square corners, hairline rules, one orange accent, monospaced figures. | done |
| 24 | 2026-10-22, 12:00–12:20 | main agent (orchestrator) | Run the session: two research waves, the probe, the site; commit and push | the git history, `origin/main` | Commits `22ee3d4` → `0e51ea4` → `2e6da5d` → `037ead1` → `3e4bbdc` → `c4de488` → `274d2b1` → `670bf20` → `f5fc589`. The measured headline of the session: **the cropper decides, not the model** (0 % → 75 % on the same service by changing only the input), and a ready-made PP-OCRv6 beats our 0.000 with 0.40. | done |
| 25 | 2026-10-22, 12:05–12:15 | migration agent | Move the project notes into `docs/`, add the onboarding and the glossary, add the nested `AGENTS.md` files | `docs/**`, `agents/INDEX.md`, `agents/AGENT_LOG.md`, `agents/REPO_STRUCTURE.md`, `llms.txt`, `HANDOVER.md`, `README.md`, `dataset/generator/AGENTS.md`, `train/AGENTS.md` | Four files moved with `git mv` (`reports/{PIPELINE_DESIGN,REVIEW_*}.md` → `docs/`), 13 files' links fixed, `docs/GLOSSARY.md` + `docs/ONBOARDING.md` + two nested `AGENTS.md` created, `build/scratch` (1.31 GB) cleaned. **No data path moved** — `dataset/`, `train/`, `bench/`, `site/`, `research/` stayed where they were. | done |
| 26 | 2026-10-22, 12:15–12:45 | conventions agent (this row's author) | Research how repositories are organised for AI agents, then apply it: fewer files, less always-on context, no duplication | `agents/REPO_CONVENTIONS_RESEARCH.md`, `AGENTS.md`, `CONTINUE.md`, `llms.txt`, `agents/INDEX.md`, `agents/AGENT_LOG.md`, `agents/REPO_STRUCTURE.md`, `research/runtime/README.md` | Phase 1 (research): 15+ searches, 6 primary sources read in full, including **arXiv:2602.11988** (ETH Zurich AGENTbench: LLM-written context files *reduce* success by 3 %, human-written ones give +4 % at +19 % cost, repository overviews have **no** effect, Codex truncates AGENTS.md at 32 KiB silently) and Anthropic's context-engineering guide. Phase 2 (applied): `AGENTS.md` **25 899 → 18 628 B** (the catalogue tree, the state summary and "how to add a type" moved out; a budget note added), `CONTINUE.md` rewritten as a self-contained next-session prompt, `research/runtime/` **53 files / 33.8 MB → 2 files / 10 KB** (46 one-off probe scripts and the build artefacts deleted; the C# source and the config kept), `research/briefs/` (15 transient briefs) and `research/__pycache__/` deleted, `llms.txt` and `agents/INDEX.md` brought up to date. Deliberately **not** taken: `CLAUDE.md` / `.cursorrules` / `.clinerules` / `GEMINI.md` (six copies of one rules file drift apart) and repomix (a generated snapshot, not a curated map). | done |

### 3.1 Notes on the reconstruction

- **Everything before row 15 is reconstructed from the repository's own artefacts**, not from a live
  agent registry: the git log (3 commits, all by the human owner `Titlehhhh`, all on 2026-10-21), the
  journal in `HANDOVER.md` §6.5, the `Reviewer:` / `Audit window:` headers of the three review
  reports, `reports/subagent_results.json`, and the `AGENTS.md` §0 note about the two files the main
  agent patched itself.
- **No agent id appears anywhere in the repository**, so none is given here. The historic sessions are
  identified by role only.
- **The exact ordering of rows 1–11 is partially inferred.** The timestamps that *are* verifiable are
  the git commit times (rows 12–14), the audit window of `docs/adr/0003-plugin-identification-method.md` (row 4:
  18:03–18:25) and the file revision times listed in `docs/adr/0001-dataset-is-kept-in-git.md` (rows 2–3). Rows 1,
  6–11 carry the date but **no verified time** — the order between them is an inference, marked as
  such.
- **Row 6 is an inference from a single sentence** in `AGENTS.md` §0: *"как было с `McUi.drawColored`
  и `TextBand`"* — the main agent made those two edits itself to unblock a stuck agent. The
  `HANDOVER.md` §6.5 "Two bugs that cost the most" section confirms the effect of the first.
- **Row 8's numbers** come from `HANDOVER.md` §6.5, which is a measurement log written by the trainer
  agent. They were **not** re-measured here — running the trainers is out of scope for the index
  task.
- **Row 9's numbers** were re-verified on 2026-10-21 during the index session:
  `torch.cuda.get_arch_list()` contains `sm_61`, `torch.cuda.is_available()` is True, the device is an
  NVIDIA GeForce GTX 1080 Ti with 11.8 GB.
- **Row 13's dataset regeneration was verified indirectly**: the shipped trees contain 3400 + 1200
  labelled PNGs in 46 types of 100, matching the claim in the commit message and in `HANDOVER.md`.
- **Rows 16–19 are not reconstructed.** They were reported by the orchestrator at the end of the
  2026-10-21 evening session, from that session's own results. Row 18's training numbers are the
  training agent's own measurements, carried over here as reported — they were **not** re-measured by
  the index agent (running the trainers is out of scope for the index work).

---

## 4. Adding a row

When an agent session ends, the orchestrator adds one row to §3 with:

- a **sequential number**,
- the **date** (and the time, if it is known),
- the **role** of the agent — never an invented id,
- the **task** in one line,
- the **files owned** — the exact list the brief gave it,
- the **result** in one line, with the verification command if there was one,
- the **status** from the legend.

If the agent was stopped half-way, the row says **stopped / unverified** and names what was left
unfinished. A stopped agent leaves the tree in an inconsistent state — say so in the row, so the next
orchestrator knows to compile before handing out the next brief.
