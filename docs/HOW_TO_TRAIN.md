# HOW_TO_TRAIN — как обучать CaptchaOCR самому

**Короткий runbook для этой машины.** Все команды — копипастом в Windows PowerShell 5.1
(правый клик → «вставить», Enter). Ни одна команда не требует прав администратора.

* **Что обучаем:** `PaddlePaddle/PP-OCRv6_medium_rec_safetensors` (19 134 326 параметров,
  Apache-2.0) — лучшая из измеренных чужих баз (`reports/bench_models/ppocrv6-medium.json`).
* **Чем:** `.venv-gpu\Scripts\python.exe` — **единственный** интерпретатор с CUDA
  (`torch 2.14.1+cu126`). Системный `python` — CPU-only, обучение в ~9 раз медленнее.
* **Скрипт:** `train/finetune_ppocr.py` (сплит по типам, CTC-обучение, `--resume`, оценка
  по типам). Список флагов — `train/finetune_ppocr.py --help` (проверен 2026-10-22).
* **Куда пишется:** `train\run_ppocr\<имя прогона>\` (чекпоинты и логи на диске, в git не идут).

---

## Рецепт публикации: три шага

```
(1) ДООБУЧИТЬ с мягким lr=1e-5     train\finetune_ppocr.py       →  <run>\best.pt
(2) ИНТЕРПОЛИРОВАТЬ с базой α=0.4  train\soup_eval.py            →  <run>\soup_best.pt, soup.json
(3) ЭКСПОРТИРОВАТЬ и выложить      train\run_ppocr\export_hf.py  →  hf upload Titlehhhh/captchaocr-ppocrv6
```

| шаг | что делает | измеренный результат |
|---|---|---|
| 1 | дообучение PP-OCRv6_medium_rec на 13 типах с полосой, 7 типов удержаны | медиана по удержанным типам **58.80 % → 48.00 %** — дообучение **само по себе вредит** |
| 2 | интерполяция весов с базой: `θ(α) = α·θ_дообуч. + (1−α)·θ_базы` | при **α = 0.4**: медиана **63.80 %**, micro **61.23 %** — лучше базы **на всех 7 типах сразу** |
| 3 | экспорт в safetensors + карточка + `hf upload` | репозиторий `Titlehhhh/captchaocr-ppocrv6` |

> ### ⚠️ Правило: **никогда не публикуем чистое дообучение**
> Дообученная модель (α = 1.0) на **10.8 п.п. хуже** нетронутой базы
> (48.00 % против 58.80 % медианы по 7 удержанным типам). Публикуем **только**
> интерполяцию с α = 0.4. Чистый `best.pt` — это чекпоинт **для шага 2**, а не
> для выкладки.

Числа во всех трёх шагах — из одного прогона, один пайплайн, 7 удержанных типов из
5 плагинов, 3500 картинок. Источники: `reports/TRAINING_PPOCR_V6_BIG.md`,
`reports/TRAINING_PPOCR_V6_BIG.json`, `train/run_ppocr/big/soup.json`.

> **Честная оговорка.** И α, и эпоха выбраны **на том же удержанном наборе**, на котором
> потом измерены, поэтому 63.80 % — оптимистичная оценка. Смягчает то, что кривая
> гладкая: прирост есть на всём диапазоне α ∈ [0.25, 0.6], а не в одной точке.
> На втором удержанном наборе выбор α не проверялся.

---

## 0. Подготовка окна (один раз на окно PowerShell)

Откройте PowerShell **в корне репозитория** (каталог, где лежат `AGENTS.md` и `dataset/`) — все
команды этого runbook копипастятся оттуда как есть.

> **Токена ещё нет?** Создайте каталог `.hf-cache` в корне репозитория и положите туда свой токен
> (`hf auth login` кладёт его в `%USERPROFILE%\.cache\huggingface\token`; скопируйте его в
> `.hf-cache\token`) либо задайте `HF_HOME` на свой общий кэш. **Токен не печатать, не копировать
> в репозиторий и не коммитить.**

`HF_HOME` указывает на каталог `.hf-cache`: токен лежит в `$HF_HOME\token`, а снапшоты моделей — в
`$HF_HOME\hub`, поэтому `HF_HUB_CACHE` указывает на подпапку `hub` (иначе веса не находятся локально
и `from_pretrained` пойдёт в сеть).

```powershell
$env:PYTHONIOENCODING="utf-8"          # без этого кириллица в логах ломается

# из корня репозитория: токен в $HF_HOME\token, снапшоты моделей — в $HF_HOME\hub
$env:HF_HOME      = (Resolve-Path .\.hf-cache).Path
$env:HF_HUB_CACHE = Join-Path $env:HF_HOME "hub"
```

Проверка, что GPU виден (должно быть `True`):

```powershell
.venv-gpu\Scripts\python.exe -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

---

## 1. Шаг 1 — дообучение с мягким learning rate

Это ровно та команда, которая дала измеренные числа в отчёте
`reports/TRAINING_PPOCR_V6_BIG.md` (лог — `train/run_ppocr/big/log.txt`):

```powershell
.venv-gpu\Scripts\python.exe train\finetune_ppocr.py --out train\run_ppocr\big `
    --epochs 20 --batch-size 32 --lr 1e-5 --head-lr 1e-5 `
    --workers 6 --eval-every 1 --save-every 100 --max-minutes 36
```

* `--out` — каталог прогона; всё остальное пишется туда.
* `--lr 1e-5` — **не поднимайте до 1e-4**. При 1e-4 дообучение на этом сплите ухудшило
  метрику (медиана по удержанным типам 0.600 → 0.410, `reports/TRAINING_PPOCR_V6.md` §4).
* `--max-minutes 36` — «мягкая» остановка: скрипт сам доходит до конца эпохи, пишет
  `ckpt\final.pt` и завершается. Поставьте больше (например `--max-minutes 240`) или
  уберите флаг, чтобы доучиться все 20 эпох.
* Первые ~41 с скрипт тратит на **нулевой шаг** — замер предобученной модели на наших
  типах. Это страховка: если нулевой шаг дал ~0.6, вход сделан правильно и обучаться есть
  на что; если 0.0 — пайплайн сломан, и учиться бессмысленно.
* **Это только шаг 1.** Дообучение само по себе ухудшает метрику (58.80 % → 48.00 %).
  Дальше — **шаг 2: интерполяция весов с базой** (раздел 5).

Прогон «на два шага» (проверка, что всё живое, ~2 минуты):

```powershell
.venv-gpu\Scripts\python.exe train\finetune_ppocr.py --out train\run_ppocr\smoke `
    --epochs 2 --limit-per-type 20 --batch-size 32 --lr 1e-5 --head-lr 1e-5
```

---

## 2. Остановка

| как | что происходит | что теряется |
|---|---|---|
| **Ctrl+C** в окне, где идёт обучение | скрипт падает с `KeyboardInterrupt` | текущий батч и текущая эпоха (незаписанные шаги) |
| **мягкая остановка** `--max-minutes N` | скрипт сам доходит до конца эпохи, пишет `ckpt\final.pt` и выходит с кодом 0 | ничего |

Что **уже сохранено** в `train\run_ppocr\<прогон>\`:

| файл | что внутри | когда пишется |
|---|---|---|
| `ckpt\step_000100.pt`, `step_000200.pt`, … | **полное состояние**: модель + оптимизатор + scheduler + GradScaler + номер эпохи + номер шага + аргументы | каждые `--save-every` шагов (по умолчанию 100) |
| `ckpt\final.pt` | то же полное состояние | в конце **каждого** прогона (даже прерванного по времени) |
| `best.pt` | **только веса** лучшего чекпоинта по медиане exact match на удержанных типах | после каждой валидации, если метрика улучшилась |
| `log.txt` | весь лог прогона (дописывается) | постоянно |
| `result.json` | финальные метрики по типам | только если прогон дошёл до конца |

Если окно потерялось и процесс «висит» — убить его:

```powershell
Get-Process python -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -like "*\.venv-gpu\*" } |
    Stop-Process -Force
```

Убитый процесс не пишет `final.pt`, но все `ckpt\step_*.pt`, которые успел сохранить,
остаются валидными — с них и продолжаем (раздел 3).

---

## 3. Продолжение без потери прогресса

### 3.1 Команда

```powershell
.venv-gpu\Scripts\python.exe train\finetune_ppocr.py --out train\run_ppocr\big `
    --epochs 20 --batch-size 32 --lr 1e-5 --head-lr 1e-5 `
    --workers 6 --eval-every 1 --save-every 100 --max-minutes 120 --resume
```

Ключевое: **тот же `--out` и те же гиперпараметры**, что и в первом запуске, плюс `--resume`.

### 3.2 Где лежат чекпоинты

```
train\run_ppocr\big\ckpt\step_000100.pt   ← состояние после 100 шагов
train\run_ppocr\big\ckpt\step_000200.pt
...
train\run_ppocr\big\ckpt\final.pt          ← состояние на конец прогона
train\run_ppocr\big\best.pt                ← лучшие веса (без оптимизатора)
```

Размер одного `step_*.pt` — **~230 МБ** (модель + состояние оптимизатора AdamW со
моментами + scheduler + GradScaler). `best.pt` — ~77 МБ. **Поставьте `--save-every 200`**
или подчистите старые `step_*.pt`, если не хватает места: 16 чекпоинтов — это ~3.7 ГБ.

### 3.3 Что именно лежит в чекпоинте

Проверено по коду `train/finetune_ppocr.py` (строки 465–468 для `step_*.pt`, 503–507 для
`final.pt`, чтение — 396–409):

```python
torch.save({"model":     model.state_dict(),      # веса
            "optimizer": optimizer.state_dict(),  # состояние AdamW (моменты 1 и 2)
            "sched":     sched.state_dict(),      # OneCycleLR: last_epoch, total_steps, LR
            "scaler":    scaler.state_dict(),     # GradScaler: текущий масштаб градиентов
            "epoch":     epoch,                   # номер эпохи
            "step":      global_step,             # номер шага
            "args":      vars(args)},             # аргументы запуска
           os.path.join(ckpt_dir, f"step_{global_step:06d}.pt"))
```

`--resume` читает **новейший** файл в `ckpt\`: сортировка по имени, берётся последний
из файлов, чьё имя начинается с `step_` или равно `final.pt`. Имена нумерованы с
нулями (`step_000100.pt`), поэтому «последний по имени» = «с наибольшим номером шага».
`final.pt` по алфавиту встаёт **перед** `step_*.pt`, поэтому он никогда не выигрывает у
чекпоинта с большим номером шага.

Свой номер шага увидеть можно так:

```powershell
.venv-gpu\Scripts\python.exe -c "import torch; c=torch.load(r'train\run_ppocr\big\ckpt\step_001600.pt',map_location='cpu',weights_only=False); print('epoch',c['epoch'],'step',c['step'],'keys',sorted(c.keys()))"
```

Взять конкретный (не новейший) чекпоинт: `--resume` всегда берёт новейший, поэтому
переименуйте или уберите из `ckpt\` более новые `step_*.pt` — и запустите `--resume`
снова. Например, продолжить с шага 800 при наличии шагов 1600:

```powershell
New-Item -ItemType Directory -Force -Path train\run_ppocr\big\ckpt_hold | Out-Null
Move-Item train\run_ppocr\big\ckpt\step_00[12-9]*.pt train\run_ppocr\big\ckpt_hold\
# ... запустить с --resume ...
```

### 3.4 Чего `--resume` **не** делает

* **Не меняет расписание LR.** `sched` восстанавливается из чекпоинта, поэтому `--epochs`
  при продолжении должен быть **тем же**, что и в первом запуске: OneCycleLR рассчитан на
  `steps_per_epoch × epochs` шагов и «дотянуть» его другим значением нельзя.
* **`--init-from` — работает.** Флаг загружает **только веса** из указанного чекпоинта
  и создаёт **новый** оптимизатор и **новое** расписание OneCycleLR
  (`train/finetune_ppocr.py:306-312`). Нулевой шаг после этого меряет именно эту модель.
  Это способ начать новый цикл обучения с другим LR, не продолжая старый:

  ```powershell
  .venv-gpu\Scripts\python.exe train\finetune_ppocr.py --out train\run_ppocr\big2 `
      --init-from train\run_ppocr\big\best.pt `
      --epochs 10 --lr 5e-6 --head-lr 5e-6 --batch-size 32 --workers 6 --max-minutes 30
  ```

  `--init-from` и `--resume` — не взаимозаменяемые: `--resume` продолжает тот же цикл
  (с тем же расписанием LR), `--init-from` начинает новый.
* **Не восстанавливает RNG-состояние** (только модель/оптимизатор/scheduler/scaler/шаг),
  поэтому после прерывания воспроизводимость по-seed не гарантируется.

---

## 4. Оценка без обучения

### 4.1 Нулевой шаг — замер предобученной модели на наших типах

Это и есть «оценка без обучения»: скрипт меряет модель и **выходит**, обучение не
начинается (в коде — ветка `if args.zero_step and not args.eval_only: … return`).

```powershell
.venv-gpu\Scripts\python.exe train\finetune_ppocr.py --out train\run_ppocr\zerostep `
    --zero-step --limit-per-type 20
```

Напечатает per-type таблицу `ZERO STEP (pretrained, before any training)` и медиану по
удержанным типам, и запишет `train\run_ppocr\zerostep\zero_step.json`.
Ориентир: медиана **≈ 0.588**, micro **≈ 0.55** на 7 удержанных типах
(`train/run_ppocr/big/log.txt`, строка «zero step»). Если число упало ниже 0.3 — сломался
вход (кроп по полосе, нормализация, BGR-порядок), а не модель.

> ⚠️ `--eval-only` **в одиночку не делает того, что читается в названии**: он только
> пропускает нулевой шаг, после чего обучение идёт дальше (код: `if not args.eval_only or
> args.zero_step:` — при `--eval-only` без `--zero-step` блок оценки не выполняется вовсе,
> а раннего выхода нет). Оценка без обучения — это `--zero-step` **без** `--eval-only`.

### 4.2 Оценка обученного чекпоинта без обучения

Чтобы не учить и не портить рабочий прогон, делаем копию каталога прогона и запускаем
в ней `--eval-only --resume` с `--epochs`, равным **«эпоха чекпоинта + 1»** — тогда цикл
обучения пуст (стартовая эпоха = `epoch + 1`, а `range(start_epoch, epochs)` пуст), и
скрипт только печатает метрики по типам.

Сначала узнать эпоху чекпоинта (она не обязана совпадать с номером шага):

```powershell
.venv-gpu\Scripts\python.exe -c "import torch; c=torch.load(r'train\run_ppocr\big\ckpt\step_001600.pt',map_location='cpu',weights_only=False); print('epoch',c['epoch'],'step',c['step'])"
```

Для `step_001600.pt` это `epoch 7`, значит `--epochs 8`:

```powershell
$eval = "train\run_ppocr\eval_check"
Remove-Item $eval -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path "$eval\ckpt" | Out-Null
Copy-Item train\run_ppocr\big\ckpt\step_001600.pt "$eval\ckpt\"
.venv-gpu\Scripts\python.exe train\finetune_ppocr.py --out $eval --eval-only --resume `
    --epochs 8 --limit-per-type 20 --device cuda
```

Что должно напечататься (проверено 22.10.2026 на CPU с `--limit-per-type 2`):

```
resumed from step_001600.pt (epoch 8, step 1600)
training: 8 epochs x 1 steps = 8 steps ...
resumable checkpoint written: ...\ckpt/final.pt (epoch 7, step 1600)
--- FINAL (last epoch, no best checkpoint) ---
  out/JSH32/Minecaptcha/map          n=   2 exact=0.500 cer=0.125
  ...
  MEDIAN over 7 types: exact=0.5 cer=0.125  (micro: exact=0.6429 cer=0.131)
```

Строки `epoch N: loss=...` быть не должно — значит обучение действительно не шло.
(Если `--epochs` поставить больше «эпоха + 1», скрипт выполнит ещё одну эпоху.)

---

## 5. Шаг 2 — интерполяция весов с базой (WiSE-FT)

Дообучение на 13 типах с полосой **забывает предобучение**: медиана по 7 удержанным
типам падает с 58.80 % до 48.00 %. Лечится интерполяцией весов обратно к базе:

```
θ(α) = α · θ_дообученной + (1 − α) · θ_предобученной
```

`α = 0` — предобученная модель, `α = 1` — дообученная. Измеряем сетку α тем же
пайплайном, что и обучение (те же 7 удержанных типов, те же 3500 картинок, тот же кроп,
та же нормализация, тот же жадный CTC-декод).

```powershell
.venv-gpu\Scripts\python.exe train\soup_eval.py
```

Скрипт без аргументов повторяет опубликованное измерение: он берёт
`train\run_ppocr\big\best.pt`, меряет 7 значений α и пишет рядом с ним
`soup.json` (все измерения) и `soup_best.pt` (веса лучшего α).

**Измеренная сетка** (7 удержанных типов, 3500 картинок; `train/run_ppocr/big/soup.json`):

| α | медиана exact | медиана CER | micro exact | micro CER |
|---|---|---|---|---|
| 0.00 — предобученная база | 58.80 % | 16.57 % | 56.46 % | 24.46 % |
| 0.25 | 62.00 % | 14.83 % | 59.91 % | 21.32 % |
| **0.40 — публикуем это** | **63.80 %** | **15.03 %** | **61.23 %** | **20.04 %** |
| 0.50 | 61.40 % | 16.30 % | 61.23 % | 19.64 % |
| 0.60 | 59.20 % | 17.73 % | 61.00 % | 19.51 % |
| 0.75 | 54.20 % | 20.40 % | 59.49 % | 19.95 % |
| 1.00 — чистое дообучение | 48.00 % | 22.33 % | 54.80 % | 21.81 % |

Контроль согласованности сработал: α = 0.00 воспроизводит нулевой шаг прогона
(58.80 % / 56.46 %), α = 1.00 — его лучший чекпоинт (48.00 % / 54.80 %).

Полезные флаги (по `train\soup_eval.py --help`):

```powershell
# другой чекпоинт
.venv-gpu\Scripts\python.exe train\soup_eval.py --ckpt train\run_ppocr\big\ckpt\step_000800.pt

# своя сетка alpha и свои выходные файлы
.venv-gpu\Scripts\python.exe train\soup_eval.py --alphas 0,0.1,0.2,0.3,0.4,0.5 `
    --out train\run_ppocr\big\soup2.json --soup-ckpt train\run_ppocr\big\soup2_best.pt

# быстрая проверка на 3 картинках с типа (не измерение, а smoke-тест)
.venv-gpu\Scripts\python.exe train\soup_eval.py --alphas 0.0 --limit-per-type 3 `
    --out tmp_soup.json --soup-ckpt tmp_soup.pt
```

> ⚠️ **α и эпоха выбраны на удержанном наборе** — 63.80 % это оптимистичная оценка.
> На втором наборе удержанных типов выбор не проверялся.

---

## 6. Шаг 3 — экспорт и выкладка весов на Hugging Face

Репозиторий модели: **<https://huggingface.co/Titlehhhh/captchaocr-ppocrv6>** — веса выложены
2026-10-22: коммит `43a65582a9171ae5fb8cf2dd688c0bd4340bca0c`, 8 файлов,
`model.safetensors` 76 747 448 Б (карточку правили ещё трижды, последний коммит карточки —
`f5e30ebe`).

Перед выкладкой проверьте, что в экспорте действительно интерполяция, а не чистое
дообучение: в `train\run_ppocr\big\export\finetune_meta.json` должно стоять
`"soup_alpha": 0.4`.

### 6.1 Экспорт дообученных весов PP-OCRv6 (рекомендуемый путь)

```powershell
$env:HF_HOME      = (Resolve-Path .\.hf-cache).Path
$env:HF_HUB_CACHE = Join-Path $env:HF_HOME "hub"

# ВАРИАНТ A (рекомендуемый): экспортировать интерполяцию --soup-alpha 0.4.
# Скрипт сам считает theta = alpha*theta_ft + (1-alpha)*theta_base по той же формуле.
.venv-gpu\Scripts\python.exe train\run_ppocr\export_hf.py `
    --ckpt train\run_ppocr\big\best.pt --soup-alpha 0.4 `
    --out  train\run_ppocr\big\export

# ВАРИАНТ B: экспортировать готовый soup_best.pt из шага 2.
.venv-gpu\Scripts\python.exe train\run_ppocr\export_hf.py `
    --ckpt train\run_ppocr\big\soup_best.pt `
    --out  train\run_ppocr\big\export
```

> **Не экспортируйте `best.pt` без `--soup-alpha`.** Это чистое дообучение — на 10.8 п.п.
> хуже базы. Публикуем только α = 0.4.

Что получится в `train\run_ppocr\big\export\`:

| файл | что |
|---|---|
| `model.safetensors` | веса дообученной модели (архитектура не менялась — `config.json` базы валиден) |
| `config.json` | скопирован из базы `PaddlePaddle/PP-OCRv6_medium_rec_safetensors` |
| `preprocessor_config.json` | тоже из базы, **но нормализация пропатчена** на PaddleOCR (`(x/255-0.5)/0.5`) — с Imagenet-нормализацией модель получила бы пиксели, которых не видела |
| `processor_config.json` | `PPOCRV6SmallRecImageProcessor` |
| `character_list.txt` | словарь модели: 18 710 записей, индекс 0 = blank |
| `finetune_meta.json` | происхождение экспорта: чекпоинт, эпоха, шаг, число параметров |

### 6.2 Экспорт нашего CRNN+CTC (для сравнения / отдельной публикации)

`train/export_hf.py` собирает **самостоятельный** репозиторий HF из CRNN-чекпоинта
(конфиг, класс модели, процессор, словарь, веса, ONNX, карточка модели) и **сам себя
проверяет**: сверяет предсказания обучающего кода, экспортированного кода, свежего
процесса и ONNX — и падает, если они разошлись.

```powershell
.venv-gpu\Scripts\python.exe train\export_hf.py --from-run train\run `
    --out build\hf_export --charset latin --repo-id Titlehhhh/captchaocr-ppocrv6
```

Флаг этого скрипта (проверено `--help`): `--checkpoint`, `--from-run`, `--out`,
`--charset {latin,cyrillic}`, `--val-report`, `--repo-id`, `--n-verify`,
`--dataset-roots`, `--skip-onnx`, `--skip-verify`, `--report`.
Формат чекпоинта у него — **CRNN** (`train/train.py`), а не PP-OCR; для PP-OCR
используйте `train/run_ppocr/export_hf.py` из раздела 5.1.

### 6.3 Выкладка на Hugging Face

```powershell
$env:HF_HOME      = (Resolve-Path .\.hf-cache).Path
$env:HF_HUB_CACHE = Join-Path $env:HF_HOME "hub"
hf auth whoami                                   # ✓ Logged in / user: Titlehhhh
hf upload Titlehhhh/captchaocr-ppocrv6 train\run_ppocr\big\export --repo-type model
```

Проверить, что загрузилось:

```powershell
hf repo-files Titlehhhh/captchaocr-ppocrv6
```

> Токен лежит в `.hf-cache\token` и подхватывается автоматически, **когда задан
> `HF_HOME`**. Без `HF_HOME` `hf` скажет, что не авторизован. `HF_HOME` также нужен
> любому обращению к хабу из Python (`huggingface_hub`).

---

## 7. Сколько это занимает (измерено, GTX 1080 Ti)

Источник — `train/run_ppocr/big/log.txt` (прогон: 20 эпох × 204 шага, batch 32,
вход 48×320, fp16 + GradScaler) и `reports/TRAINING_PPOCR_V6.md` (предыдущий прогон).

| величина | значение |
|---|---|
| скорость | **82–100 img/s** (fwd+bwd, batch 32, fp16) |
| длительность шага | 79–172 мс |
| нулевой шаг (оценка 3500 картинок) | 41.3 с |
| одна эпоха обучения | **58–93 с** чистого обучения |
| одна эпоха целиком (обучение + валидация при `--eval-every 1`) | ~1.5–2.2 мин |
| весь прогон 20 эпох | ~30–36 мин (столько и было отдано под `--max-minutes 36`) |
| предыдущий прогон (100 картинок на тип, 30 эпох) | 101–119 img/s; 6 эпох ≈ 90 с; весь прогон ≈ 2 мин 20 с |
| размер чекпоинта | ~230 МБ (`step_*.pt`), ~77 МБ (`best.pt`) |
| веса в safetensors | ~77 МБ |
| шаг 2 (интерполяция, 7 значений α) | ~41 с на α → **~5 мин** на всю сетку |
| шаг 3 (экспорт + проверка) | ~2 мин |

Ориентир для планирования: **20 эпох ≈ полчаса**, и это с валидацией каждый эпоху.

---

## 8. Если что-то пошло не так

| симптом | причина | что делать |
|---|---|---|
| `CUDA out of memory` | батч 32 при 48×320 на 11.8 ГБ не влезает (или параллельно идёт другая задача) | `--batch-size 16` (шагов в эпоху станет 408 вместо 204 — расписание LR удлинится вдвое), при необходимости `--batch-size 8` и `--workers 4` |
| `PermissionError` / нет доступа к `HF_HOME` | не задан `HF_HOME` | `$env:HF_HOME = (Resolve-Path .\.hf-cache).Path` и `$env:HF_HUB_CACHE = Join-Path $env:HF_HOME "hub"` — из корня репозитория |
| `torch.cuda.is_available() == False` | вызван системный `python` | только `.venv-gpu\Scripts\python.exe` |
| `hf` не авторизован | не задан `HF_HOME` | `$env:HF_HOME=...`, затем `hf auth whoami` |
| «`build.ps1` не запускается» / «AuthorizationManager check failed» | на этой машине выполнение `.ps1` заблокировано | выполняйте логику инлайн (ниже) |
| датасет пуст / `train items: 0` | `dataset/out` и `dataset/out_ru` не пересобраны | команды ниже |
| лосс висит на 4.14 (`ln 63`) первые ~1000 шагов | это **плато all-blank CTC**, норма | не «чините» модель, ждите |
| после дообучения метрика **упала** | модель забывает предобучение (13 типов / 6500 картинок против тысяч шрифтов PP-OCR) | понижайте `--lr` (1e-4 → 1e-5), `--head-lr` так же; либо заморозьте бэкбон |
| кириллические типы выпали из обучения | в словаре PP-OCRv6 **нет ни одной буквы U+0400–U+04FF** (проверено) | это не баг: для кириллицы нужна другая база (`cyrillic_PP-OCRv5_mobile_rec`) |
| выложили чистое дообучение, а метрика упала | опубликован α = 1.0 вместо α = 0.4 | переэкспортируйте с `--soup-alpha 0.4` (раздел 6.1) — это **−10.8 п.п.** разницы |
| `soup_eval.py` пишет «checkpoint not found» | в каталоге прогона нет `best.pt` | передайте путь явно: `--ckpt train\run_ppocr\big\best.pt` |
| `soup_eval.py` падает на `from finetune_ppocr import ...` | скрипт запущен из другой директории | запускайте из корня репозитория: `.venv-gpu\Scripts\python.exe train\soup_eval.py` |

### Пересборка датасета (если папки `dataset/out`, `dataset/out_ru` нет или они пустые)

`build.ps1` на этой машине **запустить нельзя** — политика выполнения блокирует `.ps1`.
Логика скрипта выполняется инлайн:

```powershell
$javac = if ($env:JAVA_HOME) { "$env:JAVA_HOME\bin\javac.exe" } else { "javac" }
$java  = if ($env:JAVA_HOME) { "$env:JAVA_HOME\bin\java.exe"  } else { "java" }
$core  = Get-ChildItem -File dataset\generator\dev\captcha\*.java | % FullName

& $javac -encoding UTF-8 -d build\classes    -sourcepath dataset\generator    $core (Get-ChildItem -Recurse -Filter *.java dataset\generator    | % FullName)
& $javac -encoding UTF-8 -d build\classes_ru -sourcepath dataset\generator_ru $core (Get-ChildItem -Recurse -Filter *.java dataset\generator_ru | % FullName)

& $java "-Djava.awt.headless=true" -cp build\classes    dev.captcha.Gen      dataset\out    500
& $java "-Djava.awt.headless=true" -cp build\classes    dev.captcha.Validate dataset\out
& $java "-Djava.awt.headless=true" -cp build\classes_ru dev.captcha.Gen      dataset\out_ru 500
& $java "-Djava.awt.headless=true" -cp build\classes_ru dev.captcha.Validate dataset\out_ru

python tools\restore_real_shots.py     # вернуть reference-скриншоты после пересборки
```

> **Генераторы не засеяны**: пересборка даст *другие* случайные сэмплы (шрифты те же,
> текст и шум — новые). Измерение всегда ведётся на конкретной папке; «пересоберём и
> получим то же самое» здесь неверно.

---

## 9. Карта файлов

| путь | что |
|---|---|
| `train/finetune_ppocr.py` | обучение PP-OCRv6: сплит, нулевой шаг, CTC, `--resume`, оценка по типам |
| `train/ppocr_data.py` | датасет для этого скрипта: кроп по полосе, масштаб 48, BGR, нормализация, словарь |
| `train/train.py` | наш собственный CRNN+CTC с нуля (другая ветка) |
| `train/captcha_crnn.py` | архитектура CRNN и обработка полос |
| `train/export_hf.py` | экспорт CRNN-чекпоинта в самостоятельный репозиторий HF (+ ONNX + самопроверка) |
| `train/soup_eval.py` | **шаг 2**: интерполяция весов с базой (WiSE-FT), измерение сетки α, запись `soup.json` и `soup_best.pt` |
| `train/run_ppocr/export_hf.py` | экспорт дообученных весов PP-OCRv6 в папку HF (`--soup-alpha` для интерполяции) |
| `train/run_ppocr/big/` | текущий прогон: `log.txt`, `best.pt`, `ckpt/step_*.pt`, `ckpt/final.pt`, `export/` |
| `reports/TRAINING_PPOCR_V6.md` | предыдущий прогон (100 картинок на тип) с разбором |
| `reports/TRAINING_PPOCR_V6_BIG.md` | текущий прогон (500 картинок на тип): три строки результата и сетка α |
| `reports/TRAINING_CRNN_BIG.md` | наш CRNN на большом датасете: 37.20 % медиана на невиданных типах |
| `reports/TRAINING_TROCR_BIG.md` | TrOCR-small: замер не завершён, нулевой шаг 0.00 % |
| `reports/bench_models/*.json` | измеренные чужие модели (единый протокол) |
| `docs/INPUT_PIPELINE.md` | как PNG доходит до модели: кроп по полосе, масштаб, нормализация, размер тензора — три конвейера в сравнении |
| `docs/OCR_MODELS_101.md` | обзор ландшафта моделей (OCR / VLM / CTC) |
| `reports/HTML/index.html` | HTML-отчёт проекта: датасет, модели, замеры, этот же runbook |
