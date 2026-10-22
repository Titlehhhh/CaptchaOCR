# C2 — техническая рецензия: честны ли цифры, согласованы ли код и документация, корректны ли публикации

**Дата:** 2026-10-22 · **Роль:** придирчивый технический рецензент · **Правил:** ничего, кроме этого отчёта.

**Метод.** Каждое утверждение из README / HANDOVER / AGENTS / карточек HF сверено с первоисточником
(измеренный JSON, файл разметки, код) и **пересчитано** — приведённая команда и её фактический вывод.
Публикации проверены через API Hugging Face (`/api/datasets/...`, `/api/models/...`, `/tree/main`)
и через `raw/main/README.md`.

> **Замечание о номерах строк.** Во время рецензии README.md переписывался владельцем
> (после моего первого чтения файл вырос с 378 до 382 строк, номера сдвинулись). Все номера строк
> в этом отчёте — **по рабочему дереву на 2026-10-22, после правки README**; при дальнейших правках
> сверяйтесь по **тексту** цитаты, а не по номеру строки.

**Состояние репозитория на момент рецензии:** `git log` → 2 коммита (`4807546`, `84d181f` — в задании
упоминался один); `git status` → `M README.md`, `M dataset/samples/README.md`,
`M tools/hf_dataset_card.md`, `M tools/hf_model_card.md` (документация правится параллельно с рецензией).
Публикации на HF и HEAD репозитория из-за этого могли разойтись — часть расхождений ниже может быть
уже исправлена к моменту чтения отчёта.

---

## 1. Топ-10 расхождений

### №1. CER для EasyOCR: в документации 1.861, измерено **1.8353**

| | |
|---|---|
| **Утверждается** | «`EasyOCR` \| 0.115 \| — \| **1.861**» |
| **Где** | `README.md:312`; также `HANDOVER.md:97`, `agents/AGENT_LOG.md:246`, `agents/INDEX.md:44`, `docs/adr/0002-recogniser-architecture-and-data.md:818` и `:1009`, `reports/CAPTCHA_OCR_REPORT.md:13`, `reports/MODEL_PLAN.md:697` |
| **Первоисточник** | `reports/bench_results_others.json` → ключ `EasyOCR/en` → `"mean_cer": 1.8353` |

```
python -c "import json;d=json.load(open('reports/bench_results_others.json',encoding='utf-8'));e=d['EasyOCR/en'];c=[p['cer'] for p in e['preds']];print(len(c),sum(c)/len(c),e['mean_cer'])"
→ 104 1.8353 1.8353
```

Пересчёт по пер-prediction CER даёт **1.8353**, а не 1.861. Это опечатка, а не округление: в двух
других местах того же репозитория то же самое измерение записано верно —
`reports/TRAINING_MINIMAL_LATIN.md:447` («`EasyOCR/en` \| band \| 0.115 \| **1.835**») и
`reports/research2/G_test_plan.md:54` («0.115 \| **1.835**»).

**Хуже всего `docs/adr/0002-…md:1009`**, где стоит «✅ `bench_results_others.json`: accuracy 0.1154,
**mean_cer 1.8614**» — то есть документ *делает вид*, что сверился с JSON, и при этом цитирует не то
значение, которое там лежит.

**Как исправить:** `1.861` → `1.835` (или `1.8353`) в 7 местах; в ADR-строке 1009 заменить
«mean_cer 1.8614» → «mean_cer 1.8353» и перепроверить «✅».

---

### №2. Таблица бенчмарков в README смешивает два разных протокола измерения

**Утверждается** (`README.md:306-313`):

> «Готовые модели на тех же данных (**по 20 картинок на тип, все 46 типов**, `reports/bench_models/`)»
> … `| EasyOCR | 0.115 | — | 1.861 |`

**Факт.** Строка EasyOCR пришла из другого прогона: `reports/bench_results_others.json` → `n = 104`
(13 типов × 8), а в самом `reports/bench_models/easyocr.json` измерение сделано на **8 типах / 64
картинках** (`protocol.item_sets = ['legacy64']`) и даёт `acc_micro = 0.3281`, `cer_micro = 0.3826`.

```
python -c "import json;d=json.load(open('reports/bench_models/easyocr.json',encoding='utf-8'));print(d['protocol']['item_sets'],d['protocol']['n_per_type']);print(d['modes']['band']['legacy64']['metrics']['all_types'])"
→ ['legacy64'] 20
→ {'types': 8, 'items': 64, 'acc_micro': 0.3281, 'cer_micro': 0.3826, ...}
```

То есть ни `0.115`, ни `1.861` из `reports/bench_models/easyocr.json` **не следуют** — заголовок
таблицы («все 46 типов») к этой строке неверен. То же смешение в `agents/INDEX.md:44`
(«acc **0.077–0.115** / CER **0.785–1.861**»): 0.077 (`anuashok/ocr-captcha-v3`,
`reports/bench_results.json`: `"accuracy": 0.0769`) измерен на **целом кадре**, 0.115 (EasyOCR) —
на **полосе**. Это признаёт сам `agents/INDEX.md` (расхождение #11).

**Как исправить:** разбить таблицу на две с явными протоколами («протокол bench_models: 46 типов × 20
картинок» и «протокол bench_results_others: 104 картинки, 13 типов») либо убрать строку EasyOCR из
таблицы и сослаться на `reports/bench_results_others.json` отдельно.

---

### №3. Карточка модели на HF: прогон описан как «2 эпохи», измерено **6 эпох**

**Опубликовано** (<https://huggingface.co/Titlehhhh/captchaocr-ppocrv6/raw/main/README.md>, раздел
«Why the weights are not here yet»):

> «A short probe run (**2 epochs**) of the fine-tune was measured on the same held-out types…»

**Первоисточник** `reports/TRAINING_PPOCR_V6.json`:

```
python -c "import json;d=json.load(open('reports/TRAINING_PPOCR_V6.json',encoding='utf-8'));print(d['training_run']['epochs_completed'],d['training_run']['steps_completed'],d['training_run']['planned_steps'],d['training_run']['stopped'])"
→ 6 240 1230 by the author (the run was killed during epoch 5)
```

`loss_timeline` содержит 6 записей (epoch 0…5). Оценка (`--eval-every 2`) была только на 1-й и 3-й
эпохах. Логи прогона это подтверждают (`train/run_ppocr/final/log.txt`): «epoch 1: … median exact=0.41
cer=0.2883», «epoch 3: … median exact=0.24 cer=0.34», «epoch 5: loss=0.0136 …» — шесть эпох, 240 шагов.

**Откуда взялось «2» в карточке.** В репозитории есть отдельный **пилотный** прогон
(`train/run_ppocr/smoke/`, `smoke/result.json`) — «Пилотный прогон из брифа (2 эпохи, 20 картинок на
тип)» (`reports/TRAINING_PPOCR_V6.md:222`). Карточка склеила два разных прогона: длительность — от
пилота (2 эпохи), а цифры **0.41 и 0.24 — от основного прогона на 6 эпох**. Поэтому фраза
«A short probe run (2 epochs) … median exact match 0.41 after epoch 1 and 0.24 after epoch 3»
внутренне противоречива: прогон на 2 эпохи не мог дать оценку «after epoch 3».

**Как исправить:** «A probe run of **6 epochs** (240 of 1230 planned steps, stopped by the author) was
measured and evaluated after epoch 1 and epoch 3; it was worse than the base model — median exact
match 0.41 (epoch 1) and 0.24 (epoch 3) against 0.60 for the untouched base model».

---

### №4. Карточка модели ссылается на первоисточник, которого нет в репозитории

**Опубликовано** (таблица «The base model, measured before fine-tuning»):

> «| exact match (micro) on the 7 type-held-out types, band crop | 0.5586 | **`train/run_ppocr/` zero-step baseline** |»

**Факт.** Каталог `train/run_ppocr/` существует **только в локальном рабочем дереве** и **в git не
входит** (`git status` его не показывает, в репозитории на GitHub его нет) — читатель, который
откроет репозиторий, по этой ссылке ничего не найдёт. Измеренное значение лежит в
`reports/TRAINING_PPOCR_V6.json` → `zero_step.aggregate.exact_match_micro = 0.5586` (совпадает),
а `train/run_ppocr/final/` — это рабочий каталог прогона (логи, чекпоинты на 200+ МБ), не
первоисточник для публикации.

**Логи прогона подтверждают JSON** (`train/run_ppocr/final/log.txt`, локально):

```
zero step: 32.0s  held-out median exact=0.6 cer=0.1575
epoch 1: loss=0.0762  …  held-out median exact=0.41 cer=0.2883  micro exact=0.4486
epoch 3: loss=0.0194  …  held-out median exact=0.24 cer=0.34  micro exact=0.4229
epoch 5: loss=0.0136  12.9s  115.9 img/s        ← 6 эпох (0…5), 240 шагов из 1230
```

**Как исправить:** в карточке заменить источник на `reports/TRAINING_PPOCR_V6.json` → `zero_step.aggregate`.

---

### №5. `tools/hf_model_card.md` — шаблон **другой** модели; publish-скрипт перезапишет карточку

**Факт.** `tools/hf_model_card.md` — шаблон карточки **CRNN+CTC** под MIT:

```
tools/hf_model_card.md:2   license: mit
tools/hf_model_card.md:24  * **Architecture:** CRNN (CNN → BiLSTM) with a CTC head, {N_CLASSES} classes
```

а `tools/publish_hf.py` рендерит **именно его** в репозиторий модели:

```
tools/publish_hf.py:85    MODEL_CARD_TEMPLATE = HERE / "hf_model_card.md"
tools/publish_hf.py:1336-1337  template = MODEL_CARD_TEMPLATE.read_text(...); card, leftovers = render_template(template, model_card_values(args, info))
```

Опубликованная же карточка `Titlehhhh/captchaocr-ppocrv6` — **другая** (PP-OCRv6, `license: apache-2.0`,
`base_model: PaddlePaddle/PP-OCRv6_medium_rec_safetensors`) и в репозитории **отсутствует**: шаблона
под неё в `tools/` нет.

**Последствие.** Любой прогон документированного publish-пути для этой модели затрёт хорошую,
честную карточку на карточку CRNN/MIT с архитектурой, числом классов и лицензией, не относящимися к
PP-OCRv6.

**Как исправить:** завести `tools/hf_model_card_ppocr.md` (шаблон под текущую карточку) и выбирать
шаблон по типу модели в `publish_hf.py`; текущую опубликованную карточку сохранить в репозитории
как первоисточник.

---

### №6. Метаданные HF-репозитория модели заявляют готовую загружаемую модель — весов нет

```
web_fetch https://huggingface.co/api/models/Titlehhhh/captchaocr-ppocrv6
→ "pipeline_tag":"image-to-text", "library_name":"transformers",
  "base_model:finetune:PaddlePaddle/PP-OCRv6_medium_rec_safetensors",
  "license:apache-2.0", "transformersInfo":{"auto_model":"AutoModel"},
  "siblings":[{"rfilename":".gitattributes"},{"rfilename":"README.md"}],
  "usedStorage":0
```

Текст карточки честно пишет «the weights are **not published yet**», но **метаданные** — а именно они
попадают в выдачу поиска HF, в `transformers` auto-detection и в сторонние индексы — утверждают, что
это дообученная PP-OCRv6-модель под Apache-2.0, которую грузит `AutoModel`. Фактически в репозитории
только `README.md` и `.gitattributes`, `usedStorage = 0`.

**Как исправить:** до выкладки весов убрать из метаданных `base_model:finetune:` и `library_name`
(или добавить явный тег вроде `weights: not yet published`); `pipeline_tag` оставить, но текст
карточки должен это оговаривать (он оговаривает — это правильно).

---

### №7. У датасета на HF нет файла лицензии; `license: other` при AGPL-3.0 и «all rights reserved» внутри

```
web_fetch https://huggingface.co/api/datasets/Titlehhhh/captchaocr-dataset/tree/main
→ data/ (dir), .gitattributes, README.md, dataset_inventory.json      # LICENSE — НЕТ
web_fetch https://huggingface.co/api/datasets/Titlehhhh/captchaocr-dataset
→ "tags":["license:other",...], "cardData":{"license":"other","license_name":"mixed-per-plugin-licences"}
```

**Что хорошо:** per-type лицензии в карточке расписаны, и **AGPL-3.0 (`LimboFilter`, 4 типа) там
отражён явно** — это требование задания выполнено.

**Что плохо:** `license: other` на уровне репозитория = «никакой распознанной лицензии», при том что
внутри 4 типа под AGPL-3.0 (`LimboFilter`), 5 типов под GPL-3.0 (`China2B2T/Captcha`,
`irootdev/AnBot`, `jonesdevelopment/sonar` ×3) и **6 типов — «all rights reserved / лицензии нет»**
(`Archy-X/Krypton` ×2, `Yukun99/Captchas`, `CaptchaGUI`, `CaptchaVerifyZ`, `ringoame196…`).
`license_name` — свободный текст, а не юридический документ; файла `LICENSE` в репозитории нет
(карточка сама пишет «The **generator code** of the project is under a separate licence», но где оно —
не сказано).

**Как исправить:** положить в корень датасета `LICENSE`/`TERMS.md` с явной раскладкой
«строка данных наследует лицензию плагина-источника; в составе есть AGPL-3.0 и all-rights-reserved
типы», и переименовать `license_name` в формат, прямо называющий ограничение
(например `mixed-per-plugin-licences (includes AGPL-3.0 and all-rights-reserved types)`).

---

### №8. README называет опубликованные страницы «заглушками»

```
README.md:378-381
  * **Датасет на Hugging Face** (заглушка, будет опубликован):
  * **Модель на Hugging Face** (заглушка, будет опубликована):
```

Факт: обе страницы существуют и заполнены (датасет — 4600 PNG + разметка; модель — карточка),
API отдаёт 200. Формулировка «заглушка» противоречит состоянию публикации и видна внешнему читателю
README на GitHub.

**Как исправить:** «**Датасет на Hugging Face** (опубликован: 4600 PNG + разметка)» и
«**Модель на Hugging Face** (опубликована карточка; весов модели пока нет)».

---

### №9. Внутренние документы проекта противоречат фактам (это видно и агенту, и преподавателю)

| Утверждение | Где | Факт |
|---|---|---|
| «They differ in **8** of the 46 types» | `.agents/skills/captcha-train/SKILL.md:85` (и `.agents/skills/captcha-dataset/SKILL.md`) | **9** типов: `AdvancedCaptcha/math`, `XProtect/equation`, `XProtect/reverse`, `Mrbysco/Captcha/math`, `GalleryCaptcha/ru-numberword`, `ru-numberword-caption`, `LimboFilter/map`, `framed2x2`, `framed3x3` (README:164 и AGENTS.md §3 говорят 9 — то есть **скилл устарел**) |
| «the best of them is ≈ **0.16** exact match on our data» | `AGENTS.md:116` (единственное вхождение 0.16 во всём репо, `git grep`) | Лучший измеренный: **0.4043** на полосе (46 типов) и **0.0783** на кадре (`ppocrv6-medium`); в старом протоколе — 0.1154 (EasyOCR) и 0.0769 (`anuashok`). Значения 0.16 нет ни в одном измерении |

```
python -c "import glob,json;fs=sorted(glob.glob('dataset/out/**/labels.jsonl',recursive=True))+sorted(glob.glob('dataset/out_ru/**/labels.jsonl',recursive=True));d=[f for f in fs if any(json.loads(l)['text']!=json.loads(l)['answer'] for l in open(f,encoding='utf-8') if l.strip())];print(len(d));print(*[x.replace(chr(92),'/') for x in d],sep='\n')"
→ 9
→ dataset/out/FeelingAlive0/AdvancedCaptcha/math/labels.jsonl
  dataset/out/LagBug/XProtect/equation/labels.jsonl
  dataset/out/LagBug/XProtect/reverse/labels.jsonl
  dataset/out/Mrbysco/Captcha/math/labels.jsonl
  dataset/out_ru/GalleryCaptcha/ru-numberword-caption/labels.jsonl
  dataset/out_ru/GalleryCaptcha/ru-numberword/labels.jsonl
  dataset/out_ru/LimboFilter/framed2x2/labels.jsonl
  dataset/out_ru/LimboFilter/framed3x3/labels.jsonl
  dataset/out_ru/LimboFilter/map/labels.jsonl
```

**Как исправить:** скилл `captcha-train` → «9 of the 46 types» (добавив `LagBug/XProtect/reverse`);
`AGENTS.md:116` → назвать конкретные числа и протокол («на полосе — 0.404, на кадре — 0.078»).

---

### №10. Опубликованная карточка модели содержит число, источника которого нет в репозитории

> «holds out whole **plugins** (never random splits — a random split leaks the exact gold answer of
> **34 %** of the test samples)»

Проверка:

```
git grep -n "34 %\|34%" -- "*.md"      → совпадений нет (exit code 1)
Select-String reports\TRAINING_PPOCR_V6.md -Pattern "34|leak"
→ 16: Параметры | 19 134 326 ...          (совпадение по подстроке «134326»)
→ 106: ещё ниже — 0.24 / 0.34             (это CER, не доля утечки)
```

Ни расчёта 34 %, ни упоминания утечки в измерениях нет — это неподтверждённое число, опубликованное
наружу.

**Как исправить:** либо положить в репозиторий скрипт+вывод, посчитавший 34 % (и сослаться на него),
либо заменить на непроверяемую формулировку («a random split leaks the gold answer of many test
samples, because several types have few distinct answers» — как уже написано в `train/AGENTS.md`).

---

## 2. Что подтвердилось (сводка)

| Цифра / утверждение | Где в README | Первоисточник | Результат проверки |
|---|---|---|---|
| 46 типов, 4600 PNG | README:71-72 | 46 `labels.jsonl`, 4600 строк | ✅ совпало |
| 23 плагина-источника (18 в `out/` + 5 в `out_ru/`) | README:73, 80-84 | каталоги | ✅ 18 + 5 = 23 |
| 517 эталонных скриншотов | README:75 | `real_shots/**.png` | ✅ ровно 517 |
| faithful 12 / clean-room 10 / reconstructed 1 (по типам 25/16/5) | README:74 | карточка HF (таблица плагинов) | ✅ 25+16+5 = 46, 23 строки |
| `text != answer` у 9 типов из 46 | README:164 | пересчёт по всем `labels.jsonl` | ✅ 9 (в README — правильно; **скилл** — нет, см. №9) |
| полосу несут 29 типов из 46 | README:172 | пересчёт `roi != null` | ✅ 29 типов, 2899 строк с полосой, 1701 без — совпало и с карточкой HF |
| PP-OCRv6_medium_rec: 0.404 (полоса) / 0.078 (кадр) / CER 0.566 | README:310 | `reports/bench_models/ppocrv6-medium.json` → band/full `all_types`: `acc_micro 0.4043`, `cer_micro 0.5662`; frame/full `acc_micro 0.0783` | ✅ совпало |
| «0.552 по полосе и 0.035 по целому кадру» на 29 типах | README:316 | `roi_types`: band `acc_micro 0.5517`, frame `acc_micro 0.0345` | ✅ совпало |
| «в **16 раз** хуже на кадре» | README:316 | 0.5517 / 0.0345 = 15.99 | ✅ совпало |
| PP-OCRv5_mobile_rec: 0.315 / 0.028 / CER 0.530 | README:311 | `ppocrv5-mobile.json`: 0.3152 / 0.0283 / 0.5298 | ✅ совпало |
| `jtrecenti/txtcaptcha-crnn`: 0.002 / 0.000 / CER 1.046 | README:313 | `txtcaptcha-crnn.json`: 0.0022 / 0.0 / 1.0455 | ✅ совпало |
| наш CRNN: **1.000** на обученных типах, **0.000** на невиданных, CER 0.912–1.058, медиана 0.954 | README:319-322 | `reports/eval_main_final.json`: 6 типов `exact 100/100`, 4 типа `exact 0`, CER 0.926/1.055/0.91375/0.980 → медиана 0.954; `reports/TRAINING_MINIMAL_LATIN.md:219-237` | ✅ совпало (overall accuracy 0.6 = 6 из 10 типов) |
| T1: нулевой шаг — медиана 0.600, CER 0.1575 по 7 удержанным типам | задание | `TRAINING_PPOCR_V6.json` → `zero_step.aggregate` = `{types 7, exact_match_median 0.6, cer_median 0.1575}` | ✅ совпало |
| T1: после дообучения 0.410 / 0.2883 | задание | `after_training.aggregate` = `{exact_match_median 0.41, cer_median 0.2883}`, `best_epoch 1` | ✅ числа совпали, **но** это «лучший чекпоинт на эпохе 1», а не «после 6 эпох» (последняя оценка — эпоха 3: 0.24 / 0.34) — см. №3 |
| T1: логи прогона сходятся с JSON | — | `train/run_ppocr/final/log.txt` (локально, не в git) | ✅ «zero step: … median exact=0.6 cer=0.1575», «epoch 1: … 0.41 / 0.2883», «epoch 3: … 0.24 / 0.34», 6 эпох (0…5) |
| `reports/TRAINING_PPOCR_V6.md` не противоречит JSON | — | `:5`, `:78`, `:91`, `:151`, `:167`, `:189` | ✅ честно пишет «остановлен автором на 6-й эпохе из 30 (шаг 240 из 1230)», «лучший чекпоинт (эпоха 1)», «на эпохе 3 — 0.24». Проблема только в **опубликованной карточке** (№3) |
| «словарь модели без кириллицы» | задание, карточка HF | `preprocessor_config.json` базовой модели | ✅ **подтверждено**: 18 710 записей, записей с кодовыми точками U+0400–U+04FF — **0** |
| контракт `labels.jsonl` (10 ключей) | README:156-168 | все 46 файлов | ✅ ключи ровно `file, plugin, captcha, answer, text, prompt, roi, width, height, source` — совпадает |
| «Every PNG here is our own render» | карточка HF | все 4600 PNG — собственные рендеры, чужих нет | ✅ подтверждено (real_shots в публикацию не идут) |
| размер датасета 43.6 МБ (45 688 077 Б) | README:176, карточка HF | сумма PNG | ✅ совпало (но это **только PNG**; с `labels.jsonl` (1 391 312 Б) реально 47 079 389 Б ≈ 44.9 МиБ) |
| алфавит 129 символов | карточка HF | объединение `text` по всем 4600 строк | ✅ 129 |
| «генераторы не засеяны» | README:228-230 | `build.ps1`/генераторы — `Random` без фиксированного seed | ✅ согласуется с AGENTS.md §3 |
| `python tools\fetch_dataset.py --dry-run` работает офлайн и печатает заявленное | README:197-202 | прогон | ✅ «types: 46 of 46», «total: 4600 files, 43.57 MB», «nothing was downloaded» |
| флаги `train.py` против `train/AGENTS.md` | README:257, `train/AGENTS.md` §таблица | `train/train.py:77-115` (`--charset/--types/--val-types/--exclude-types/--trees/--allow-no-roi/--epochs/--batch-size/--lr/--head-lr/--glyph-height/--workers/--augment-affine/--no-augment/--out/--save-every/--resume/--device/--amp/--no-amp/--seed/--limit-per-type/--log-every/--threads`) | ✅ все перечисленные флаги существуют; «флага `--require-roi` не существует» — ✅ верно |
| `train/finetune_ppocr.py --epochs 30 --batch-size 32` (команда в карточке HF) | карточка HF | `train/finetune_ppocr.py:238-266` | ✅ флаги существуют |

---

## 3. Что НЕ проверено (честный список)

1. **Запуск обучения/бенчмарка целиком** — не выполнялся (время и GPU); все числа взяты из
   записанных JSON и пересчитаны по ним, но не воспроизведены «с нуля».
2. `python tools\check_labels_and_roi.py dataset\out_ru` и `check_band_vs_answer.py` — **не запускались**
   (совпадение по полосам проверено собственным пересчётом `roi != null`, но не чекером проекта).
3. `git count-objects -vH` → «около 142 МБ» (README:180-181) — **не проверено**.
4. Соответствие карточки HF датасета локальному шаблону `tools/hf_dataset_card.md` — сверены только
   **числа** (46/4600/23/43.6 МБ/29/2899/1701/9/25-16-5/129), но не текст построчно.
5. `dataset/samples/` — наличие 230 PNG и 2.2 МБ — **не пересчитывал**.
6. Лицензии 23 плагинов — сверено **только** с таблицей в карточке HF (она согласована с README по
   всем 23 строкам); фактические файлы `LICENSE` в чужих репозиториях **не скачивались и не проверялись**.
7. Число «34 % утечки при случайном сплите» (§10) — не пересчитывал, источник не нашёл.
8. «Репозиторий растёт быстрее… 142 МБ», «TrOCR 334 млн параметров» (README:291) — не проверял.
9. Живая страница `https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset` (рендер) — смотрел
   только API и `raw/main/README.md`; визуальный вид страницы не оценивал.
10. `reports/eval_main_final.json` — не проверял, соответствует ли он чекпоинту
    `build\scratch\main_final.pt` (сам чекпоинт в репозитории не коммитится).

---

## 4. Русский язык: «капт» вместо «капчи»

Замечание владельца: слово склоняется как «капт» — это неверная норма; правильно «капчи», «капчами»,
«капче». Ниже — полный перечень по всем `.md`.

```
git grep -n "капт" -- "*.md"
```

**Важное уточнение (это честнее, чем просто «везде неправильно»):** часть вхождений —
**родительный множественного** числа от «капча», то есть «капч» — **грамматически верна**
(«46 типов капч», «решение капт», «корпуса капт»). Ошибка — в остальных падежных формах, которых у
«капча» не существует: винительный («капту»), творительный («каптой»), дательный/предложный
(«капте»), именительный множественного («капты»), предложный множественного («каптах/каптам»),
а также в формах-составных («капта-модель»).

### 4.1 Ошибки (формы, которых не существует) — 15 вхождений

| Файл:строка | Как написано | Как надо |
|---|---|---|
| `README.md:53` | «картинку-**капту** Minecraft-антибота» | «картинку-**капчу**» |
| `README.md:92` | «плагина за **каптой** нет» | «плагина за **капчей** нет» |
| `README.md:94` | «Плагины, чьи **капты** воспроизведены» | «чьи **капчи** воспроизведены» |
| `README.md:340` | «сайт-атлас: все **капты** крупно» | «все **капчи** крупно» |
| `reports/research/briefs/A_ocr_engines.md:27` | «маленькой Minecraft-**капте**» | «Minecraft-**капче**» |
| `reports/research3/MODEL_LANDSCAPE.md:209` | «exact-match по **капте** для VLM» | «по **капче**» |
| `reports/research3/MODEL_LANDSCAPE.md:218` | «на **каптах**» | «на **капчах**» |
| `reports/research3/MODEL_LANDSCAPE.md:228` | «может и **капту**, и арифметику» | «может и **капчу**» |
| `reports/research3/MODEL_LANDSCAPE.md:233` | «**капта** требует» | «**капча** требует» |
| `reports/research3/MODEL_LANDSCAPE.md:235` | «**капта** с VLM — шумная метрика» | «**капча** с VLM» |
| `reports/research3/MODEL_LANDSCAPE.md:257` | «документированная **капта**-модель в HF» | «**капча**-модель» |
| `reports/research3/MODEL_LANDSCAPE.md:260` | «TrOCR-энкодер уже видел **капты**» | «видел **капчи**» |
| `reports/research3/MODEL_LANDSCAPE.md:282` | «CER 0.0139 на **каптах**» | «на **капчах**» |
| `reports/research3/MODEL_LANDSCAPE.md:473` | «TrOCR-дообученные **капта**-модели» | «**капча**-модели» |
| `reports/research3/MODEL_LANDSCAPE.md:509` | «качество на **каптах**» | «на **капчах**» |

(15 строк: 4 в README + 1 в briefs + 10 в MODEL_LANDSCAPE.)

### 4.2 Грамматически верно, но стилистически коряво (род. мн. ч. «капч») — 17 вхождений

`README.md:1` (дважды: «датасет **капт**», «распознавание этих **капт**»), `README.md:332`
(«генераторы **капт**»), `README.md:363` («решения **капт**»), `AGENTS.md:121`, `CONTINUE.md:11`,
`HANDOVER.md:4`, `reports/research3/MODEL_LANDSCAPE.md:1` и `:203` («Для **капт** с кириллицей»),
`reports/research3/TRAINING_METHODS.md:1, 33, 52, 120, 127, 136, 312, 530, 614`.

Ещё одно вхождение — `reports/CAPTCHA_SYSTEM_OVERVIEW.md:138` («наша 5-символьная **капта**») —
**полностью верное** (именительный падеж единственного числа), в списки выше не входит.

Рекомендация: в **читаемых** файлах (README, HANDOVER, AGENTS, CONTINUE) писать «капчи» — так, как
уже написано в заголовке «Капчи», — а «капч» оставить только там, где это естественное
конструктивное падежное согласование («решение капт», «корпуса капт»).

### 4.3 Оценка: это выглядит как небрежность?

**Да, и заметно.** Обоснование:

* **4 из 15 грубых ошибок — в `README.md`**, то есть в единственном файле, который откроет
  преподаватель или посетитель GitHub. Строки 53, 92, 94, 340 бросаются в глаза: «картинку-**капту**»,
  «плагина за **каптой** нет», «чьи **капты** воспроизведены», «все **капты** крупно»; в заголовке
  (строка 1) — «датасет **капт**».
* В `reports/research3/MODEL_LANDSCAPE.md` — 14 вхождений, 10 из них неверных форм; это второй по
  объёму документ проекта (62 КБ) и он читается как «черновик», хотя лежит в `reports/`.
* Ошибка однотипная и системная («капта» вместо «капча» во всех падежах) — это не опечатка
  в одном месте, а **неосознанно выбранная форма слова**, то есть признак того, что слово склоняется
  «по-явасти» (как `captcha` в коде), а не по-русски.
* Дополнительно в тех же отчётах есть другие кривые формы: «капта-модель», «капта-OCR» —
  гибриды русского корня с латиницей в одной основе.

**Про карточки на Hugging Face:** ошибки **нет** — обе опубликованные карточки написаны
преимущественно по-английски («46 captcha types · 4600 labelled PNG», «a text recogniser for the
captchas…») и слова «капт» не содержат. Но там есть **другая** стилистическая небрежность, видимая
снаружи: в англоязычной шапке карточки датасета стоит «· **43.6 МБ**» (кириллическая единица в
английской строке) — лучше «43.6 MB». Это мелочь, но карточку читают чужие люди.

---

## 5. Итог

**Можно ли доверять цифрам в README — частично.**

Ключевые числа **подтвердились почти все**: 46 типов / 4600 PNG / 23 плагина / 517 эталонных
скриншотов / 29 типов с полосой / 9 типов с `text ≠ answer` / 0.404 и 0.078 для PP-OCRv6 / «×16 хуже
на кадре» / 1.000 и 0.000 для нашего CRNN / 0.600-0.1575 и 0.410-0.2883 для T1 / «в словаре модели
нет кириллицы» — всё это пересчитано и сходится. Но **две конкретные цифры неверны** (CER EasyOCR
1.861 → 1.8353; «≈ 0.16» в AGENTS.md), **таблица бенчмарков смешивает два протокола измерения**, и
**опубликованная карточка модели** содержит неверное число эпох («2» вместо 6), ссылается на
несуществующий в репозитории первоисточник и указывает на публикацию, которой нет («заглушка»).
Итог: **цифрам измерений — да; формулировкам и публикациям — только после правки**, иначе на защите
первый же вопрос «а откуда 1.861?» стоит ответа.
