# LOCAL_ENV — локальный тулчейн этой машины

> Этот файл — про **эту машину**; переносимые инструкции для любого пользователя — в
> [`docs/HOW_TO_TRAIN.md`](HOW_TO_TRAIN.md) и [`docs/ONBOARDING.md`](ONBOARDING.md).

**Дата:** 2026-10-22. Все пути проверены на этом компьютере: JDK и `hf` — запуском, пути харнесса —
чтением установленного пакета `@deepseek-ai/dsh-skill-filesystem` и `@deepseek-ai/dsh-launch-environment`
(`C:\Users\Title\AppData\Local\npm-cache\_npx\1e7f6d9597241db0\node_modules\@deepseek-ai\`).

Краткая версия для агента — навык [`.agents/skills/captcha-toolchain/SKILL.md`](../.agents/skills/captcha-toolchain/SKILL.md).
Этот файл — полная таблица: чинить что-то сразу по ней, за минуту.

---

## 1. Пути — одна таблица

| Путь | Что это | Кто владеет |
|---|---|---|
| `I:\ForAndroid\Java\21` | **JDK 21.0.8** (LTS). Внутренний том NTFS, drive type 3 = fixed, не съёмный | эта машина (ручная установка) |
| `%JAVA_HOME%` (пользовательская переменная Windows) | указывает на `I:\ForAndroid\Java\21`; наследуется **каждым новым shell** | эта машина |
| `dataset\generator\`, `dataset\generator_ru\` | Java-генераторы; нужен JDK 21 | **репозиторий** |
| `build.ps1` | скрипт сборки — **запустить нельзя** (см. §4) | репозиторий |
| `.venv-gpu\Scripts\python.exe` | **единственный** интерпретатор с CUDA (`torch 2.14.1+cu126`) | репозиторий (5 ГБ, gitignored) |
| системный `python` | **CPU-only** — обучать на нём нельзя | эта машина |
| `.hf-cache\` | локальный кэш Hugging Face этого проекта (`HF_HOME`) | репозиторий (gitignored) |
| `.hf-cache\token` | **токен аккаунта `Titlehhhh`** — не печатать, не копировать, не коммитить | репозиторий (gitignored) |
| `.dsh\` (в корне проекта) | слот харнесса для навыков проекта: `.dsh\skills\` | репозиторий (не создан) |
| `.agents\skills\` (в корне проекта) | слот навыков агентов проекта: `captcha-dataset`, `captcha-train` | **репозиторий** |
| `.env` (в корне проекта) | **слой env №1 (проект)** — `JAVA_HOME`, `HF_HOME`, `HF_HUB_CACHE`, `PYTHONIOENCODING` | репозиторий (gitignored) |
| `~\.dsh\` | **харнесс-дом** (`$DSH_HOME`): `.credentials.yaml`, `cache\`, `sessions\`, `profiles\`, `skills\`, `settings.yaml` | эта машина |
| `~\.dsh\skills\` | слот навыков харнесса для пользователя (сейчас там `web-search`) | эта машина |
| `~\.dsh\.env` | **слой env №2 (машина)** — `JAVA_HOME`, `PYTHONIOENCODING` | эта машина |
| `~\.agents\` | общий корень агентов (`$DSH_AGENTS_HOME`), общий с другими инструментами; слот `~\.agents\skills\` | эта машина (не создан) |
| `C:\Users\Title\AppData\Local\npm-cache\_npx\1e7f6d9597241db0\node_modules\@deepseek-ai\` | установленный код харнесса — источник истины по путям | npm |

---

## 2. Java: JDK 21

JDK 21.0.8 (2025-07-15 LTS) стоит в **`I:\ForAndroid\Java\21`** — на фиксированном внутреннем томе NTFS
(drive `I:`, `DriveType = 3`, не съёмный).

`JAVA_HOME` уже задан **на уровне пользователя Windows** (`[Environment]::GetEnvironmentVariable("JAVA_HOME","User")`),
поэтому новая оболочка наследует его сама — экспортировать руками ничего не нужно.

> **`java`/`javac` НЕ на `PATH`.** Ни в сессионном, ни в пользовательском `PATH` нет каталога JDK:
> команда `java -version` даёт «не распознано как имя командлета». Пользуйтесь `$env:JAVA_HOME`:
> `"$env:JAVA_HOME\bin\javac.exe"`, `"$env:JAVA_HOME\bin\java.exe"`.
> (В `AGENTS.md` §7 и в навыках `captcha-dataset` / `captcha-train` написано «JDK 21 в `PATH`» —
> это устаревшая формулировка; правильный путь — `I:\ForAndroid\Java\21`.)

---

## 3. Hugging Face: токен

Токен аккаунта **`Titlehhhh`** лежит в локальном кэше проекта:

```
C:\Users\Title\Projects\CapthaModel\.hf-cache\token
```

`HF_HOME` должен указывать на каталог `.hf-cache` — тогда `hf` и `huggingface_hub` находят токен сами.
`.hf-cache/` в `.gitignore`. **Сам токен не печатать, не копировать и не коммитить** — только путь.

---

## 4. Слои `.env`, которые читает харнесс

Пакет `@deepseek-ai/dsh-launch-environment` читает **два** файла и делает **снимок при старте** харнесса.
Изменение вступает в силу **в следующем запуске**, а не в текущей сессии.

| Слой | Файл | Что в нём |
|---|---|---|
| проект | `C:\Users\Title\Projects\CapthaModel\.env` | `JAVA_HOME`, `HF_HOME`, `HF_HUB_CACHE`, `PYTHONIOENCODING` |
| машина | `C:\Users\Title\.dsh\.env` | `JAVA_HOME`, `PYTHONIOENCODING` |

Приоритет (от высшего к низшему): унаследованное окружение процесса → `<cwd>/.env` → `$DSH_HOME/.env`.
`.env` в `.gitignore`.

**`build.ps1` запустить нельзя** — выполнение любого `.ps1` блокируется политикой
(«AuthorizationManager check failed»), даже для файла в рабочем дереве. Выполняйте логику инлайн
(команды — в `AGENTS.md` §4 и в навыке `captcha-dataset`). Бинаря `pwsh` на машине нет — только
Windows PowerShell 5.1.

---

## 5. Где харнесс хранит навыки

Корень проекта — ближайший предок с `.git` (здесь `C:\Users\Title\Projects\CapthaModel`).
Ранги из `dsh-skill-filesystem` (`PROJECT_DSH_RANK = 100`, `PROJECT_AGENTS_RANK = 200`,
`CUSTOM_RANK = 300`, `USER_DSH_RANK = 400`, `USER_AGENTS_RANK = 500`):

| Слот | Путь | Ранг | Что кладём |
|---|---|---|---|
| проект, харнесс | `<projectRoot>\.dsh\skills\<имя>\SKILL.md` | 100 | навык, специфичный для харнесса |
| проект, агенты | `<projectRoot>\.agents\skills\<имя>\SKILL.md` | 200 | **этот репозиторий** так и делает |
| свои каталоги | (настраиваются) | 300 | — |
| пользователь, харнесс | `~\.dsh\skills\<имя>\SKILL.md` | 400 | `web-search` лежит здесь |
| пользователь, агенты | `~\.agents\skills\<имя>\SKILL.md` | 500 | общий с другими инструментами |

Харнесс-дом `~\.dsh\` (`$DSH_HOME`) и общий корень `~\.agents\` (`$DSH_AGENTS_HOME`) переопределяются
переменными `DSH_HOME` / `DSH_AGENTS_HOME`.

---

## 6. Python и GPU

| Что | Значение |
|---|---|
| GPU | NVIDIA GeForce GTX 1080 Ti, 11264 MiB (11.8 ГБ), sm_61, драйвер 581.57 |
| venv с CUDA | `.venv-gpu\Scripts\python.exe` → `torch 2.14.1+cu126`, `torch.cuda.is_available() == True` |
| системный python | **CPU-only** — обучение на нём идёт в ~9 раз медленнее (не использовать) |

---

## 7. Как проверить (копипаст, всё read-only)

```powershell
# JDK и JAVA_HOME
$env:JAVA_HOME                                          # I:\ForAndroid\Java\21
[Environment]::GetEnvironmentVariable("JAVA_HOME","User") # то же на уровне пользователя
& "$env:JAVA_HOME\bin\java.exe" -version                # 21.0.8
Get-Command java -ErrorAction SilentlyContinue           # пусто — java НЕ на PATH

# Hugging Face
$env:HF_HOME="C:\Users\Title\Projects\CapthaModel\.hf-cache"
hf auth whoami                                          # [OK] Logged in / user: Titlehhhh

# Слои .env
Get-Content "C:\Users\Title\Projects\CapthaModel\.env"  # проектный слой
Get-Content "C:\Users\Title\.dsh\.env"                  # машинный слой

# Навыки: где что лежит
Get-ChildItem "$env:USERPROFILE\.dsh\skills" -Directory   # пользовательские навыки харнесса
Get-ChildItem ".agents\skills" -Directory                 # навыки проекта
Get-ChildItem "C:\Users\Title\AppData\Local\npm-cache\_npx" # установленный харнесс (источник истины)

# Python и GPU
.venv-gpu\Scripts\python.exe -c "import torch; print(torch.__version__, torch.version.cuda, torch.cuda.is_available())"
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv
```

---

## 8. Если что-то сломалось — за минуту

| Симптом | Причина | Что делать |
|---|---|---|
| `java` не найден | нет в `PATH` | зовите `"$env:JAVA_HOME\bin\java.exe"`; `JAVA_HOME` уже задан, руками ничего экспортировать не надо |
| `hf` не залогинен | не задан `HF_HOME` | `$env:HF_HOME="C:\Users\Title\Projects\CapthaModel\.hf-cache"`, затем `hf auth whoami` |
| переменная из `.env` не видна | снимок окружения сделан при старте | перезапустите харнесс — правка `.env` действует со следующего запуска |
| `build.ps1` не запускается | политика выполнения блокирует `.ps1` | выполняйте логику инлайн (`AGENTS.md` §4) |
| `pwsh` не найден | бинаря нет на этой машине | Windows PowerShell 5.1; синтаксис без `-` префиксов pwsh |
| навык не появился в каталоге | skill discovery идёт при старте | положите его в `.agents\skills\<имя>\SKILL.md` и перезапустите сессию |
| torch видит только CPU | вызван системный python | `.venv-gpu\Scripts\python.exe` вместо `python` |
