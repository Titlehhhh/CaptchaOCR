# ONBOARDING — с чего начать в CaptchaOCR

**Для нового человека или нового агента. 10 минут на чтение, потом — команды.**
Корень репозитория: `C:\Users\Title\Projects\CaptchaOCR`.

---

## 1. Что это

Лаборатория моделей для решения Minecraft-капч. Две половины:

- **датасет** — Java-генераторы, которые заново отрисовывают капчи 23 плагинов (18 в
  `dataset/generator/`, 5 в `dataset/generator_ru/`), плюс сгенерированный датасет
  (`dataset/out/`, `dataset/out_ru/`) — **46 типов x 100 картинок = 4600**, с метками в `labels.jsonl`;
- **модели** — `train/` (свой CRNN+CTC), `bench/` (харнессы для чужих движков), `reports/` (измеренные
  результаты), `site/` (сайт-атлас: все капчи крупно, кто как их решает в процентах, как выглядит
  обрезание по полосе).

Текущее состояние и что дальше — `HANDOVER.md`. Главный документ сессии — `reports/CAPTCHA_SYSTEM_OVERVIEW.md`.

## 2. Порядок чтения

| # | файл | зачем |
|---|---|---|
| 1 | `AGENTS.md` | правила: главный агент — оркестратор, один файл — один агент, как брифовать, как принимать результат |
| 2 | `llms.txt` | карта репозитория для машины (то же самое, но коротко и по-пути) |
| 3 | `HANDOVER.md` | состояние проекта: что сделано, что измерено, что делать дальше |
| 4 | `docs/GLOSSARY.md` | словарь: `text` vs `answer`, полоса, группа A/B/C, CTC, type-held-out |
| 5 | `agents/INDEX.md` | подробная карта: 46 типов, команды, ловушки машины, 17 расхождений документов и реальности |
| 6 | `docs/ONBOARDING.md` | этот файл |

## 3. Правила, которые нельзя нарушать

- **Главный агент — оркестратор.** Он ставит задачу, принимает результат, разруливает конфликты
  (один файл — один агент), пересобирает датасет и коммитит. Код он не пишет.
- **Не выдумывать источник.** Нет апстрима — пишем «не найдено» и помечаем `reconstructed`.
- **Не «чинить» дефект апстрима** — воспроизводим и документируем.
- **Не редактировать измеренный результат** в `reports/` — перезамеряем.
- **Не удалять `real_shots/`** и `site/captchas/` — это материал для сверки, не обучающие данные.
- **Датасет — артефакт машины:** шрифты зависят от системы, поэтому датасет генерируется один раз
  и обучается с этой же папки.

## 4. Машина (Windows)

| что | где |
|---|---|
| Java 21 | `I:\ForAndroid\Java\21\bin` (`javac.exe`, `java.exe`) |
| Python с CUDA | `.venv-gpu\Scripts\python.exe` (torch 2.14.1+cu126, sm_61, GTX 1080 Ti 11.8 ГБ) |
| Системный Python | **CPU-only** — для трейнера не годится |
| `pwsh` | **не существует**, только Windows PowerShell 5.1 |
| запуск `.ps1` | **заблокирован** — логику `build.ps1` выполняем inline (блок в `AGENTS.md` §4) |
| `ddgs` (веб-поиск) | ставить `$env:PYTHONIOENCODING="utf-8"` для кириллицы |

## 5. Команды

```powershell
# скомпилировать оба генератора (логика build.ps1, которую нельзя выполнить как .ps1)
$java = "I:\ForAndroid\Java\21\bin"
$core = Get-ChildItem -File dataset\generator\dev\captha\*.java | % FullName
& "$java\javac.exe" -encoding UTF-8 -d build\classes -sourcepath dataset\generator $core (Get-ChildItem -Recurse -Filter *.java dataset\generator | % FullName)
& "$java\javac.exe" -encoding UTF-8 -d build\classes_ru -sourcepath dataset\generator_ru $core (Get-ChildItem -Recurse -Filter *.java dataset\generator_ru | % FullName)

# сгенерировать (100 на тип) и провалидировать
& "$java\java.exe" "-Djava.awt.headless=true" -cp build\classes     dev.captcha.Gen     dataset\out    100
& "$java\java.exe" "-Djava.awt.headless=true" -cp build\classes     dev.captcha.Validate dataset\out
& "$java\java.exe" "-Djava.awt.headless=true" -cp build\classes_ru  dev.captcha.Gen     dataset\out_ru 100
& "$java\java.exe" "-Djava.awt.headless=true" -cp build\classes_ru  dev.captcha.Validate dataset\out_ru

# после пересборки вернуть эталонные скриншоты
python tools\restore_real_shots.py

# проверить метки и полосы
python tools\check_labels_and_roi.py dataset\out_ru
python tools\check_band_vs_answer.py dataset\out_ru

# обучение (GPU) — читать train/AGENTS.md, там про плато CTC и type-held-out
.venv-gpu\Scripts\python.exe train\train.py --charset latin --trees both --epochs 80 --workers 6

# сайт-атлас: открыть site\index.html двойным кликом (файл://, без сервера)
```

## 6. Где что лежит

| путь | что |
|---|---|
| `dataset/generator/`, `dataset/generator_ru/` | Java-исходники генераторов; правила — в `dataset/generator/AGENTS.md` |
| `dataset/out/`, `dataset/out_ru/` | сгенерированный датасет, метки в `labels.jsonl` |
| `train/` | модель, трейнер, измерители; правила — в `train/AGENTS.md` |
| `bench/` | харнессы для чужих моделей (`bench/bench_models.py` — единый протокол) |
| `tools/` | чекеры и измерители (35 скриптов) |
| `reports/` | **только измеренные результаты**: `TRAINING_MINIMAL_LATIN.md`, `CAPTCHA_SYSTEM_OVERVIEW.md`, `research2/` (10 отчётов), `bench_models/` (JSON) |
| `docs/` | человеческая документация: `pipeline-design.md`, `GLOSSARY.md`, `ONBOARDING.md`, `adr/` (решения) |
| `research/` | исходники апстримов, декомпиляция, находки по идентификации плагинов |
| `site/` | сайт-атлас + 525 референсов группы GalleryCaptcha в `site/captchas/` |
| `agents/` | документация **для ИИ**: `INDEX.md`, `AGENT_LOG.md`, `DSH_HARNESS.md`, `REPO_STRUCTURE.md` |

## 7. С чего начать работу

1. Прочитать `AGENTS.md` и `HANDOVER.md` §7 (порядок работ).
2. Проверить, что дерево собирается и `dev.captcha.Validate` чист (команды в §5).
3. Взять **одну** задачу из `HANDOVER.md` §7, определить владельца файлов и **не трогать** то, что
   уже отслеживается другим агентом.
4. При сомнениях — `agents/AGENT_LOG.md` (протокол субагента и таблица владения) и
   `agents/INDEX.md` §9 (расхождения документов и измеренной реальности).
