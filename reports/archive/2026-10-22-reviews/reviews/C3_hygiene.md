# C3 — ревизия «чистоты публикации»

**Дата проверки:** 2026-10-22 · **Проверял:** аудитор публикации (C3) · **Ничего не правил**
**Объект:** `github.com/Titlehhhh/CaptchaOCR` (сейчас `private`), ветка `main`, HEAD `84d181f`
**Локально:** `C:\Users\Title\Projects\CapthaModel`, HEAD `84d181f` == `origin/main`

---

## ВЕРДИКТ

**Публиковать нельзя. Ветка `main` чиста — а сама публикация нет.**

Текущая ветка `main` (2 коммита, 521 blob, 24.27 МБ) не содержит **ни одного** совпадения
по запрещённым шаблонам (`bareapi`, `capmonster`, `mit_ck`, `mitelis`, `i.ibb.co`,
`i.postimg.cc`, `support@`) — ни в именах файлов, ни в содержимом текстовых файлов, ни в
истории этой ветки. Реальные скриншоты (`real_shots/*.png`) в дерево не попали, HF-карточки
чистые, секретов нет.

**Но «историю переписали» только локально.** На сервере GitHub **все 9 старых коммитов
остались адресуемы по SHA** — и в каждом из них лежит запрещённый сервис: домен
`bareapi.shop`, тип капчи `BARE-API/<type>`, 511 картинок с `i.ibb.co`, живой cookie
`mit_ck_p1`, `support@mitelis.net`, скрипт `bench/probe_capmonster.py` с
`https://api.capmonster.cloud/createTask` и его результаты, а также 1240 чужих скриншотов.
Хуже того: **опубликованный `agents/AGENT_LOG.md` сам перечисляет эти SHA** — публичный
репозиторий выдаёт ключи к грязной истории.

Пока это так, «приватный репозиторий» — единственное, что удерживает следы. Один клик
«Make public» — и следы становятся публичными по прямым ссылкам `/commit/<sha>`, а
`AGENT_LOG.md` помогает их найти.

**Что сделать до публикации (по убыванию важности):**

1. **Удалить репозиторий на GitHub и создать заново** из чистой локальной копии
   (надёжнее force-push: GitHub держит недостижимые объекты, пока не сработает GC).
   Затем проверить, что `gh api repos/Titlehhhh/CaptchaOCR/commits/cfb7c7b` → **404**.
2. **Вычистить SHA старых коммитов** из `agents/AGENT_LOG.md` (строки 248–259) и
   `reports/research2/T1_models_test.md:163` — либо не публиковать `agents/AGENT_LOG.md`.
3. **Убрать персональные пути** (`C:\Users\Title\...`) — особенно `agents/DSH_HARNESS.md`
   целиком; и вычистить хардкод `C:\Users\Title\Projects\CapthaModel` из `research/tools/*.py`.
4. **Решить по `research/limbofilter/*.java`** (декомпиляция AGPL-3.0): удалить / оставить
   с атрибуцией под AGPL / заменить ссылкой.
5. Остальное (мусор, размеры, HF-карточка модели) — по желанию, не блокирует.

---

## 1. Следы коммерческого сервиса

### 1.1 Точные следы в ветке `main` — **НЕ НАЙДЕНЫ**

| Проверка | Команда | Результат |
|---|---|---|
| Имена файлов/каталогов | скан 20 шаблонов по `trees/main?recursive=1` | **0 совпадений** |
| Содержимое всех текстовых файлов | `git grep -I -n -i -E "bareapi\|bare-api\|bare_api\|capmonster\|mit_ck\|mitelis\|i\.ibb\.co\|i\.postimg\.cc\|support@" origin/main` | **0 совпадений** |
| Код GitHub | `gh search code "bareapi repo:Titlehhhh/CaptchaOCR"` (+ capmonster, mit_ck, i.ibb.co, i.postimg.cc) | **пусто []** по всем пяти |
| История ветки | `git log --all -p \| Select-String "bareapi\|..."` | **0 совпадений** |
| Мусор в индексе git | `git fsck --unreachable --dangling` | **пусто** (локально всё вычищено) |

### 1.2 ⛔ КРИТИЧНО: старая история жива на GitHub — следы там есть

`git log --all` локально показывает 2 коммита, но **на сервере GitHub доступны по SHA все 9
старых коммитов**, перечисленных в `agents/AGENT_LOG.md`:

```
gh api repos/Titlehhhh/CaptchaOCR/commits/cfb7c7b   → 200 OK  (корень старой истории)
gh api repos/Titlehhhh/CaptchaOCR/commits/22ee3d4   → 200 OK  («…and the CapMonster probe script»)
```

Ответы — 12/12 `REACHABLE`: `cfb7c7b, 7ffd0b8, 8845049, 2e6da5d, 0e51ea4, 037ead1,
22ee3d4, 3e4bbdc, c4de488, 274d2b1, 670bf20, f5fc589`.

Содержимое старых коммитов снято тарболлами
(`GET /repos/Titlehhhh/CaptchaOCR/tarball/<sha>`) и просканировано:

| Коммит | Что внутри (запрещённого) |
|---|---|
| `cfb7c7b` (корень) | `AGENTS.md` → `bareapi.shop/captchas`; `dataset/out_ru/BARE-API/{ru-numberword,ru-numberword-caption,ru-object-swatch,ru-symbols,ru-web}/labels.jsonl` — **500 строк** с `bareapi`/`BARE-API` в поле `source`; `research/bareapi_captchas.html` — **511** ссылок `i.ibb.co` + **14** `i.postimg.cc`; `site/captchas/manifest.json`, `site/site_matches.json` — те же 511 URL; `research/bm_cookies.txt` — **живой cookie `mit_ck_p1`**; `research/bm_real.html` → `support@mitelis.net`, `cdn.mitelis.net`; `research/bm_fetch.py` → обход `mit_ck_p2`; **1240 чужих PNG** в `real_shots/`, 6489 PNG в дереве |
| `22ee3d4` | **+ `bench/probe_capmonster.py`** («Probe the CapMonster Cloud "Image to Text" service on our own captchas»); `reports/bench_models/capmonster_probe.md` (42 упоминания); `reports/bench_models/capmonster_probe_results.json` → `"api": "https://api.capmonster.cloud"`; URL `api.capmonster.cloud/createTask`, `/getTaskResult`, `docs.capmonster.cloud`, `github.com/CapMonsterCloud/*` |
| `3e4bbdc`, `c4de488` | «каталог-витрина» `site/` — 563…1182 файла, 7050 PNG, весь каталог запрещённого сервиса |

Счётчики совпадений по паттернам (по файлам-тарболлам):

| коммит | bareapi | bare-api | BARE-API | capmonster | mit_ck | i.ibb.co | i.postimg.cc | mitelis | support@ |
|---|---|---|---|---|---|---|---|---|---|
| `cfb7c7b` | 560 | 851 | 678 | 0 | 26 | 1534 | 55 | 9 | 3 |
| `22ee3d4` | 576 | 1020 | 847 | **60** | 27 | 1534 | 55 | 9 | 3 |

**Вердикт: блокирующий дефект.** Действие — удалить репозиторий и пересоздать (или GC через
GitHub Support), затем проверить 404 по всем 12 SHA.

### 1.3 ⛔ КРИТИЧНО: опубликованный `agents/AGENT_LOG.md` раздаёт SHA старой истории

| Находка | Где | Как проверить | Действие |
|---|---|---|---|
| 9 SHA старых коммитов, включая `22ee3d4` («CapMonster probe script») и `cfb7c7b` (корень с `bareapi`) | `agents/AGENT_LOG.md:248,249,250,259` | `git grep -I -n -E "(cfb7c7b\|22ee3d4\|3e4bbdc\|f5fc589)" origin/main` | вычистить SHA (заменить на «история переписана») **или** не публиковать `agents/AGENT_LOG.md` |
| SHA `7ffd0b8` | `reports/research2/T1_models_test.md:163` | тот же grep | вычистить |

### 1.4 Нечёткие шаблоны — совпадения есть, но это **другие** сервисы

Проверенные шаблоны `captcha-service`, `solver-api`, `api-key`, `clientKey`,
`anti-captcha`, `rucaptcha`, `2captcha`, `killcaptcha` дали совпадения **только в отчётах
исследования рынка** и указывают на **других** коммерческих солверов, не на запрещённый:

| Находка | Где | Как проверить | Действие |
|---|---|---|---|
| `anti-captcha` (3 URL), `2captcha` (3), `capsolver.com` (1), `opencaptcha.io` (2) — конкуренты в обзоре рынка | `reports/CAPTCHA_SYSTEM_OVERVIEW.md:360,489,490,495`, `reports/research/00_SYNTHESIS.md:240,241,382`, `reports/research/briefs/E_unknown_plugin_pipeline.md:20,23`, `reports/research2/A_ready_projects.md:16,41,44,46,355,367`, `CONTINUE.md:120` | `git grep -I -n -i -E "anti-captcha\|2captcha\|capsolver\|opencaptcha" origin/main` | **ложное срабатывание** (не запрещённый сервис). Но это **решение автора**: называть конкурентов поимённо в публичном лабораторном отчёте — нормально или нет. Тексты — из чужого рынка, а не из вашего эксперимента; автору стоит либо оставить, либо обезличить |
| `mit_ck_p1` / `mit_ck_p2` (cookie-челлендж) | **только** в старой истории (`research/bm_cookies.txt`, `AGENTS.md` старого коммита) | см. 1.2 | исчезнет вместе с репозиторием |

### 1.5 Полный список внешних URL — см. **Приложение A** (667 уникальных URL, 116 хостов)

Оценка хостов: `github.com` (451), `huggingface.co` (383), `arxiv.org` (273),
`spigotmc.org`/`spigotmc.ru` (64 — сайты плагинов), `onnxruntime.ai`, `paddleocr.ai`,
`pypi.org`, `raw.githubusercontent.com`, `modrinth.com`, `spiget.org`, `mcreference.com`,
`thecvf.com`, `acm.org`, `web.archive.org`, `gnu.org`, `wikipedia.org`, `distill.pub`,
`nvidia.com` — **нормальные ссылки на документацию, статьи, репозитории плагинов и
лицензии**. Единственные «непривычные» хосты — поисковики, которыми пользовались
исследовательские скрипты (`rightdao.com`, `gibiru.com`, `nova.rambler.ru`, `priv.au`,
`go.mail.ru`, `yandex.ru`, `searx.be`, `search.marginalia.nu`) и сайты Minecraft-ресурсов
(`mcbase.ru`, `mcmodshub.com`, `craftit.ru`, `mcorep.ru`, `dandynes.ru`, `spigotunlocked.com`,
`rubukkit.org`, `minecraftforum.ru`, `hangar.papermc.io`) — **это не следы сервиса**,
это инструменты поиска апстримов. `elytrium.net` — сайт автора LimboFilter (MIT/AGPL-апстрим,
упоминание законное и нужное). `127.0.0.1:3080` — локальный адрес GUI-харнесса (см. 2.2).

---

## 2. Персональные данные и секреты

### 2.1 Секреты — **настоящих нет**

| Проверка | Команда | Результат |
|---|---|---|
| Токены HF/GH | `git grep -I -n -E "ghp_\|gho_\|ghu_\|ghs_\|github_pat_\|sk-[A-Za-z0-9]{16}\|hf_[A-Za-z0-9]{20,}\|AKIA[0-9A-Z]{16}\|-----BEGIN\|xox[baprs]-\|eyJ[A-Za-z0-9_-]{10}" origin/main` | 5 совпадений — **все** это плейсхолдеры `hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx` в `tools/PUBLISH_HF.md:16,22` и `tools/publish_hf.py:260,264,268`. Реальных токенов нет |
| `.env`, `*.pem`, `*.key`, `id_rsa` | `git ls-files \| Select-String "\.env\|\.pem\|\.key$\|id_rsa"` | **пусто** |
| Кэш HF в индексе | `git ls-files \| Select-String "hf-cache\|token"` | **пусто** — `.hf-cache/` в `.gitignore` (строка «The Hugging Face model cache») |
| `password`, `secret`, `token=` | `git grep -I -n -i -E "password\|secret\|token=" origin/main` | совпадений с секретами нет (см. 2.2 про `HF_TOKEN` — это имя переменной окружения, не значение) |
| Почтовый адрес автора | `git grep -I -n "93156853@users.noreply.github.com" origin/main` | **пусто** |
| `Titlehhhh` (ник GitHub) | 10+ вхождений | **ок** — ник GitHub виден всем по определению |

### 2.2 ⚠️ Персональные пути — есть, и их много

| Находка | Где | Как проверить | Действие |
|---|---|---|---|
| **Windows-имя пользователя и домашние пути харнесса** (20+ вхождений): `C:\Users\Title\deepseek-harness`, `C:\Users\Title\.dsh\profiles\web\cordis.patch.yml`, `C:\Users\Title\AppData\Local\npm-cache\_npx\1e7f6d9597241db0\...`, версия `@deepseek-ai/dsh 0.2.1-rc.2`, **маршрут модели `openrouter → minimax/minimax-m3.1-flash:free`**, путь к профилю и `.agent-presets` | `agents/DSH_HARNESS.md:15,23,24,26,27,29,30,59,75,121,170,174,208,249,360,424` | `git grep -I -n -E "[A-Za-z]:[\\/]+Users[\\/]" origin/main` | **Убрать `agents/DSH_HARNESS.md` из публичного репозитория целиком** — это внутренняя документация рабочего окружения, постороннему она ничего не даёт, а публикует имя пользователя, структуру домашней папки и провайдера/ключ модели. Если файл нужен — оставить локально и добавить в `.gitignore` |
| Личный путь к проекту | `CONTINUE.md:23`, `HANDOVER.md:3`, `docs/ONBOARDING.md:4`, `agents/INDEX.json:3` (`"repo": "C:\\Users\\Title\\Projects\\CaptchaOCR"`), `bench/bench_models.py:274` (`C:\Users\Title\.cache\huggingface`) | тот же grep | заменить на относительные пути / `$env:USERPROFILE` |
| Хардкод `C:\Users\Title\Projects\CapthaModel\...` в исследовательских скриптах | `research/tools/engine_probe.py:16,21,26,31`, `research/tools/respages.py:8`, `research/tools/respages2.py:8`, `research/tools/spigotru2.py:23` (и, по образцу, остальные `research/tools/*.py`) | тот же grep | заменить на `Path(__file__).resolve().parents[2]` — скрипты всё равно пишут файлы |
| Нестандартный диск `I:\ForAndroid\Java\21` | `AGENTS.md:159,213`, `README.md:218,222`, `agents/INDEX.md:394,509`, `agents/AGENT_LOG.md:49`, `dataset/generator/AGENTS.md:69`, `docs/ONBOARDING.md:47,58`, `build.ps1:14`, `llms.txt:45`, `.agents/skills/captcha-dataset/SKILL.md:14,36` | `git grep -I -n "I:\\\\ForAndroid" origin/main` | **низкий риск** (не имя пользователя, а раскладка дисков). В README уже заменено на `$env:JAVA_HOME` в несохранённой правке — доделать то же в остальных 8 местах |
| Имя локальной папки `CapthaModel` (отличается от публичного `CaptchaOCR`) | карточка модели на HF: «Both sources are files in the **CapthaModel** project repository» | `web_fetch` карточки | мелочь, но поправьте на «CaptchaOCR» |
| `research/runtime/native/config.json` | содержит только конфиг модели (charset, путь к чекпоинту `train/run/main/ckpt/step_0005700.pt`, размер onnx) | прочитан целиком | **ок**, секретов нет |

---

## 3. Мусор, размеры и дубликаты

**Состав опубликованного дерева:** 741 элемент, из них **521 blob, 24 269 801 байт (24.27 МБ)**.
Распределение: `dataset/` — 318, `reports/` — 75, `research/` — 46, `tools/` — 32,
`train/` — 16, `bench/` — 11, `docs/` — 7, `agents/` — 6.

### 3.1 Файлы > 1 МБ — их всего **два**

| Размер | Файл | Вердикт |
|---|---|---|
| **2 673 704** (2.55 МБ) | `reports/roi_bands_minimal.png` | **оставить** — иллюстрация к разбору полос. Опционально пережать в PNG8 (визуально тот же результат, ~200 КБ) |
| **2 346 567** (2.24 МБ) | `reports/roi_bands_borderline.png` | **оставить** (то же) |
| 854 823 | `reports/bench_models/anuashok-v3.json` | оставить (измерение) |
| 851 399 | `reports/bench_models/emelnov-mailru.json` | оставить |
| 850 638 | `reports/bench_models/doctr-crnn-ru.json` | оставить |
| 846 359 | `reports/bench_models/grafj-crnn-base.json` | оставить |
| 844 912 | `reports/bench_models/grafj-crnn.json` | оставить |
| 843 096 | `reports/bench_models/ppocrv6-medium.json` | оставить |
| 841 720 | `reports/bench_models/ppocrv5-cyrillic.json` | оставить |
| 840 302 | `reports/bench_models/ppocrv5-mobile.json` | оставить |
| 839 047 | `reports/bench_models/grafj-convtr.json` | оставить |
| 832 314 | `reports/bench_models/txtcaptcha-crnn.json` | оставить |
| 713 072 | `reports/augmented_minimal.png` | оставить |
| 686 493 | `reports/augmented_minimal_noaffine.png` | оставить |
| 564 962 | `reports/roi_frames_minimal.png` | оставить |
| 445 638 | `reports/research/00_SYNTHESIS.pdf` | оставить |
| 321 082 | `reports/captcha_pdf_embedded.html` | оставить |
| 310 112 | `reports/image_b64.json` | **мусор** — дамп base64; генерируется заново, в репозитории не нужен → **удалить** |
| 285 939 | `reports/bench_models/trocr-base-printed.json` | оставить |
| 229 409 | `reports/eval_main_final.json` | оставить |

* 9 бенч-JSON по ~840 КБ = **7.5 МБ** — это per-sample результаты. По правилам репозитория
  `reports/` хранит измеренные результаты, и они их же корректируют. **Оставить**, но если
  хочется уменьшить репозиторий — вынести per-sample записи в один отдельный файл.
* **Файлов > 100 МБ нет** → лимит GitHub не нарушен.
* `size` репозитория по API GitHub = **152 927 КБ (149 МБ)** — это старые объекты в базе
  GitHub (см. 1.2), а не текущая ветка. Достижимое дерево — 24 МБ.

### 3.2 Дубликаты и мусор

| Находка | Где | Как проверить | Вердикт |
|---|---|---|---|
| **5 пар байт-в-байт одинаковых PNG** (`mine-*.png` ≡ `ref-*.png`, MD5 совпадает по всем 5 парам) | `research/myout/` ↔ `research/refout/` | `Get-FileHash research\myout\*.png,research\refout\*.png -Algorithm MD5` | **удалить одну из папок** (5 КБ, но это чистка) |
| `*.log`, `*.tmp`, `*~`, `*.ipynb`, `*.rar`, `*.jar` в индексе | — | `git ls-files \| Select-String "\.log$\|\.tmp$\|~$\|\.ipynb$"` | **пусто** — чисто |
| Файлы вне индекса, которые уедут при `git add -A` | — | `git ls-files --others --exclude-standard` | **пусто** — ничего лишнего не уедет |
| Скомпилированный `__pycache__/*.pyc` **с запрещёнными следами** в рабочем дереве (не в git!) | `tools/__pycache__/cluster_site_captchas.cpython-314.pyc` → `bareapi.shop`; `tools/__pycache__/restore_real_shots.cpython-314.pyc` → `bareapi.shop`, `BARE-API`; `bench/__pycache__/probe_capmonster.cpython-314.pyc` → `api.capmonster.cloud/createTask` | сканирование рабочего дерева | **не публикуется** (`__pycache__/` в `.gitignore`), но это **мина**: если кто-то сделает `git add -f` или поменяет ignore — следы уедут. **Рекомендация: удалить `__pycache__` из рабочего дерева** (он и так не нужен) |
| `research/jars/`, `research/cfr.jar`, `research/decompiled/`, `research/cvz*/` | `.gitignore` | `git ls-files \| Select-String "research/jars\|cfr\|decompiled"` | **пусто** — покрыто игнором |
| `reports/research3/PUBLIC_REPO_AUDIT.md` | — | поиск по дереву GitHub | **удалён** из публикации (0 совпадений) |

### 3.3 Технические риски публикации

| Проверка | Результат |
|---|---|
| `.gitignore` покрывает `.hf-cache/` | **да** (комментарий «The Hugging Face model cache») — и `git ls-files` показывает, что в индексе его нет |
| `.gitignore` покрывает `train/run*/`, чекпоинты, веса | **да**: `train/run/`, `train/run_ppocr/`, `train/*/ckpt/`, `*.pt`, `*.pth`, `*.onnx`. В опубликованном `train/` — только 16 `.py`/`.md`, ни одного веса |
| `.gitignore` покрывает `build/` | **да** (`build/`, `*.class`) |
| `.gitignore` покрывает `dataset/out/**.png`, `dataset/out_ru/**.png` | **да** — в индексе только `labels.jsonl` + 230 PNG витрины `dataset/samples/` |
| `.gitignore` покрывает `tmp/`, `tmp*/`, `*.log`, `.DS_Store`, `Thumbs.db` | **да** |
| Файлы > 100 МБ в индексе | **нет** |
| Чужие скриншоты (`real_shots/`) в индексе | **нет**: в дереве только 6 README-заглушек (`BotFilter`, `Captcha`, `CaptchaGUI`, `CaptchaVerifyZ`, `SmartCaptcha`, `WeatherActionCaptcha`) + `tools/restore_real_shots.py`. Ни одного PNG |
| Локальный `git fsck --unreachable --dangling` | **пусто** — локальная копия чистая; проблема только на сервере |

---

## 4. Правовые риски

### 4.1 `research/limbofilter/*.java` — декомпиляция AGPL-3.0 (чужая работа) — ⚠️ высокий риск

6 файлов, 56 348 байт: `CaptchaGenerator.java` (17 413), `Settings.java` (21 019),
`CaptchaPainter.java` (8 404), `RippleEffect.java` (4 439), `RenderedFont.java` (3 923),
`OutlineEffect.java` (1 909). В заголовке каждого — **неотретушированный копирайт
Elytrium и полный текст GNU AGPL-3.0**:

```java
/* Copyright (C) 2021 - 2025 Elytrium
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU Affero General Public License ... */
package net.elytrium.limbofilter.captcha.painter;
```

**Оценка.** Публикация декомпилированного кода AGPL-проекта — самый чувствительный пункт
из всех: (1) это производная работа чужого AGPL-кода; (2) AGPL требует распространять её
на тех же условиях, то есть репозиторий должен быть AGPL-3.0 (весь код, не только папка),
а для сетевого использования — предоставлять исходники пользователям; (3) декомпиляция
сама по себе не даёт прав на перелицензирование, даже если заголовки сохранены. При этом
проект заявляет AGPL-3.0 и для *типов капт* LimboFilter (`labels.jsonl` → `source` →
`net.elytrium.limbofilter.captcha.painter.CaptchaPainter#drawCaptcha`), т.е. AGPL-по-
производные уже публикуются на HF — это отдельный, но родственный вопрос (см. 4.3).

**Действие (варианты, по возрастанию трудозатрат):**
- **(A) Удалить `research/limbofilter/`** из публичного дерева (оставить локально) и
  заменить в `research/RU_CAPTCHA_SOURCES.md` / `reports/LIMBOFILTER_IDENTIFICATION.md`
  ссылку на `https://github.com/Elytrium/LimboFilter` + описание алгоритма своими словами.
  **Рекомендую.**
- **(B) Оставить с атрибуцией** — тогда: добавить `LICENSE` (AGPL-3.0) в корень,
  `SPDX-License-Identifier: AGPL-3.0-only` в каждый файл, явный блок «This file is a
  decompiled excerpt of Elytrium/LimboFilter, © Elytrium, AGPL-3.0» и ссылку на upstream.
  Публикация тогда законна, но требует перелицензирования **всего** репозитория.
- **(C) Оставить как есть** — риск: претензия правообладателя (весь проект из-за папки).

### 4.2 Чужие картинки: `dataset/out_ru/*/real_shots/`

**В публику не уходят** — в дереве GitHub только README-заглушки, PNG исключены
(`.gitignore`: `dataset/out_ru/**/*.png`). Это **правильно**. Атрибуция при этом есть и
в README (`README.md:223`: «эталонные скриншоты `real_shots/` — чужие скриншоты в публику не
идут»), и в README-заглушках:

| Каталог (в публику) | Что сказано в заглушке | Оценка |
|---|---|---|
| `dataset/out_ru/BotFilter/real_shots/README.md` | «510 captcha PNGs that the BotFilter plugin actually produced, recovered from the community dataset `github.com/ServerSideProject/botfilter_captcha_dataset` — **MIT, 2022**» | атрибуция и лицензия указаны. Но README ссылается на `research/jars/botfilter_captcha_dataset.rar` и `research/jars/bf_dataset/` — **этих путей в публичном репозитории нет** (`research/jars/` в `.gitignore`) → битая ссылка в публичном README. **Действие: поправить текст** («в рабочей копии автора») |
| `dataset/out_ru/WeatherActionCaptcha/real_shots/README.txt` | два кадра из YouTube-роликов, канал/автор названы, происхождение описано; сам плагин — с spigotmc.ru | атрибуция корректная; YouTube-кадры — цитата для идентификации, не перепубликация. **Но `README.txt` в кодировке, которую читает как mojibake** (`РљРѕСЂ...` = «Капча») — файл записан в windows-1251 и показан как UTF-8. **Действие: перекодировать в UTF-8** |

### 4.3 Лицензии данных — таблица есть, риск управляем

`reports/`, README и HF-карточка дают лицензию **по каждому типу**: MIT (11 плагинов),
GPL-3.0 (3), AGPL-3.0 (LimboFilter), CC0-1.0 (jSdCool), BSD-2-Clause + запрет на
коммерческий хостинг (BotFilter), и **8 типов без лицензии («all rights reserved»)**
(`Archy-X/Krypton`, `CaptchaGUI`, `CaptchaVerifyZ`, `Yukun99`, `ringoame196`,
`GalleryCaptcha` ×5). Для последних карточка честно пишет «не установлена».

**Оценка:** публикация собственных **рендеров** чужих алгоритмов — наименее рискованный
вариант, но «all rights reserved» означает, что у автора **нет** права публиковать даже
перерисовку, если это производная работа. Для 8 типов это юридически тонко.
**Действие (решение автора):** в HF-карточке для каждого из этих 8 типов либо (а) собрать
разрешение, либо (б) убрать эти типы из публичного датасета, либо (в) оставить явную
оговорку «no licence — published for research, ask the author». Сейчас в карточке есть
таблица с лицензиями и фраза «A user of this dataset must comply with the licence of the
plugin each row came from» — это правильный каркас, но не замена праву на публикацию.
Отдельно: AGPL-типы LimboFilter (4 типа, 400 PNG) выложены с формулировкой «clean-room
reconstruction» — для AGPL «clean-room» не снимает AGPL, если рендер воспроизводит
защищённую работу; **либо** распространите AGPL-3.0 на датасет целиком, **либо**
перерисуйте иначе.

### 4.4 Прочее

- `dataset/samples/**` (230 PNG) — собственные рендеры генераторов, в README витрина с
  золотыми ответами. Правообладателя не нарушают.
- Данные, полученные **обходом** cookie-челленджа чужого сайта, остались только в старой
  истории (`research/bm_*`, `site/captchas/*`). После удаления репозитория — исчезают.
  В опубликованном дереве — чисто.

---

## 5. Публикации на Hugging Face

### 5.1 Датасет `Titlehhhh/captchaocr-dataset` — **чисто**

| Проверка | Результат |
|---|---|
| `GET /api/datasets/Titlehhhh/captchaocr-dataset` | `private: false`, создан 2026-10-22, `usedStorage` 46 049 012 Б (46 МБ), `license: other / mixed-per-plugin-licences` |
| Состав | `data/out/**` (34 типа × 100 PNG + `labels.jsonl`), `data/out_ru/**` (12 × 100), `README.md` (24 565 Б), `dataset_inventory.json` (53 721 Б) |
| Карточка | следов сервиса **нет**, личных путей **нет**, «Every PNG here is our own render», «No picture, page or answer taken from a third-party service is published here», «the reference screenshots … stay in the project's working tree» — честно |
| `labels.jsonl` × 3 типа (`out_ru/LimboFilter/map`, `out/haq/mapcha/map`, `out_ru/BotFilter/map`) | `source` содержит **только** `класс#метод` апстрима (`net.elytrium.limbofilter.captcha.painter.CaptchaPainter#drawCaptcha; …`, `dev.affan.mapcha.player.CaptchaPlayer#generateCaptcha`, `ru.leymooo.botfilter.captcha.generator.CaptchaPainter#draw`) — **ни URL, ни имён сервисов**. Строка `source` — это аудит-тропа, а не ссылка |
| `dataset_inventory.json` | машинная сводка (счётчики, алфавиты, лицензии), следов нет |

**Риск:** лицензионный (4.3) — 8 типов без лицензии. Не гигиенический.

### 5.2 Модель `Titlehhhh/captchaocr-ppocrv6` — **карточка честная, но репозиторий пустой**

| Проверка | Результат |
|---|---|
| `GET /api/models/Titlehhhh/captchaocr-ppocrv6` | `private: false`, `usedStorage: 0`, `license: apache-2.0`, `pipeline_tag: image-to-text`, `base_model: PaddlePaddle/PP-OCRv6_medium_rec_safetensors`, тег `base_model:finetune:…` |
| Состав | **только** `.gitattributes` и `README.md` (8 936 Б) — **весов нет, `config.json` нет** |
| Карточка | прямо признаёт: «the weights are **not published yet** … there is no checkpoint, no `config.json` and no measured metric … Nothing here is invented» и (RU) «репозиторий модели пока **пуст по весам**» — это хорошо и честно |
| **Проблема 1** | YAML-метка `base_model: …` + тег `base_model:finetune:…` делают карточку похожей на **готовую модель** в листинге HF, хотя весов нет. Для публикации «обещания без весов» лучше снять `base_model:`/`finetune`-теги, пока чекпоинта нет |
| **Проблема 2** | Раздел «Measured results» ссылается на `train/run_ppocr/` (zero-step baseline: 0.5586 / 0.60 / 0.2561) — а `train/run*/` **в `.gitignore`**, т.е. **эти измерения не опубликованы и не проверяемы**. Либо приложить zero-step baseline в репозиторий, либо сослаться на публикуемый источник |
| **Проблема 3** | «Both sources are files in the **CapthaModel** project repository» — раскрывает локальное имя папки (вместо публичного `CaptchaOCR`) |
| Код в карточке | `from_pretrained("Titlehhhh/captchaocr-ppocrv6")` показан, но честно сказано, что грузить нечего. Дубликаты картинок в карточке нет |

---

## 6. Что НЕ проверено (границы аудита)

1. **Содержимое картинок глазами.** Ни один PNG не открывался — ни 230 в `dataset/samples/`,
   ни эталонные кадры `real_shots/` на диске, ни картинки в `reports/*.png`. Оценка
   «не выглядят ли они как снимки чужого сервиса» сделана **по именам, README-заглушкам и
   происхождению** (см. `tools/restore_real_shots.py`), а не по пикселям.
   → **требует глаз автора**: открыть `dataset/samples/**` (230 файлов) и убедиться, что
   среди них нет кадров, на которых видно UI/брендинг стороннего сервиса.
2. **Содержимое всех 4600 PNG датасета на HF** — открыты только 3 файла `labels.jsonl`;
   сами картинки не смотрелись. Проверка на «снимок чужого сервиса» по пикселям не делалась.
3. **Не проверено, остались ли на GitHub «висячие» объекты без коммита** (старые blob-объекты,
   не адресуемые через `commits/<sha>`). Проверены только коммиты. После удаления
   репозитория вопрос снимается сам.
4. **Не открывались глазами** `site/` из старой истории (563–1182 файла) — оценка по именам
   и грепам.
5. **Не читались целиком** 75 файлов `reports/` и 46 файлов `research/` — только grep по
   шаблонам; возможны содержательные/юридические проблемы, не выражающиеся в шаблонах.
6. **Не проверялись метаданные PNG** (EXIF/текстовые чанки) на наличие следов.
7. **Не проверялась приватность/доступность HF-репозиториев** (dataset-repo открыт для всех —
   это, видимо, задумано, но автору стоит подтвердить).
8. **Не проверялся `research/runtime/csharp/Program.cs`** (8 953 Б) — прочитан только
   `config.json`; в grep по запрещённым шаблонам чисто.

---

## Приложение A. Полный список внешних URL в опубликованном дереве

Снято из **опубликованной ветки `main`** (`git grep -I -o -E "https?://…" origin/main`),
уникальных — **667**, уникальных хостов — **116**.

**Сводка по хостам (частота → хост):**

```
451 github.com          383 huggingface.co     273 arxiv.org
 40 www.spigotmc.org     27 onnxruntime.ai      26 www.paddleocr.ai
 24 spigotmc.ru          23 pypi.org            20 raw.githubusercontent.com
 11 api.github.com        9 www.youtube.com       8 modrinth.com
  8 api.spiget.org        8 mcreference.com       7 openaccess.thecvf.com
  7 dl.acm.org            6 web.archive.org       6 onnx.ai
  6 lite.duckduckgo.com   6 datasets-server.huggingface.co
  6 www.gnu.org           5 pillow.readthedocs.io  5 rdrr.io
  5 api.modrinth.com      5 docs.pytorch.org      5 www.bing.com
  4 llmstxt.org           4 agents.md             4 agentsstandard.com
  4 cdn.spiget.org        4 sourcegraph.com       4 en.wikipedia.org
  4 distill.pub           4 docs.nvidia.com       4 searx.be
  3 repomix.com           3 anti-captcha.com      3 2captcha.com
  3 ar5iv.labs.arxiv.org  3 www.kaggle.com        3 ieee-dataport.org
  3 yandex.ru             3 www.google.com        3 search.marginalia.nu
  2 blog.buildbetter.ai   2 www.anthropic.com     2 adr.github.io
  2 khimananda.com        2 source.unsplash.com   2 www.spigotunlocked.com
  2 keras.io              2 cdn.modrinth.com      2 www.rubukkit.org
  2 opencaptcha.io        2 99franklin.github.io   2 www.researchsquare.com
  2 deepwiki.com          2 www.usenix.org        2 developers.google.com
  2 scikit-learn.org      2 rapidai.github.io     2 documentation.pw
  2 export.arxiv.org      2 registry.npmjs.org    2 grep.app
  2 www.startpage.com     2 rightdao.com          2 gibiru.com
  2 nova.rambler.ru       2 www.qwant.com         2 priv.au
  2 www.baidu.com         2 www.sogou.com
  1 127.0.0.1:3080        1 codex.danielvaughan.com
  1 geekworkbench.com     1 www.augmentcode.com   1 lobehub.com
  1 capsolver.com         1 elytrium.net          1 albumentations.ai
  1 mcbase.ru             1 mcmodshub.com         1 repo1.maven.org
  1 zyszys.github.io      1 llm-stats.com        1 presenc.ai
  1 textocr.github.io     1 tesseract-ocr.github.io
  1 aclanthology.org      1 www.mdpi.com          1 api.semanticscholar.org
  1 yadi.sk               1 webui.adventure.kyori.net
  1 minecraft.tools       1 media.discordapp.net  1 html.duckduckgo.com
  1 duckduckgo.com        1 www.mojeek.com        1 search.brave.com
  1 search.maven.org      1 api.qwant.com         1 www.ecosia.org
  1 searchcode.com        1 yep.com               1 search.lycos.com
  1 www.ask.com           1 go.mail.ru            1 www.craftit.ru
  1 hangar.papermc.io     1 api.spigotmc.org      1 hub.spigotmc.org
  1 www.minecraftforum.ru  1 mcorep.ru             1 dandynes.ru
  1 download.pytorch.org
```

**Оценка:** ни один хост не указывает на запрещённый сервис (`i.ibb.co`, `i.postimg.cc`,
`bareapi.shop`, `capmonster.cloud` в опубликованном дереве отсутствуют). `github.com`,
`huggingface.co`, `arxiv.org`, `spigotmc.org/ru`, `modrinth.com`, `pypi.org` — нормальные
ссылки. Поисковики (`rightdao`, `gibiru`, `priv.au`, `nova.rambler`, `go.mail.ru`,
`yandex.ru`, `searx.be`, `marginalia`, `duckduckgo`, `bing`, `startpage`, `qwant`,
`ecosia`, `lycos`, `ask`, `brave`, `mojeek`, `html.duckduckgo`, `lite.duckduckgo`) и
Minecraft-сайты (`mcbase.ru`, `mcmodshub.com`, `craftit.ru`, `mcorep.ru`, `dandynes.ru`,
`spigotunlocked.com`, `rubukkit.org`, `minecraftforum.ru`, `hangar.papermc.io`,
`minecraft.tools`) — рабочий инструментарий исследования, **не следы сервиса**.
`127.0.0.1:3080` — локальный адрес GUI (см. 2.2). `capmonster.com`/`anti-captcha.com`/
`2captcha.com`/`opencaptcha.io` — другие коммерческие солверы (см. 1.4).

<details>
<summary>Полный список 667 URL (разворачиваемый блок)</summary>


http://127.0.0.1:3080
http://web.archive.org/cdx/search/cdx?url=spigotmc.org/resources*
http://web.archive.org/web/2023/https://www.spigotmc.org/resources/1.captcha.1/
http://www.gnu.org/licenses/
http://www.rubukkit.org/threads/137038/
https://2captcha.com/h/what-is-a-captcha-solver
https://99franklin.github.io/ocrbench_v2/
https://aclanthology.org/2023.findings-acl.697/
https://adr.github.io/
https://agents.md/
https://agentsstandard.com/
https://albumentations.ai/docs/
https://anti-captcha.com/apidoc/task-types/ImageToTextTask
https://api.github.com/
https://api.github.com/repos/
https://api.github.com/repos/AttentionCaptcha/Captcha-images
https://api.github.com/search/repositories?q=%s&sort=stars&order=desc&per_page=100
https://api.github.com/search/repositories?q=Captcha-images+in:name
https://api.github.com/search/repositories?q=captchaverifyz
https://api.github.com/search/repositories?q=smartcaptcha
https://api.github.com/users/Supl1n/repos
https://api.modrinth.com/v2/project/e015SVoM
https://api.modrinth.com/v2/project/LbnXX4g9
https://api.modrinth.com/v2/project/LbnXX4g9/version
https://api.modrinth.com/v2/search?query=captcha
https://api.qwant.com/v3/search/web?q=
https://api.semanticscholar.org/graph/v1/paper/DOI:10.1145/3696409.3700215
https://api.spiget.org/v2/authors/317151
https://api.spiget.org/v2/authors/317151/resources
https://api.spiget.org/v2/resources/125355
https://api.spiget.org/v2/resources/70935
https://api.spiget.org/v2/search/resources/smartcaptcha?size=30
https://api.spigotmc.org/
https://ar5iv.labs.arxiv.org/html/1507.05717
https://ar5iv.labs.arxiv.org/html/1911.08947
https://arxiv.org/abs/1406.2227
https://arxiv.org/abs/1507.05717
https://arxiv.org/abs/1604.01653
https://arxiv.org/abs/1703.00868
https://arxiv.org/abs/1704.03155
https://arxiv.org/abs/1704.04811
https://arxiv.org/abs/1706.02737
https://arxiv.org/abs/1812.05824
https://arxiv.org/abs/1904.01941
https://arxiv.org/abs/1910.02562
https://arxiv.org/abs/1910.04396
https://arxiv.org/abs/1911.08947
https://arxiv.org/abs/2002.01276
https://arxiv.org/abs/2008.11603
https://arxiv.org/abs/2009.01766
https://arxiv.org/abs/2009.06488
https://arxiv.org/abs/2101.06329
https://arxiv.org/abs/2103.04400
https://arxiv.org/abs/2105.08582
https://arxiv.org/abs/2107.09313
https://arxiv.org/abs/2107.12087
https://arxiv.org/abs/2108.06949
https://arxiv.org/abs/2109.03144
https://arxiv.org/abs/2109.10282
https://arxiv.org/abs/2111.03664
https://arxiv.org/abs/2205.00159
https://arxiv.org/abs/2205.03873
https://arxiv.org/abs/2207.06966
https://arxiv.org/abs/2207.07048
https://arxiv.org/abs/2212.05525
https://arxiv.org/abs/2303.06946
https://arxiv.org/abs/2307.08723
https://arxiv.org/abs/2309.15963
https://arxiv.org/abs/2402.05417
https://arxiv.org/abs/2402.15806
https://arxiv.org/abs/2403.11578
https://arxiv.org/abs/2408.16930
https://arxiv.org/abs/2409.01704
https://arxiv.org/abs/2410.09913
https://arxiv.org/abs/2410.09913v3
https://arxiv.org/abs/2411.15858
https://arxiv.org/abs/2510.14528
https://arxiv.org/abs/2512.02318
https://arxiv.org/abs/2601.21957
https://arxiv.org/abs/2602.11988
https://arxiv.org/abs/2603.03580
https://arxiv.org/abs/2603.24373
https://arxiv.org/abs/2604.14314
https://arxiv.org/abs/2606.03264
https://arxiv.org/abs/2606.13108
https://arxiv.org/abs/2607.22708
https://arxiv.org/abs/2609.31957
https://arxiv.org/html/2008.11603v1
https://arxiv.org/html/2103.04400v2
https://arxiv.org/html/2107.09313v1
https://arxiv.org/html/2307.08723v2
https://arxiv.org/html/2410.09913v3
https://arxiv.org/html/2410.09913v3)):**
https://arxiv.org/html/2601.14277v1
https://arxiv.org/html/2603.24373v1
https://arxiv.org/pdf/1612.07828v1.pdf
https://blog.buildbetter.ai/agents-md-vs-cursorrules-vs-claude-skills-2026-comparison/
https://capsolver.com/
https://cdn.modrinth.com/data/LbnXX4g9/versions/dHdoDcmQ/CaptchaVerifyZ-1.4.jar
https://cdn.spiget.org/file/spiget-resources/70935.jar
https://codex.danielvaughan.com/2026/03/27/agents-md-bloat-problem/
https://dandynes.ru/
https://datasets-server.huggingface.co/info?dataset=AvinashRicky/CaptchaOCR-500K
https://datasets-server.huggingface.co/info?dataset=hammer888/captcha-data
https://deepwiki.com/Tencent/ncnn/4.4-int8-quantization-and-inference
https://developers.google.com/edge/litert
https://distill.pub/2017/ctc/
https://dl.acm.org/doi/10.1145/3696409.3700215
https://docs.nvidia.com/cuda/cuda-toolkit-release-notes/index.html
https://docs.pytorch.org/docs/2.14/amp.html
https://docs.pytorch.org/docs/stable/onnx_export.html
https://docs.pytorch.org/docs/stable/quantization.html
https://documentation.pw/versions.html
https://download.pytorch.org/whl/cu126
https://duckduckgo.com/html/?q=
https://elytrium.net/
https://en.wikipedia.org/wiki/Connectionist_temporal_classification
https://export.arxiv.org/api/query?search_query=all:%22Decomposed%20CTC%22
https://export.arxiv.org/api/query?search_query=ti:%22SATRN%22
https://geekworkbench.com/blog/technical/git-lfs-large-files/
https://gibiru.com/results.html?q=
https://github.com/0b01/SimGAN-Captcha
https://github.com/2captcha/2captcha-python
https://github.com/AakashKumarNain/CaptchaCracker/raw/master/captcha_images_v2.zip
https://github.com/agentsmd/agents.md
https://github.com/akiraly/cage
https://github.com/alibaba/MNN
https://github.com/alibaba/MNN/blob/master/README.md
https://github.com/a-maliarov/amazoncaptcha
https://github.com/AnswerDotAI/llms-txt
https://github.com/Archy-X/Krypton
https://github.com/ashtonav/opencaptcha
https://github.com/baudm/parseq
https://github.com/baud-xl/parseq
https://github.com/Bazskillz/captcha-crnn-solver
https://github.com/benjaminwan/OcrLiteAndroidOnnx
https://github.com/benjaminwan/OcrLiteNcnn
https://github.com/benjaminwan/OcrLiteOnnx
https://github.com/Botsailer/captcha-solver
https://github.com/Botsailer/captcha-solver)**
https://github.com/breezedeus/CnOCR
https://github.com/China2B2T/Captcha
https://github.com/clovaai/CRAFT-pytorch
https://github.com/clovaai/deep-text-recognition-benchmark
https://github.com/clovaai/SynthText
https://github.com/clovaai/synthtiger
https://github.com/cloverpray/deep-learning-captcha-ocr-tutorial
https://github.com/cosmos223/Captcha
https://github.com/CrispStrobe/CrispEmbed
https://github.com/CrispStrobe/CrispEmbed)**
https://github.com/datalab-to/surya
https://github.com/deepseek-ai/deepseek-harness
https://github.com/deepseek-ai/DeepSeek-OCR
https://github.com/deepseek-ai/DeepSeek-OCR-2
https://github.com/dessant/buster
https://github.com/deveshrohan/captcha-solver
https://github.com/DevSakio/Captcha
https://github.com/DionaMC/BungeeCord-BotFilter-ENG
https://github.com/docling-project/docling
https://github.com/eidonjoe/gm-captcha
https://github.com/Elytrium/LimboFilter
https://github.com/Elytrium/LimboFilter#readme
https://github.com/EVOL-ution/Captcha-Recognition-using-CRNN
https://github.com/facebookresearch/hiertext
https://github.com/faustomorales/keras-ocr
https://github.com/FeelingAlive0/AdvancedCaptcha
https://github.com/FlashVision/FlashOCR
https://github.com/GeorgeChan/captchapng
https://github.com/ggml-org/ggml
https://github.com/ggml-org/ggml/blob/master/docs/gguf.md
https://github.com/ggml-org/llama.cpp
https://github.com/ggml-org/llama.cpp/blob/master/docs/ops.md
https://github.com/ggml-org/llama.cpp/blob/master/README.md
https://github.com/ggml-org/llama.cpp/blob/master/tools/quantize/README.md
https://github.com/GiovanniEliasDaRosa/Image-Puzzle
https://github.com/githubharald/CTCDecoder
https://github.com/githubharald/CTCDecoder)**
https://github.com/google-ai-edge/mediapipe
https://github.com/Gregwar/Captcha
https://github.com/haq/mapcha
https://github.com/huggingface/transformers/blob/main/docs/source/en/custom_models.md
https://github.com/huggingface/transformers/blob/main/MIGRATION_GUIDE_V5.md
https://github.com/InstantlyMoist/Captcha
https://github.com/irootdev/AnBot
https://github.com/JaidedAI/EasyOCR
https://github.com/JasonLiTW/simple-railway-captcha-solver
https://github.com/joelparkerhenderson/architecture-decision-record
https://github.com/Joey61021/captcha
https://github.com/jonathan-kao/captcha-crnn-minimal
https://github.com/jonesdevelopment/sonar
https://github.com/J-Rios/multicolorcaptcha
https://github.com/jSdCool/minecaptcha
https://github.com/JSH32/Minecaptcha
https://github.com/jtrecenti/txtcaptcha
https://github.com/jtrecenti/txtcaptcha)**
https://github.com/just-captcha/ProstoCaptcha
https://github.com/k2-fsa/sherpa-onnx
https://github.com/kasuganosoras/MCreCaptcha_Server
https://github.com/KhaLee2307/StrDA
https://github.com/kingknight07/Deep-Captcha
https://github.com/ku21fan/STR-Fewer-Labels
https://github.com/ku21fan/STR-Fewer-Labels/blob/main/data.md
https://github.com/kuszaj/claptcha
https://github.com/laforetbrut/are-you-sure
https://github.com/LagBug/XProtect
https://github.com/lepture/captcha
https://github.com/Leymooo/BungeeCord
https://github.com/limingda1212/CapCRNN
https://github.com/lorien/captcha_solver
https://github.com/lorien/captcha_solver)**
https://github.com/Loyisa/BungeeCord-BotFilter-ZHCN
https://github.com/luojiucheng/LSVT
https://github.com/madmaze/pytesseract
https://github.com/max11-dev/Captcha
https://github.com/mbi/django-simple-captcha
https://github.com/MetaAgentX/NextGen-CAPTCHAs
https://github.com/MetaAgentX/OpenCaptchaWorld
https://github.com/microsoft/onnxruntime
https://github.com/microsoft/onnxruntime/blob/main/docs/OperatorKernels.md
https://github.com/microsoft/onnxruntime/blob/main/LICENSE
https://github.com/microsoft/onnxruntime/blob/main/onnxruntime/python/tools/quantization/operators/lstm.py
https://github.com/microsoft/onnxruntime/blob/main/onnxruntime/python/tools/quantization/registry.py
https://github.com/microsoft/onnxruntime/gh-pages/docs/execution-providers/CUDA-ExecutionProvider.md
https://github.com/microsoft/onnxruntime/gh-pages/docs/performance/model-optimizations/float16.md
https://github.com/microsoft/onnxruntime/gh-pages/docs/performance/model-optimizations/ort-format-models.md
https://github.com/microsoft/onnxruntime/issues/14439
https://github.com/microsoft/onnxruntime/issues/20052
https://github.com/microsoft/unilm
https://github.com/microsoft/unilm/tree/master/trocr
https://github.com/mikeyy/nonoCAPTCHA
https://github.com/mindee/doctr
https://github.com/mmeerrkkaa/funtime-captcha-verifed
https://github.com/Mountchicken/Union14M
https://github.com/Mrbysco/Captcha
https://github.com/n1zamu/NCaptcha
https://github.com/naptha/tesseract.js
https://github.com/naptha/tesseract.js-core
https://github.com/nbiish/agents-standard
https://github.com/nbswords/ocr-captchas
https://github.com/Nicbo/Captcha
https://github.com/Noonenowhoiam/WebSiteCpatcha
https://github.com/NopeCHALLC/nopecha-extension
https://github.com/NopeCHALLC/nopecha-extension)**
https://github.com/NopeCHALLC/nopecha-nodejs
https://github.com/NopeCHALLC/nopecha-python
https://github.com/openai/codex/issues/7138
https://github.com/opendatalab/OmniDocBench
https://github.com/open-mmlab/mmocr
https://github.com/openvinotoolkit/openvino
https://github.com/openvinotoolkit/openvino/blob/master/README.md
https://github.com/PaddlePaddle/Paddle2ONNX
https://github.com/PaddlePaddle/Paddle-Lite
https://github.com/PaddlePaddle/PaddleOCR
https://github.com/ptigas/simple-captcha-solver
https://github.com/pytorch/pytorch/blob/main/docs/source/onnx_export.md
https://github.com/pytorch/pytorch/blob/main/torch/ao/quantization/observer.py
https://github.com/Raffinert/FuzzySharp
https://github.com/ramSeraph/captchabreaker
https://github.com/RapidAI/RapidOCR
https://github.com/RapidAI/RapidOCR/tree/main/cpp
https://github.com/RapidAI/RapidOcrCpp
https://github.com/RapidAI/RapidOCRLite
https://github.com/RapidAI/RapidOcrNcnn
https://github.com/RapidAI/RapidOcrOnnx
https://github.com/RapidAI/RapidSpeech.cpp
https://github.com/rapidfuzz/RapidFuzz
https://github.com/rapidfuzz/rapidfuzz-cpp
https://github.com/rapidfuzz/rapidfuzz-rs
https://github.com/recaptchaUser/minecraft-captcha-solver
https://github.com/rednote-hilab/dots.ocr
https://github.com/reidjJava/Captcha
https://github.com/ringoame196-s-mcPlugin/ReproductionCAPTCHA
https://github.com/roatienza/straug
https://github.com/robatkins/GPT4o-Captcha-Bypasser
https://github.com/robatkins/GPT4o-Captcha-Bypasser)**
https://github.com/robertknight/tesseract-wasm
https://github.com/rockchip-linux/rknn-toolkit2
https://github.com/rockchip-linux/rknn-toolkit2/blob/master/LICENSE
https://github.com/roncuevas/Captchas
https://github.com/S1SYPHOS/php-simple-captcha
https://github.com/SantiagoDemattei/captcha-text-recognition
https://github.com/SanyumCode/captcha-crnn
https://github.com/sarvex/ocr-captcha
https://github.com/ServerSideProject/botfilter_captcha_dataset
https://github.com/Shashank3736/captcha-canvas
https://github.com/shenhao-stu/ohmycaptcha
https://github.com/shenhao-stu/ohmycaptcha)**
https://github.com/shved255/LofiWebCaptcha-Bukkit
https://github.com/shved255/LofiWebCaptcha-site
https://github.com/siwtom/captchas-solver_crnn
https://github.com/SJTU-DeepVisionLab/FreeReal
https://github.com/sml2h3/ddddocr
https://github.com/sml2h3/ddddocr)**
https://github.com/sun1638650145/CRNN
https://github.com/Supl1n/CaptchaGUI
https://github.com/Tencent/ncnn
https://github.com/Tencent/ncnn/blob/master/README.md
https://github.com/Tencent/ncnn/blob/master/src/layer/lstm.cpp
https://github.com/Tencent/ncnn/blob/master/src/layer/lstm.h
https://github.com/Tencent/ncnn/blob/master/src/layer/rnn.cpp
https://github.com/Tencent/ncnn/blob/master/tools/pnnx/README.md
https://github.com/Tencent/ncnn/wiki/quantized-int8-inference
https://github.com/tensorflow/tensorflow/blob/master/LICENSE
https://github.com/tesseract-ocr/tesseract
https://github.com/Titlehhhh/CaptchaOCR
https://github.com/Topdu/OpenOCR
https://github.com/Topdu/OpenOCR/blob/main/docs/svtrv2.md
https://github.com/uber-research/uber-text
https://github.com/Ucas-HaoranWei/GOT-OCR2.0
https://github.com/UCRAFTS/CaptchaPlugin
https://github.com/UCRAFTS/CaptchaService
https://github.com/UIPlugins/CaptchaAPI
https://github.com/verylovemetal/WeatherActionCaptcha
https://github.com/vinyzu-archive/Botright
https://github.com/walijoy/captcha-generator
https://github.com/X0X0X00/CaptchaArena
https://github.com/Xewdy444/Playwright-reCAPTCHA
https://github.com/xHossein/PyPasser
https://github.com/xuyaooo/DataAugOCR
https://github.com/yamadashy/repomix
https://github.com/Ymxer/BotFilter
https://github.com/YoGoUrT20/Minecraft-bypass-captcha-bot
https://github.com/Yukun99/Captchas
https://github.com/Yuliang-Liu/MultimodalOCR
https://github.com/Z4OLLIEZ4/reCaptcha
https://go.mail.ru/search?q=
https://grep.app/api/search?q=
https://hangar.papermc.io/
https://html.duckduckgo.com/html/?q=
https://hub.spigotmc.org/
https://huggingface.co/
https://huggingface.co/04RR/Florence-base-Captcha
https://huggingface.co/Acetde/captcha2broker
https://huggingface.co/allenai/Molmo-7B-D-0924
https://huggingface.co/AndresDev/captCHAD
https://huggingface.co/antflydb/Florence-2-base
https://huggingface.co/anthrapper/tcrocr-captcha
https://huggingface.co/anuashok/ocr-captcha-v2
https://huggingface.co/anuashok/ocr-captcha-v3
https://huggingface.co/api/datasets/AvinashRicky/CaptchaOCR-500K
https://huggingface.co/api/datasets/hammer888/captcha-data
https://huggingface.co/api/datasets/NNEngine/Captcha-OCR
https://huggingface.co/api/datasets/NNEngine/Captcha-OCR/tree/main
https://huggingface.co/api/datasets/project-sloth/captcha-images
https://huggingface.co/api/datasets/remiai3/synthetic-captchas-library
https://huggingface.co/api/datasets/squirelmail/dataset-BotDetect-CAPTCHA-Generator
https://huggingface.co/api/datasets/squirelmail/dataset-BotDetect-CAPTCHA-Generator/tree/main/data
https://huggingface.co/api/datasets/szili2011/captcha-ocr-dataset
https://huggingface.co/api/datasets/Titlehhhh/captchaocr-dataset
https://huggingface.co/api/datasets?search=captcha&limit=50&sort=downloads
https://huggingface.co/api/datasets?search=captcha&limit=50&sort=downloads&direction=-1
https://huggingface.co/api/models/
https://huggingface.co/api/models/PaddlePaddle/PP-OCRv6_medium_rec
https://huggingface.co/api/models/PaddlePaddle/PP-OCRv6_medium_rec/tree/main
https://huggingface.co/api/models/PaddlePaddle/PP-OCRv6_medium_rec_safetensors
https://huggingface.co/api/models?search=captcha&limit=100
https://huggingface.co/api/models?search=crnn&limit=50&sort=downloads
https://huggingface.co/api/models?search=dots.ocr&limit=20
https://huggingface.co/api/models?search=PP-OCR&limit=50&sort=downloads
https://huggingface.co/api/models?search=PP-OCRv6&limit=20
https://huggingface.co/api/models?search=trocr&limit=100&sort=downloads
https://huggingface.co/arkhabbazan/ocr-digits-captcha
https://huggingface.co/arkhabbazan/ocr-math-captcha
https://huggingface.co/ATH-MaaS/CaptchaMind-7B
https://huggingface.co/ayoubkirouane/moondream2-image-captcha
https://huggingface.co/CaptchaKraken/CaptchaKraken-v1.2-GGUF
https://huggingface.co/chanelcolgate/trocr-base-printed_captcha_ocr
https://huggingface.co/collections/PaddlePaddle/pp-ocrv6
https://huggingface.co/confiacompany/confia-captcha-ocr-pt
https://huggingface.co/cstr/dbnet-ic15-GGUF
https://huggingface.co/cstr/got-ocr2-crispembed-GGUF
https://huggingface.co/cstr/PP-OCRv6_medium_rec-GGUF
https://huggingface.co/cstr/PP-OCRv6_tiny_rec-GGUF
https://huggingface.co/cstr/trocr-base-printed-GGUF
https://huggingface.co/cstr/trocr-small-printed-GGUF
https://huggingface.co/datalab-to/indra-ocr
https://huggingface.co/datasets/ATH-MaaS/Captcha
https://huggingface.co/datasets/AvinashRicky/CaptchaOCR-500K
https://huggingface.co/datasets/Capycap-AI/CaptchaSolve30k
https://huggingface.co/datasets/cybertruck32489/captcha_100k
https://huggingface.co/datasets/FlanChanXwO/phpwind-captcha-dataset
https://huggingface.co/datasets/hammer888/captcha-data
https://huggingface.co/datasets/inclusionAI/VenusBench-CAPTCHA
https://huggingface.co/datasets/Knight07/Deep_Captcha
https://huggingface.co/datasets/langningchen/luogu-captcha-dataset
https://huggingface.co/datasets/NNEngine/Captcha-OCR
https://huggingface.co/datasets/OpenCaptchaWorld/Open_CaptchaWorld
https://huggingface.co/datasets/priyank-m/MJSynth_text_recognition
https://huggingface.co/datasets/project-sloth/captcha-images
https://huggingface.co/datasets/remiai3/synthetic-captchas-library
https://huggingface.co/datasets/remiai3/synthetic-captchas-library/raw/main/README.md
https://huggingface.co/datasets/remiai3/tiny-captcha-library
https://huggingface.co/datasets/squirelmail/dataset-BotDetect-CAPTCHA-Generator
https://huggingface.co/datasets/szili2011/captcha-ocr-dataset
https://huggingface.co/datasets/szili2011/captcha-ocr-dataset/raw/main/README.md
https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset
https://huggingface.co/datasets/yuxi5/text-captcha-data-clean
https://huggingface.co/datasets/ZHEN-04/CaptchaArena
https://huggingface.co/datasets/ZHEN-04/CaptchaArena-Trajectories
https://huggingface.co/datasets?search=captcha
https://huggingface.co/dathuynh1108/ocr-captcha-v3-finetuned
https://huggingface.co/deepseek-ai/DeepSeek-OCR
https://huggingface.co/docparser/captcha
https://huggingface.co/docs/datasets/stream
https://huggingface.co/docs/transformers/index
https://huggingface.co/docs/transformers/main/en/model_doc/pp_ocrv6
https://huggingface.co/dots-studio/dots.ocr
https://huggingface.co/dragonstar/image-text-captcha-v2
https://huggingface.co/ds4sd/SmolDocling-256M-preview
https://huggingface.co/DunnBC22/trocr-base-printed_captcha_ocr
https://huggingface.co/emelnov/ocr-captcha-v4-mailru
https://huggingface.co/farhad-hasankhani/qwen2-7b-instruct-trl-sft-captcha
https://huggingface.co/Felix92/doctr-torch-parseq-multilingual-v1
https://huggingface.co/FlanChanXwO/phpwind-captcha-ocr
https://huggingface.co/Gavin-chen/captcha_i2t
https://huggingface.co/Graf-J/captcha-conv-transformer-base
https://huggingface.co/Graf-J/captcha-conv-transformer-finetuned
https://huggingface.co/Graf-J/captcha-crnn-base
https://huggingface.co/Graf-J/captcha-crnn-base/raw/main/config.json
https://huggingface.co/Graf-J/captcha-crnn-finetuned
https://huggingface.co/graycat660/doctr-crnn-vgg16-bn-russian-onnx
https://huggingface.co/ha4219/yes24-captcha
https://huggingface.co/haloworker/td-captcha-model-v1
https://huggingface.co/hongyusir/trocr-base-printed_captcha_ocr
https://huggingface.co/join
https://huggingface.co/jtrecenti/txtcaptcha-crnn
https://huggingface.co/keras-io/ocr-for-captcha
https://huggingface.co/krotreaksmey/TinyOCRkhmer
https://huggingface.co/langningchen/luogu-captcha-model
https://huggingface.co/luckystars0612/trocr-finetuned-captcha
https://huggingface.co/microsoft/Florence-2-base
https://huggingface.co/microsoft/Florence-2-base-ft
https://huggingface.co/microsoft/Florence-2-large
https://huggingface.co/microsoft/Phi-4-multimodal-instruct
https://huggingface.co/microsoft/trocr-base-handwritten
https://huggingface.co/microsoft/trocr-base-printed
https://huggingface.co/microsoft/trocr-base-stage1
https://huggingface.co/microsoft/trocr-small-handwritten
https://huggingface.co/microsoft/trocr-small-printed
https://huggingface.co/microsoft/trocr-small-stage1
https://huggingface.co/models/DunnBC22/trocr-base-printed_captcha_ocr
https://huggingface.co/models/keras-io/ocr-for-captcha
https://huggingface.co/mradermacher/dots.ocr-GGUF
https://huggingface.co/muratatceken/captcha-recognition
https://huggingface.co/opendatalab/MinerU2.5-2509-1.2B
https://huggingface.co/OpenGVLab/InternVL3-8B
https://huggingface.co/PaddlePaddle/cyrillic_PP-OCRv5_mobile_rec
https://huggingface.co/PaddlePaddle/cyrillic_PP-OCRv5_mobile_rec_onnx
https://huggingface.co/PaddlePaddle/cyrillic_PP-OCRv5_mobile_rec_safetensors
https://huggingface.co/PaddlePaddle/en_PP-OCRv4_mobile_rec
https://huggingface.co/PaddlePaddle/en_PP-OCRv5_mobile_rec
https://huggingface.co/PaddlePaddle/en_PP-OCRv5_mobile_rec_safetensors
https://huggingface.co/PaddlePaddle/eslav_PP-OCRv5_mobile_rec
https://huggingface.co/PaddlePaddle/eslav_PP-OCRv5_mobile_rec_safetensors
https://huggingface.co/PaddlePaddle/latin_PP-OCRv3_mobile_rec
https://huggingface.co/PaddlePaddle/latin_PP-OCRv5_mobile_rec
https://huggingface.co/PaddlePaddle/latin_PP-OCRv5_mobile_rec_onnx
https://huggingface.co/PaddlePaddle/latin_PP-OCRv5_mobile_rec_safetensors
https://huggingface.co/PaddlePaddle/PaddleOCR-VL
https://huggingface.co/PaddlePaddle/PaddleOCR-VL-1.5
https://huggingface.co/PaddlePaddle/PaddleOCR-VL-1.6
https://huggingface.co/PaddlePaddle/PP-OCRv3_mobile_rec
https://huggingface.co/PaddlePaddle/PP-OCRv4_mobile_rec
https://huggingface.co/PaddlePaddle/PP-OCRv4_server_rec
https://huggingface.co/PaddlePaddle/PP-OCRv5_mobile_rec
https://huggingface.co/PaddlePaddle/PP-OCRv5_mobile_rec_onnx
https://huggingface.co/PaddlePaddle/PP-OCRv5_mobile_rec_safetensors
https://huggingface.co/PaddlePaddle/PP-OCRv5_server_rec
https://huggingface.co/PaddlePaddle/PP-OCRv5_server_rec_onnx
https://huggingface.co/PaddlePaddle/PP-OCRv6_medium_rec
https://huggingface.co/PaddlePaddle/PP-OCRv6_medium_rec_onnx
https://huggingface.co/PaddlePaddle/PP-OCRv6_medium_rec_safetensors
https://huggingface.co/PaddlePaddle/PP-OCRv6_medium_rec_safetensors/raw/main/config.json
https://huggingface.co/PaddlePaddle/PP-OCRv6_medium_rec_safetensors/raw/main/preprocessor_config.json
https://huggingface.co/PaddlePaddle/PP-OCRv6_small_rec
https://huggingface.co/PaddlePaddle/PP-OCRv6_small_rec_onnx
https://huggingface.co/PaddlePaddle/PP-OCRv6_small_rec_safetensors
https://huggingface.co/PaddlePaddle/PP-OCRv6_tiny_rec
https://huggingface.co/PaddlePaddle/PP-OCRv6_tiny_rec_onnx
https://huggingface.co/PaddlePaddle/PP-OCRv6_tiny_rec_safetensors
https://huggingface.co/phunc20/trocr-base-handwritten_nj_biergarten_captcha_v2
https://huggingface.co/Qwen/Qwen2.5-VL-3B-Instruct
https://huggingface.co/Qwen/Qwen2.5-VL-7B-Instruct
https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct
https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct
https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct
https://huggingface.co/saifulbabo/math-captcha
https://huggingface.co/secemp9/cloudflare_captcha
https://huggingface.co/settings/tokens
https://huggingface.co/ShooterShanky/moondream-captcha
https://huggingface.co/spaces/evaluate-metric/cer
https://huggingface.co/squirelmail/model-BotDetect-CAPTCHA-Generator
https://huggingface.co/stepfun-ai/GOT-OCR-2.0-hf
https://huggingface.co/stepfun-ai/GOT-OCR2_0
https://huggingface.co/stevenchang/captcha
https://huggingface.co/techietrader/captcha_ocr
https://huggingface.co/Titlehhhh/captchaocr-ppocrv6
https://huggingface.co/toandev/OCR-for-Captcha
https://huggingface.co/tomofi/trocr-captcha
https://huggingface.co/ultra2207/florence-2-captcha
https://huggingface.co/Vasanth/moondream-ft-captcha
https://huggingface.co/verytuffcat/captcha_image
https://huggingface.co/Wall3/Yara_Captcha_Solver
https://huggingface.co/wonder56/captcha-crnn-solver
https://huggingface.co/xiaolv/ocr-captcha
https://huggingface.co/zenoda/trocr-captcha-killer
https://huggingface.co/ZHEN-04/CaptchaAgent
https://ieee-dataport.org/documents/deep-captcha
https://keras.io/examples/vision/captcha_ocr/
https://khimananda.com/blog/git-lfs-large-files
https://lite.duckduckgo.com/lite/?q=
https://lite.duckduckgo.com/lite/?q=%22Decomposed-CTC%22+arxiv
https://lite.duckduckgo.com/lite/?q=TinyOCR+huggingface+model+repo
https://llm-stats.com/benchmarks/ocrbench
https://llmstxt.org/
https://lobehub.com/skills/erik-kroon-skills-docs-debloat
https://mcbase.ru/
https://mcmodshub.com/mod/33953
https://mcorep.ru/
https://mcreference.com
https://mcreference.com/plugins
https://mcreference.com/plugins/captchaverifyz
https://mcreference.com/plugins/smartcaptcha-gui-based-captcha-system
https://mcreference.com/search?q=
https://media.discordapp.net/attachments/878241549857738793/915165038464098314/unknown.png
https://minecraft.tools/en/json_text.php/
https://modrinth.com/plugin/captchaverifyz
https://modrinth.com/plugin/limbofilter
https://modrinth.com/plugin?query=captcha
https://modrinth.com/project/LbnXX4g9
https://nova.rambler.ru/search?query=
https://onnx.ai/onnx/operators/onnx__LSTM.html
https://onnxruntime.ai/docs/execution-providers/CUDA-ExecutionProvider.html
https://onnxruntime.ai/docs/get-started/with-cpp.html
https://onnxruntime.ai/docs/performance/model-optimizations/graph-optimizations.html
https://onnxruntime.ai/docs/performance/model-optimizations/quantization.html
https://openaccess.thecvf.com/content/ICCV2021W/ILDAV/html/Atienza_Data_Augmentation_for_Scene_Text_Recognition_ICCVW_2021_paper.html
https://openaccess.thecvf.com/content/ICCV2025/html/Du_SVTRv2_CTC_Beats_Encoder-Decoder_Models_in_Scene_Text_Recognition_ICCV_2025_paper.html
https://openaccess.thecvf.com/content/WACV2025/html/Le_Stratified_Domain_Adaptation_A_Progressive_Self-Training_Approach_for_Scene_Text_WACV_2025_paper.html
https://opencaptcha.io/
https://pillow.readthedocs.io/en/stable/handbook/concepts.html
https://presenc.ai/research/best-open-weight-ocr-document-ai-models-2026
https://priv.au/search?q=
https://pypi.org/project/2captcha-python/
https://pypi.org/project/captcha/
https://pypi.org/project/captcha-solver/
https://pypi.org/project/cnocr/
https://pypi.org/project/ddddocr/
https://pypi.org/project/django-simple-captcha/
https://pypi.org/project/docTR/
https://pypi.org/project/easyocr/
https://pypi.org/project/flashocr/
https://pypi.org/project/keras-ocr/
https://pypi.org/project/mmocr/
https://pypi.org/project/onnxruntime/
https://pypi.org/project/paddleocr/
https://pypi.org/project/pytesseract/
https://pypi.org/project/rapidocr-onnxruntime/
https://pypi.org/project/surya-ocr/
https://pypi.org/project/tesserocr/
https://pypi.org/pypi/
https://rapidai.github.io/RapidOCRDocs/main/en/install_usage/rapidocr/install/
https://raw.githubusercontent.com/
https://raw.githubusercontent.com/%s/%s/%s
https://raw.githubusercontent.com/irootdev/AnBot/master/LICENSE
https://raw.githubusercontent.com/jonesdevelopment/sonar/main/LICENSE
https://raw.githubusercontent.com/Leymooo/BungeeCord/master/LICENSE
https://raw.githubusercontent.com/Leymooo/BungeeCord/master/proxy/src/main/java/ru/leymooo/botfilter/captcha/CaptchaGeneration.java
https://raw.githubusercontent.com/Leymooo/BungeeCord/master/proxy/src/main/java/ru/leymooo/botfilter/captcha/generator/CaptchaPainter.java
https://raw.githubusercontent.com/Leymooo/BungeeCord/master/proxy/src/main/java/ru/leymooo/botfilter/captcha/generator/map/CraftMapCanvas.java
https://raw.githubusercontent.com/Leymooo/BungeeCord/master/proxy/src/main/java/ru/leymooo/botfilter/captcha/generator/map/MapPalette.java
https://raw.githubusercontent.com/Leymooo/BungeeCord/master/proxy/src/main/java/ru/leymooo/botfilter/captcha/generator/Rippler.java
https://raw.githubusercontent.com/NVIDIA/NeMo/main/docs/source/asr/ssl/configs.rst
https://raw.githubusercontent.com/PaddlePaddle/PaddleOCR/main/deploy/paddle2onnx/readme.md
https://raw.githubusercontent.com/PaddlePaddle/PaddleOCR/main/docs/version2.x/ppocr/model_compress/knowledge_distillation.en.md
https://raw.githubusercontent.com/PaddlePaddle/PaddleOCR/main/docs/version2.x/ppocr/model_compress/quantization.en.md
https://raw.githubusercontent.com/ServerSideProject/botfilter_captcha_dataset/main/LICENSE
https://raw.githubusercontent.com/Supl1n/CaptchaGUI/main/CaptchaGUI/src/me/supl1na/captcha/CaptchaListener.java
https://rdrr.io/cran/ggmlR/man/ggml_layer_lstm.html
https://registry.npmjs.org/%s/latest
https://registry.npmjs.org/-/v1/search?text=%s&size=50
https://repo1.maven.org/maven2/org/benf/cfr/0.152/cfr-0.152.jar
https://repomix.com/
https://repomix.com/guide/
https://rightdao.com/search?q=
https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.GroupKFold.html
https://search.brave.com/search?q=
https://search.lycos.com/web/?q=
https://search.marginalia.nu/search?query=
https://search.maven.org/solrsearch/select?q=
https://searchcode.com/?q=
https://searx.be/search?q=
https://source.unsplash.com/random/400x400
https://sourcegraph.com/.api/search/stream
https://sourcegraph.com/.api/search/stream?q=
https://spigotmc.ru
https://spigotmc.ru/
https://spigotmc.ru/resources/
https://spigotmc.ru/resources/?q=
https://spigotmc.ru/resources/?search=
https://spigotmc.ru/resources/limboapi-limboauth-limbofilter-virtualnye-servera-dlja-velocity.715/
https://spigotmc.ru/resources/samyj-xoroshij-konfig-na-limbofilter.3240/
https://spigotmc.ru/resources/weatheractioncaptcha-luchshaja-kapcha-dlja-zaschity-servera-vypolni-dejstvie-i-projdi-na-server.3275/
https://spigotmc.ru/search/?q=
https://spigotmc.ru/search/search
https://spigotmc.ru/search/search?keywords=
https://spigotmc.ru/search/search?keywords=Captcha&c
https://spigotmc.ru/sitemap.xml
https://spigotmc.ru/tags/captcha/
https://spigotmc.ru/tags/kapcha/
https://tesseract-ocr.github.io/tessdoc/Installation.html
https://textocr.github.io/
https://web.archive.org/web/20171127180056/https://distill.pub/2017/ctc/
https://webui.adventure.kyori.net/
https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
https://www.ask.com/web?q=
https://www.augmentcode.com/blog/your-agents-context-is-a-junk-drawer
https://www.baidu.com/s?wd=
https://www.bing.com/images/search?q=
https://www.bing.com/search?q=
https://www.craftit.ru/
https://www.ecosia.org/search?q=
https://www.google.com/search?q=
https://www.kaggle.com/datasets/muzzamalhameed/1m-big-captcha-dataset
https://www.mdpi.com/2076-3417/14/12/5016
https://www.minecraftforum.ru/
https://www.mojeek.com/search?q=
https://www.paddleocr.ai/latest/en/version2.x/ppocr/model_compress/knowledge_distillation.html
https://www.paddleocr.ai/latest/en/version2.x/ppocr/model_compress/quantization.html
https://www.paddleocr.ai/latest/en/version3.x/algorithm/PP-OCRv6/PP-OCRv6.html
https://www.paddleocr.ai/main/en/version3.x/algorithm/PP-OCRv6/PP-OCRv6.html
https://www.paddleocr.ai/main/en/version3.x/module_usage/text_recognition.html
https://www.paddleocr.ai/v3.0.3/en/version3.x/algorithm/PP-OCRv5/PP-OCRv5.html
https://www.qwant.com/?q=
https://www.researchsquare.com/article/rs-9689250/v1
https://www.sogou.com/web?query=
https://www.spigotmc.org/
https://www.spigotmc.org/resources/
https://www.spigotmc.org/resources/%E2%9A%91-smartcaptcha-%E2%9A%91-gui-based-captcha-system-%E2%9A%91.70935/
https://www.spigotmc.org/resources/1.captcha.1/
https://www.spigotmc.org/resources/319579/smartcaptcha-gui-based-captcha-system-1.0.jar
https://www.spigotmc.org/resources/70935
https://www.spigotmc.org/resources/botfilterplus.109765/
https://www.spigotmc.org/resources/captcha.103993/
https://www.spigotmc.org/resources/captcha.120533/
https://www.spigotmc.org/resources/captcha.75891/
https://www.spigotmc.org/resources/captcha.77939/
https://www.spigotmc.org/resources/captcha.84509/
https://www.spigotmc.org/resources/captcha.86350/
https://www.spigotmc.org/resources/captchagui.89583/
https://www.spigotmc.org/resources/captchaverifyz-1-21-x-26-x.125355/
https://www.spigotmc.org/resources/lofiwebcaptcha-
https://www.spigotmc.org/search/search?keywords=
https://www.spigotmc.org/threads/
https://www.spigotmc.org/threads/%E2%9A%91-smartcaptcha-%E2%9A%91-gui-based-captcha-system-%E2%9A%91.393547/
https://www.spigotunlocked.com/
https://www.startpage.com/sp/search?query=
https://www.usenix.org/conference/osdi22/presentation/lv
https://www.youtube.com/@faynerYT
https://www.youtube.com/@krytickyt
https://www.youtube.com/oembed?url=
https://www.youtube.com/watch?v=62jp1hEeSFk
https://www.youtube.com/watch?v=a3_VRVRGuEc
https://yadi.sk/d/QrSeJWeU3LAq4p
https://yandex.ru/search/?text=
https://yep.com/web?q=
https://zyszys.github.io/awesome-captcha/
</details>

---

## Приложение B. Все команды, которыми это проверено

```powershell
# --- состояние GitHub ---
gh api "repos/Titlehhhh/CaptchaOCR/git/trees/main?recursive=1" > gh_tree.json
gh api repos/Titlehhhh/CaptchaOCR/commits --jq '.[].commit.message'
gh api repos/Titlehhhh/CaptchaOCR --jq '{private:.private,size_kb:.size}'

# --- следы сервиса в опубликованной ветке ---
git grep -I -n -i -E "bareapi|bare-api|bare_api|capmonster|mit_ck|mitelis|i\.ibb\.co|i\.postimg\.cc|support@|captcha-service|solver-api|api-key|clientkey|anti-captcha|rucaptcha|2captcha|killcaptcha" origin/main
gh search code "bareapi repo:Titlehhhh/CaptchaOCR"
gh search code "capmonster repo:Titlehhhh/CaptchaOCR"
gh search code "mit_ck repo:Titlehhhh/CaptchaOCR"
gh search code "i.ibb.co repo:Titlehhhh/CaptchaOCR"
gh search code "i.postimg.cc repo:Titlehhhh/CaptchaOCR"

# --- история: локально чисто, на сервере — нет ---
git log --all -p | Select-String "bareapi|bare-api|capmonster|mit_ck|mitelis|i\.ibb\.co|i\.postimg\.cc"
git fsck --unreachable --dangling
git count-objects -vH
gh api repos/Titlehhhh/CaptchaOCR/commits/cfb7c7b      # -> 200 OK: СТАРАЯ ИСТОРИЯ ЖИВА
gh api repos/Titlehhhh/CaptchaOCR/commits/22ee3d4      # -> 200 OK: коммит с CapMonster-пробой
gh api repos/Titlehhhh/CaptchaOCR/tarball/cfb7c7b -o old.tar.gz   # снять и просканировать

# --- персональные пути и секреты ---
git grep -I -n -E "[A-Za-z]:[\\/]+Users[\\/]" origin/main
git grep -I -n -E "ghp_|gho_|github_pat_|hf_[A-Za-z0-9]{20,}|AKIA|-----BEGIN" origin/main
git ls-files | Select-String "hf-cache|token|\.env|\.pem|\.key$|id_rsa"
git ls-files --others --exclude-standard          # -> пусто: лишнего не уедет

# --- размеры и мусор ---
gh api "repos/Titlehhhh/CaptchaOCR/git/trees/main?recursive=1" --jq '.tree[] | select(.size > 1048576) | "\(.size)\t\(.path)"'
Get-FileHash research\myout\*.png,research\refout\*.png -Algorithm MD5

# --- Hugging Face ---
Invoke-RestMethod https://huggingface.co/api/datasets/Titlehhhh/captchaocr-dataset
Invoke-RestMethod https://huggingface.co/api/models/Titlehhhh/captchaocr-ppocrv6
Invoke-WebRequest https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset/raw/main/data/out_ru/LimboFilter/map/labels.jsonl
```

---

*Отчёт подготовлен в рамках задачи C3. Ни один файл репозитория, кроме
eports/reviews/C3_hygiene.md, не изменялся.*
