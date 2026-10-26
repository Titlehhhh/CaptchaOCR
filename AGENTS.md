# AGENTS.md — CaptchaOCR

**Единственная точка входа для агента в этом репозитории.** Правила здесь обязательны; детали лежат
за ссылками — читай их по надобности, а не целиком.

> **Бюджет контекста.** Харнесс обрезает суммарный отрисованный текст инструкций на **64 КиБ**
> (`maxBytes` в `packages/bundle/base/cordis.patch.yml`), Codex CLI — на **32 КиБ** и **молча**.
> Этот файл держим ниже **20 КБ** (сейчас 19.9 КБ). Если нужна новая информация — она идёт в
> `docs/` или `agents/`, а не сюда. Обоснование: `agents/REPO_CONVENTIONS_RESEARCH.md`
> (по arXiv:2602.11988: «обзоры архитектуры в контекст-файле не помогают, дублирование вредит»).

---

## 0. The main agent is an ORCHESTRATOR (главный агент — оркестратор)

**The one-line rule: the main agent is an ORCHESTRATOR. It does not implement, does not edit code,
does not run the training. It briefs, accepts, resolves conflicts, rebuilds the dataset, commits,
and answers the user.**

Every agent that reads this file — main or sub — is bound by it. The main agent's own hands stay
off the source.

### 0.1 MAY / MUST NOT

| The main agent MAY | The main agent MUST NOT |
|---|---|
| read files, list the tree, count files and samples | write or edit a source file |
| compile the generators (`javac`, both trees) | write a report that an agent was supposed to write |
| run `dev.captcha.Validate` | invent a measurement, a number, a log line or a source location |
| run the dataset checkers (`tools/check_labels_and_roi.py`, `tools/check_band_vs_answer.py`) | run a multi-hour training itself |
| inspect `labels.jsonl`, count types, diff the tree | regenerate the dataset unless the brief says so |
| brief a subagent (`subagent` / `subagent_fork`) | let two agents own the same file |
| accept a result against the checklist in §0.3 | accept a result whose numbers are not reproducible |
| run `git add` / `git commit` | push, force-push, or rewrite published history |
| answer the user | hand out a brief that is not ready (§0.2) |

### 0.2 The subagent brief — 8 mandatory parts

A task without these eight parts is **not ready to hand out**. A subagent starts with a clean
context: the brief *is* the contract, so it must be self-contained.

1. **Goal** — what "done" looks like, in one or two sentences.
2. **Input data** — the exact paths, relative to the repo root.
3. **Files owned** — the files this agent may write.
4. **Files forbidden** — everything else, named explicitly: the precious things
   (`dataset/out/`, `dataset/out_ru/`, the `real_shots/` reference images, the measured result JSONs in
   `reports/`) and the files owned by other agents.
5. **Definition of done** — the observable end state.
6. **How to self-check** — the exact command that proves it, and what its output should look like.
7. **Report format** — files touched / what was verified / what was **not** verified / what is
   broken / discrepancies (see `agents/AGENT_LOG.md` §1.3).
8. **Deadline and iteration budget** — how much wall-clock, and how many attempts.

Before handing a brief out, check that the previous work is in place: does the generator tree
compile, does `dev.captcha.Validate` pass, is no agent left half-way through an edit.

### 0.3 The acceptance checklist

A result is accepted only when every line holds:

- [ ] the tree compiles — `javac` on both generators, no errors;
- [ ] `dev.captcha.Validate` is clean on the tree that was touched;
- [ ] the diff matches the task and touches **only** the owned files;
- [ ] the report's numbers are reproducible — the agent shows the command and its output;
- [ ] no file outside the ownership was touched;
- [ ] the result is logged in `agents/AGENT_LOG.md` (ownership table + session log).

### 0.4 Conflicts: one file — one agent

Two agents editing one file overwrite each other; this already happened with
`dataset/generator_ru/`. Ownership is fixed **before** the brief goes out and is written into it.

If two agents want the same file:

1. **stop the second one** (`interrupt_agent`) before it starts editing;
2. **re-scope** one of the two briefs, so the file belongs to exactly one of them;
3. **re-issue** the brief with the new ownership written into it.

A subagent must never be left half-way through an edit — the tree stays inconsistent and the next
agent compiles on top of a broken file. If an agent has to be stopped, tell it to finish the current
edit (or revert it) before it stops.

### 0.5 The emergency exception

The main agent may make a **minimal** edit of its own — a few lines, no new design — but only to
unblock a stuck agent, and only if it says so **in the message to that agent**. The two cases in
this repository's history: `McUi.drawColored` and `TextBand`. Everything else goes to a subagent.

### 0.6 The entry points for a new agent

| файл | что это |
|---|---|
| `docs/ONBOARDING.md` | маршрут для человека/нового агента: что за проект, с чего начать, как собрать, обучить, проверить |
| `agents/INDEX.md` | подробная карта репозитория: 46 типов, контракт датасета, измеренные команды, расхождения |
| `agents/AGENT_LOG.md` | протокол субагента, таблица владения файлами, журнал сессий |
| `agents/DSH_HARNESS.md` | что DeepSeek Harness читает из репозитория — и что **не** читает |
| `agents/REPO_CONVENTIONS_RESEARCH.md` | почему репозиторий устроен так, как устроен (практики и наши вердикты) |
| `docs/GLOSSARY.md` | термины: `text` vs `answer`, `roi`/полоса, группа A/B/C, faithful/clean-room/reconstructed |
| `docs/adr/` | принятые решения (почему так) |
| `llms.txt` | машинная карта репозитория (формат llms.txt) |
| `HANDOVER.md` | состояние проекта и все измеренные числа |
| `reports/HTML/index.html` | **единственный browsable-отчёт** для владельца: все измеренные числа |
| `reports/README.md` | индекс отчётов; обзор системы — в `reports/archive/2026-10-22-overview/` |
| `agents/WORKFLOW.md` | как запускать workflow: переопределение провайдера/модели в `agent()`, бесплатные модели OpenRouter (`recursive/flint-v1.0:free` по умолчанию, `thinkingmachines/inkling:free` — fallback), проверенные сниппеты |

**Workflow по максимуму.** Когда владелец просит использовать workflow по максимуму (субагенты
на бесплатных моделях OpenRouter для него бесплатны, главный агент — нет), запускай субагентов
инструментом `workflow`, указывая бесплатную модель в `agent(prompt, {provider, model})`;
проверенный рецепт — [`agents/WORKFLOW.md`](agents/WORKFLOW.md).

---

## 1. What this project is

**CaptchaOCR** is a laboratory for building captcha-solving models that will eventually be published on
**Hugging Face**. Two halves:

| Half | What it is | Where |
|---|---|---|
| **Dataset** | A Java 21 generator that re-renders, pixel-faithfully, the captchas that real open-source Minecraft anti-bot plugins produce — 46 types, 23 000 labelled PNGs. | `dataset/generator/`, `dataset/generator_ru/`, output in `dataset/out/` and `dataset/out_ru/` |
| **Models** | Benchmark harnesses over existing OCR/captcha models, and a CRNN+CTC trained from scratch on our data. | `bench/`, `train/` |

The best measured baseline is 0.552 exact match on the answer band and 0.035 on the whole frame — the
**cropper** decides, not the model (`reports/bench_models/ppocrv6-medium.json`). Details, dataset contract and the type table: `agents/INDEX.md`.

## 2. The goal (stated by the project owner)

> Сделать открытую модель (или модели) для решения капчи, чтобы потом залить на Hugging Face.
> Это моя лабораторная работа. Хочу потыкать самые современные модели для этого.

In practice: broaden the dataset to cover the captcha styles that appear in production, try the most
modern models available (TrOCR, PaddleOCR/PP-OCRv5-v6, VLM OCR, CRNN/CTC, SVTR), and train and
publish a model (or an ensemble) on Hugging Face that is actually useful on this domain.

## 3. Where things are

| path | что лежит | подробности |
|---|---|---|
| `dataset/generator/`, `dataset/generator_ru/` | Java-генераторы 23 плагинов | `dataset/generator/AGENTS.md` — как добавить тип, house rules, правило полосы |
| `dataset/out/`, `dataset/out_ru/` | **сгенерированный** датасет: 46 типов × 500 PNG + `labels.jsonl` | **артефакт машины**: **генераторы не засеяны** — шрифты AWT те же, сами сэмплы случайны, пересборка даст другой набор |
| `dataset/out_ru/*/real_shots/` | 517 эталонных скриншотов — **не публикуются** (чужие скриншоты) | в публичный репозиторий и в датасет на HF они не идут |
| `train/` | CRNN+CTC (`captcha_crnn.py`), тренажер (`train.py`), PP-OCRv6 (`finetune_ppocr.py`, `soup_eval.py`, `export_ppocr_hf.py`) | `train/AGENTS.md` — как запускать эксперименты, плато CTC, правило полосы |
| `bench/` | 6 харнессов для чужих моделей + `bench_models.py` (единый протокол) | результаты в `reports/bench_models/` |
| `tools/` | чекеры меток и полос, анализ группы типов GalleryCaptcha, отчёты | |
| `reports/` | измеренные результаты (никогда не править JSON результатов) | индекс — `reports/README.md`, отчёт — `reports/HTML/index.html`, старое — `reports/archive/` |
| `docs/` | онбординг, глоссарий, ADR, runbook (`HOW_TO_TRAIN.md`), конвейер (`INPUT_PIPELINE.md`) | |
| `agents/` | карта репозитория, журнал сессий, правила оркестратора | |
| `research/` | апстримы, декомпиляция, эталоны, исходники рантайма | |

**Контракт датасета** (подробно — `agents/INDEX.md` §3):

```
dataset/out/<owner>/<repo>/<type>/NNN.png  + labels.jsonl     # 34 типа, owner/repo из апстрима
dataset/out_ru/<Plugin>/<type>/NNN.png     + labels.jsonl     # 12 типов, плоское имя плагина
```

`labels.jsonl`: одна строка JSON на сэмпл: `file`, `plugin`, `captcha`, `answer` (что вводит игрок),
`text` (что **нарисовано**; в 9 типах из 46 они различаются — нужен шаг solver'а), `prompt`,
`roi` (полоса `[x,y,w,h]` с ответом или `null`), `width`, `height`, `source` (апстрим-аудит).
**Правило полосы: полоса, которая не помещается в кадр, — это не полоса** (`roi` = `null`).

## 4. Commands

```powershell
# Пересборка датасета (логика build.ps1 — сам build.ps1 выполнить НЕЛЬЗЯ, см. §7)
$javac = if ($env:JAVA_HOME) { "$env:JAVA_HOME\bin\javac.exe" } else { "javac" }
$java  = if ($env:JAVA_HOME) { "$env:JAVA_HOME\bin\java.exe"  } else { "java" }
$core  = Get-ChildItem -File dataset\generator\dev\captcha\*.java | % FullName   # общие классы: нужны и RU-дереву
& $javac -encoding UTF-8 -d build\classes    -sourcepath dataset\generator    $core (Get-ChildItem -Recurse -Filter *.java dataset\generator    | % FullName)
& $javac -encoding UTF-8 -d build\classes_ru -sourcepath dataset\generator_ru $core (Get-ChildItem -Recurse -Filter *.java dataset\generator_ru | % FullName)
& $java "-Djava.awt.headless=true" -cp build\classes    dev.captcha.Gen      dataset\out    100 --jobs 36
& $java "-Djava.awt.headless=true" -cp build\classes    dev.captcha.Validate dataset\out
& $java "-Djava.awt.headless=true" -cp build\classes_ru dev.captcha.Gen      dataset\out_ru 100 --jobs 36
& $java "-Djava.awt.headless=true" -cp build\classes_ru dev.captcha.Validate dataset\out_ru
python tools\restore_real_shots.py            # вернуть real_shots/ после пересборки

# Проверки меток и полос
python tools\check_labels_and_roi.py dataset\out_ru
python tools\check_band_vs_answer.py dataset\out_ru

# Бенчмарк чужих моделей
python bench\bench_models.py --help

# Обучение (venv с CUDA, системный python — CPU-only)
.venv-gpu\Scripts\python.exe train\train.py --trees both --epochs 80 --val-types "haq/mapcha/map" "CaptchaVerifyZ/map"
```

`Gen <outDir> <count> [--jobs N]` рисует все генераторы, пишет PNG, `labels.jsonl` на тип и `index.html`.
`--jobs N` — потоки рендера (36 по умолчанию), отчёт — `reports/GEN_PARALLEL.md`. `Validate <outDir>`
печатает `n / minColors / blank / dupes / labels` по типам. `Stats <png|dir>` — гистограмма цветов.
Все три работают headless.

## 5. Adding a captcha type

**Полностью — в `dataset/generator/AGENTS.md`**: контракт `dev.captcha.Cg`, house rules (faithful over
pretty, дефекты апстрима воспроизводятся, `source()` не выдумывается), правило полосы и команды
проверки. Коротко: новый тип = **один новый java-файл** в `gens/`, больше ничего править не надо —
`Gen` находит классы рефлексией.

## 6. The state of the project

Состояние живёт в **`HANDOVER.md`** (цифры и что не сделано) и в **`reports/`** (измерения).
Коротко, чтобы не искать:

- **Датасет готов**: 46 типов, **23 000** размеченных PNG (было 46 × 100), 23 апстрим-плагина
  (12 faithful, 10 clean-room, 1 reconstructed; по типам — 25 / 16 / 5), 517 эталонных скриншотов
  (не публикуются). Разбивка типов на группы A/B/C — `agents/INDEX.md` §4.
- **Опубликовано на Hugging Face**: датасет — `Titlehhhh/captchaocr-dataset`, коммит `6248c5b9…`
  (23 000 PNG + 46 `labels.jsonl`); модель — `Titlehhhh/captchaocr-ppocrv6`, коммит `43a65582…`
  (8 файлов, 77 085 348 Б) — WiSE-FT-интерполяция `θ = 0.4·θ_ft + 0.6·θ_pretrained`.
- **PP-OCRv6 на 7 удержанных типах / 5 плагинах / 3 500 картинках** (один и тот же пайплайн):

  | вариант | median exact | median CER | micro exact | micro CER |
  |---|---|---|---|---|
  | предобученная (нулевой шаг) | 0.588 | 0.1657 | 0.5646 | 0.2446 |
  | дообученная как есть | 0.480 | 0.2233 | 0.5480 | 0.2181 |
  | **+ интерполяция α = 0.4 (опубликована)** | **0.638** | 0.1503 | 0.6123 | 0.2004 |

  α и эпоху выбирали **на том же удержанном наборе** — число оптимистично.
- **Наш CRNN+CTC с нуля** (7 типов учили, 4 удержали): на невиданных плагинах median **0.372** /
  CER 0.322, micro **0.381** / 0.410; на своих типах **1.000** — разрыв запоминания 62.8 п.п.
  (на старом рендере 100/тип было 0.000) — `reports/TRAINING_CRNN_BIG.md`.
- **TrOCR-small — не лучше**: нулевой шаг median 0.00, после одной эпохи 0.002, в 5 раз медленнее
  PP-OCRv6 — `reports/TRAINING_TROCR_BIG.md`.
- **Два бага генераторов починены 2026-10-22, датасет пересобран**: полоса `Archy-X/Krypton/map`
  была на 4 px ýже текста — теперь `band()` прибавляет `code.length()-1`; в `text` типа
  `LagBug/XProtect/reverse` лежала **перевёрнутая** строка — теперь `text()` возвращает нарисованный код.
- **Не сделано**: per-family репозитории по лицензиям, дообучение на публичном корпусе,
  независимая (не выбранная на held-out) проверка α.

## 7. Environment notes (Windows, this machine)

- **Java 21** — JDK 21 в `I:\ForAndroid\Java\21` (диск I:, внутренний том); `JAVA_HOME` уже задан на
  уровне пользователя Windows, новый shell наследует его сам (`java -version` → 21.0.8).
- **Локальный тулчейн** (JDK, токен HF, навыки, слои `.env`) — `docs/LOCAL_ENV.md` и навык
  `.agents/skills/captcha-toolchain/SKILL.md`: читай перед правкой `.env` и вызовом `hf`.
- **HF**: токен `Titlehhhh` в `.hf-cache/token` (gitignored), нужен `HF_HOME` = путь к `.hf-cache`.
- **Навыки**: `.agents/skills/` (проект) / `~/.dsh/skills/` (пользователь); `.env`: `<cwd>/.env` и `~/.dsh/.env`.
- **GPU**: NVIDIA GeForce GTX 1080 Ti (11.8 ГБ, sm_61), драйвер 581.57. CUDA-сборка torch живёт в
  `.venv-gpu/` (`torch 2.14.1+cu126` — в нём ещё есть sm_61), **системный python — CPU-only**.
  Тренировка: `.venv-gpu\Scripts\python.exe train\train.py ...`.
- **Нет бинаря `pwsh`** — только Windows PowerShell 5.1; не вызывай `pwsh`.
- **Выполнение `.ps1` заблокировано** («AuthorizationManager check failed»), даже для файла в
  рабочем дереве. `build.ps1` запустить нельзя — выполняй логику инлайн (§4).
- **Headless-браузер — только с отдельным профилем:** `--user-data-dir="$env:TEMP\edge-<задача>"`.
  Без этого headless Edge занимает профиль живого браузера и **вышибает его у владельца** (проверено
  2026-10-22). Если проверка сайта не нужна — не запускай Edge вообще.
- **`ddgs`** (веб-поиск) падает на кириллице без `$env:PYTHONIOENCODING="utf-8"`; встроенный
  `web_search` отключён, используй навык `web-search`.
- **GitHub API без токена** — 60 запросов/час, батчь запросы и спи между ними.
- **Веб-архив** (`web.archive.org`) периодически отдаёт 503 — это не значит, что страницы нет;
  повтори позже, есть зеркала (`timetravel.mementoweb.org`, `archive.ph`).

## 8. Safety and honesty rules for agents in this repo

- **Never fabricate a source location.** If a plugin's upstream source cannot be found, say so plainly and
  reconstruct the captcha from the reference screenshots in `real_shots/`, marking it clean-room / reconstructed.
  Do not invent a GitHub URL or a method name to make a record look complete.
- **Never "fix" an upstream defect** in a generator. Document it instead.
- **Do not delete the `real_shots/` reference images.** They are the ground truth for the reconstructions.
- **Label every dataset row with where it came from.** `source()` and `labels.jsonl` are the audit trail.
- **The `reports/` folder holds measured results. Do not edit a result JSON to make a model look better;
  re-run the benchmark instead.**
- **Материалы сторонних коммерческих сервисов не используются и не публикуются**: ни их картинки,
  ни страницы, ни ответы API не попадают в датасет и в репозиторий; чужие скриншоты удалены.
  Обучение строится только на собственных рендерах генераторов.
