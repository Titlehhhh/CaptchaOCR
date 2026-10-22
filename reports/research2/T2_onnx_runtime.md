# ТЕСТ T2 — свой runtime: наш CRNN → ONNX → int8 → «одна папка без Python»

**Дата:** 2026-10-22. **Машина:** Windows, Xeon E5-2697 v4 (18 ядер/36 потоков, Broadwell, AVX2 **без
VNNI** — по отчёту волны 1 F), GTX 1080 Ti 11.8 ГБ (sm_61), torch 2.14.1+cu126 в `.venv-gpu`,
onnx 1.23.2, onnxruntime 1.30.0, MSVC 14.51.36231 (VS 18 Community), Windows SDK 10.0.26100.0,
.NET SDK 9/10/11.

**Задача волны 2:** не проектировать свой рантайм, а **измерить готовый**: экспортировать нашу
модель в ONNX с динамической шириной, квантизовать в int8, измерить точность и скорость на
PyTorch/ORT и собрать минимальную поставку «одна папка, без Python», которая даёт тот же ответ,
что PyTorch.

**Все числа ниже — измерены на этой машине.** Команды приведены в §9, результаты — в
`reports/bench_models/T2_*.json`. Ничего не переносилось из чужих отчётов без проверки; там, где
цифра взята из волны 1, это помечено.

---

## 0. Коротко (главное)

1. **Экспорт в ONNX с динамической шириной работает и не теряет точность.** Наш CRNN+CTC
   (4 623 615 параметров, 63 класса) выгружается в opset 17 одним файлом **18 499 690 Б**;
   оси batch и width динамические (`image: [batch, 1, 32, width]`, `logits: [batch, time, 63]`).
   Расхождение логитов с PyTorch — **≤ 7.6·10⁻⁶** (ширины 60/128/400, батч 1; батч 4 × 200).
   Двухслойный BiLSTM выгружается **двумя узлами `LSTM`** стандартного ONNX (веса
   `[2,1024,1024]` и `[2,1024,512]`) — спецоперация не нужна.
2. **ONNX fp32 даёт ровно те же цифры, что PyTorch**: 1.000 exact match на 6 обученных типах и
   0.000 на 4 невиданных (медианный CER по невиданным 0.954) — то есть **рантайм не меняет
   ничего**, включая запоминание. Числа PyTorch воспроизвелись с опубликованными в
   `reports/TRAINING_MINIMAL_LATIN.md` (единственное расхождение — CER `haq/mapcha/map`
   1.061 против 1.058 в том отчёте; причина в §2.3).
3. **int8 на CPU — не ускорение, а потеря точности.** Динамическая квантизация (веса int8) даёт
   файл **4 668 471 Б** (в 3.96 раза меньше fp32) и **не теряет** точность (1.000 / 0.000), но
   **медленнее fp32 в 4 раза** (107.2 против 430.5 img/s на 18 потоках). Статическая квантизация
   **оставила LSTM во float32** (поэтому файл почти не ужался: 17 259 234 Б) и **сломала один тип**
   (1.000 → 0.740 на `ringoame196-s-mcPlugin/ReproductionCAPTCHA/map`); с `reduce_range=True`
   деградация исчезает — 1.000 / 0.000.
4. **CUDA EP в ONNX Runtime на 1080 Ti работает.** Это **подтверждает** рекомендацию волны 1
   (F): для 1080 Ti нужен пакет ORT ≤ 1.26, собранный под CUDA 12 — такой пакет
   (`onnxruntime-gpu==1.26.0`) и поставил сессию с `CUDAExecutionProvider` на sm_61, строки
   совпали с CPU **120/120**. Но **медленнее CPU** при одном кадре (64.9 против 279.9 img/s) и
   лишь быстрее при батче 32 (931.6 против 703.8 img/s).
5. **«Папка без Python» собрана и проверена.** Три варианта: C (C API ONNX Runtime + WIC, 194 КБ
   exe), C# (`Microsoft.ML.OnnxRuntime` + `System.Drawing`) и Python (onnxruntime + pillow, без
   torch). На 20 случайных полосах fp32 все три дают **тот же ответ, что PyTorch, 20/20**;
   ширина полосы совпадает с трейнерской 20/20. Препроцессинг C/C# отличается от PIL **не более
   чем на 1 уровень серого** (7.8·10⁻³ в нормализованных единицах) — это не меняет ответ fp32, но
   на int8 одну полосу из 20 переворачивает (модель на грани ties).
6. **Главный вывод для владельца:** «llama.cpp для капчи» как *исполнитель* не нужен — за день
   работы получена готовая поставка. А вот **формат поставки** надо выбрать сейчас, и у нас есть
   выбор: ONNX (совместимость со всем) против ncnn (меньше, но свой формат) — §7.

---

## 1. Что и на чём измерялось

| Что | Значение | Откуда |
|---|---|---|
| Модель | `train/run/main/ckpt/step_0005700.pt` (step 5700), CRNN+CTC, **4 623 615** параметров, 63 класса | `train/captcha_crnn.py:327-373` |
| Чекпоинт | 6 обученных типов, 4 held-out | `reports/TRAINING_MINIMAL_LATIN.md` §4 (команда прогона) |
| Вход | `(B, 1, 32, W)`, `T = W/4`, W плавает | `train/captcha_crnn.py:250-258` |
| Нормализация | `(x/255 − 0.5)/0.5` | `train/captcha_crnn.py:261-262` |
| PyTorch | 2.14.1+cu126 (`.venv-gpu`), CUDA доступна | измерено |
| ONNX / ORT | onnx 1.23.2, onnxruntime **1.30.0** (pip, только CPU EP: `['AzureExecutionProvider','CPUExecutionProvider']`) | измерено |
| ORT с GPU | `onnxruntime-gpu==1.26.0` в отдельном venv `build/scratch/venv-ortgpu`; CUDA 12 runtime и cuDNN 9 взяты из `torch/lib` | измерено |
| C-компилятор | MSVC 14.51.36231, `cl.exe` через `vcvars64.bat`; gcc/g++ в PATH нет | измерено |
| .NET | SDK 9.0.314 / 10.0.300 / 10.0.402 / 11.0.100-rc.2; NuGet доступен | измерено |

**Датасет не перегенерировался и не удалялся**; `dataset/**` не менялся. Датасет — 46 типов,
4600 картинок; измерение шло по 10 типам главного прогона (999 полос: 600 обученных + 399
held-out).

---

## 2. Шаг 1 — экспорт в ONNX с динамической шириной

### 2.1 Что и как выгружено

```powershell
.venv-gpu\Scripts\python.exe bench\export_onnx.py export
```

* Экспортёр — **legacy TorchScript** (`torch.onnx.export(..., dynamo=False)`). Причина измерена:
  современный экспортёр (`dynamo=True`) аргумент `dynamic_axes` принимает, но на нашей модели
  **падает**: `ConversionError: Failed to decompose the FX graph for ONNX compatibility` →
  `RuntimeError: stack expects each tensor to be equal size, but got
  torch.Size([Min((s0//4), (s0//128)), 1, 256])` — динамическая ось ширины ломает разложение
  `torch.stack` в экспорте LSTM. То есть для нашей архитектуры рабочий путь — legacy-экспортёр.
* Opset **17**. Вход `image` `(N,1,32,W)`, выход `logits` `(N,T,63)`; оси batch и width динамические.
* `CRNN.forward` возвращает `(logits, w)`, поэтому экспортируется обёртка, возвращающая только
  логиты (`bench/export_onnx.py`, класс `LogitsOnly`).
* Модель в `eval()`, `do_constant_folding=True` — BatchNorm слился в свёртки **ещё при экспорте**:
  в графе нет ни одного узла `BatchNormalization`, только 4 `Conv` (§2.4).

### 2.2 Проверка совпадения с PyTorch

| вход | torch | onnx | max abs diff логитов |
|---|---|---|---|
| (1,1,32,60) | (1,15,63) | (1,15,63) | **5.722·10⁻⁶** |
| (1,1,32,128) | (1,32,63) | (1,32,63) | **5.722·10⁻⁶** |
| (1,1,32,400) | (1,100,63) | (1,100,63) | **5.722·10⁻⁶** |
| (4,1,32,200) | (4,50,63) | (4,50,63) | **7.629·10⁻⁶** |

Разница — шум порядка float32; на argmax она не влияет (см. §2.3: строки совпадают 999/999).
Файл: `reports/bench_models/T2_export_parity.json`.

### 2.3 Точность: тот же протокол, что в `reports/TRAINING_MINIMAL_LATIN.md`

Протокол: полоса по `roi` → grayscale → высота глифа (медиана «занятых» строк) → масштаб до 32 px
→ нормализация → жадный CTC-декод; exact match + CER, пер-тип и медиана по типам. Ровно тот же
код (`train/captcha_crnn.py`), только вместо torch — ORT.

**Важная деталь протокола:** CTC-декод в трейнере идёт по **всей ширине батча**, включая
паддинг, а `input_lengths` при обучении тоже равен полной ширине батча. Поэтому измерение зависит
от того, как набирается батч: у трейнера batch 32, здесь 64. На точность это не повлияло
(1.000/0.000 в обоих), но на CER held-out типов повлияло в одну десятую: `haq/mapcha/map`
**1.061** (здесь, batch 64) против **1.058** (в `TRAINING_MINIMAL_LATIN.md`, batch 32). Это
расхождение объясняется размером батча, а не рантаймом. Отдельно проверено: **одна полоса за
раз** (без паддинга, ровно как в рантайме) даёт те же 1.000/0.000 и CER 1.056 — то есть формат
поставки на оценку не влияет.

| тип (роль) | torch fp32 | ONNX fp32 | ONNX int8 dynamic | ONNX int8 static +reduce_range |
|---|---|---|---|---|
| `Archy-X/Krypton/map` (обучен) | 1.000 / 0.000 | 1.000 / 0.000 | 1.000 / 0.000 | 1.000 / 0.000 |
| `GalleryCaptcha/ru-web` (обучен) | 1.000 / 0.000 | 1.000 / 0.000 | 1.000 / 0.000 | 1.000 / 0.000 |
| `JSH32/Minecaptcha/map` (обучен) | 1.000 / 0.000 | 1.000 / 0.000 | 1.000 / 0.000 | 1.000 / 0.000 |
| `just-captcha/ProstoCaptcha/map` (обучен) | 1.000 / 0.000 | 1.000 / 0.000 | 1.000 / 0.000 | 1.000 / 0.000 |
| `n1zamu/NCaptcha/anvil` (обучен) | 1.000 / 0.000 | 1.000 / 0.000 | 1.000 / 0.000 | 1.000 / 0.000 |
| `ringoame196-s-mcPlugin/ReproductionCAPTCHA/map` (обучен) | 1.000 / 0.000 | 1.000 / 0.000 | 1.000 / 0.000 | 1.000 / 0.000 |
| `CaptchaVerifyZ/map` (held-out) | 0.000 / 0.928 | 0.000 / 0.928 | 0.000 / 0.924 | 0.000 / 0.922 |
| `haq/mapcha/map` (held-out) | 0.000 / 1.061 | 0.000 / 1.061 | 0.000 / 1.053 | 0.000 / 1.063 |
| `jSdCool/minecaptcha/text` (held-out) | 0.000 / 0.912 | 0.000 / 0.912 | 0.000 / 0.910 | 0.000 / 0.911 |
| `laforetbrut/are-you-sure/code` (held-out) | 0.000 / 0.980 | 0.000 / 0.980 | 0.000 / 0.983 | 0.000 / 0.980 |
| **6 обученных, 600 полос** | **1.000** | **1.000** | **1.000** | **1.000** |
| **4 held-out, 399 полос** | **0.000** | **0.000** | **0.000** | **0.000** |
| медианный CER по held-out | 0.954 | 0.954 | 0.954 | 0.951 |

**Как это читать.** 1.000 на обученных типах — это **запоминание** (оно же доказано подменой
пикселей в `TRAINING_MINIMAL_LATIN.md` §6.3), а 0.000 на невиданных типах — это **то, что надо
чинить в данных**. Ни экспорт, ни int8, ни смена рантайма эти два числа не сдвинули ни на
тысячную: рантайм на точность не влияет **0**.

### 2.4 Граф ONNX (что получилось)

| файл | узлы | крупнейшие веса |
|---|---|---|
| `crnn_fp32.onnx` (18 499 690 Б) | Conv×4, Relu×4, MaxPool×3, **LSTM×2**, MatMul×1, Shape/Constant/Reshape/Transpose×… | `LSTM_428` [2,1024,1024] fp32 = 8.39 МБ; `LSTM_471` [2,1024,512] = 4.19 МБ; `Conv_383` [256,128,3,3] = 1.18 МБ; `MatMul_473` [512,63] = 0.13 МБ |

* Двухслойный BiLSTM выгрузился **двумя стандартными узлами `LSTM`** — ONNX-оператор LSTM
  ([спецификация](https://onnx.ai/onnx/operators/onnx__LSTM.html)) не имеет атрибута
  `num_layers`, но умеет хранить слои в форме весов `[num_directions, num_layers, …]`.
  Спецоперация ORT не понадобилась.
* Динамическая ширина **пережила** экспорт: вход объявлен `['batch', 1, 32, 'width']`,
  выход `['batch', 'time', 63]`; та же модель без переэкспорта работала на ширинах 60…400 и в
  батчах со смешанными ширинами (§3).

---

## 3. Шаг 2 — квантизация int8

```powershell
.venv-gpu\Scripts\python.exe bench\export_onnx.py quantize
```

| вариант | размер | к fp32 | что квантовано | точность (6 обуч. / 4 held-out) |
|---|---|---|---|---|
| fp32 | **18 499 690 Б** | 1.00× | — | 1.000 / 0.000 |
| **dynamic int8** | **4 668 471 Б** | **0.252× (3.96× меньше)** | Conv→`ConvInteger`, MatMul→`MatMulInteger`, **LSTM→`DynamicQuantizeLSTM`** (contrib-операция ORT), веса int8 | **1.000 / 0.000** |
| static int8, `reduce_range=False`, калибровка 120 полос | 17 259 234 Б | 0.933× | Conv/MatMul int8 (QDQ, per-channel), **LSTM остался fp32** | **0.957 / 0.000** — `ringoame…` упал с 1.000 до **0.740** |
| **static int8, `reduce_range=True`, калибровка 120 полос** | 17 259 234 Б | 0.933× | то же | **1.000 / 0.000** |
| static int8, `reduce_range=False`, калибровка 600 полос | 17 259 234 Б | 0.933× | то же | 0.955 / 0.000 (`ringoame…` 0.730) |

### 3.1 Что показали эти числа

1. **Динамическая квантизация — лучший компромисс «размер/точность»**: файл в 3.96 раза меньше
   и точность не пострадала. Но она требует **contrib-операции `DynamicQuantizeLSTM`**, то есть
   такая модель исполняется **только в ONNX Runtime** (ncnn/MNN/TensorRT её не прочитают).
2. **Статическая квантизация у нас не сжимает модель**: LSTM-веса — это 16.7 МБ из 18.5 МБ, и
   статический квантователь их **не тронул** (в реестре ORT `LSTM` есть только в
   `IntegerOpsRegistry`, а `LSTMQuant` подменяет узел на `DynamicQuantizeLSTM`; в нашем прогоне
   этого не произошло). Итог — файл 17.3 МБ, то есть экономия 7 %, при риске потери точности.
3. **`reduce_range=True` — обязательное условие на этом CPU.** Broadwell — AVX2 **без VNNI**, и
   ORT прямо предупреждает про переполнение `VPMADDUBSW` на таких машинах и советует
   `reduce_range` ([документация по квантизации](https://onnxruntime.ai/docs/performance/model-optimizations/quantization.html)).
   Это подтвердилось измерением: без `reduce_range` один из шести обученных типов падает с 1.000
   до 0.740, с ним — 1.000.
4. **Больше калибровки ≠ лучше**: 600 полос вместо 120 не помогли (0.955 против 0.957) —
   деградацию `ringoame…` вызывает не выбор калибровочной выборки, а сама статическая схема.

---

## 4. Шаг 3 — скорость

Полосы: 120 настоящих полос 6 обученных типов (первые 20 каждого), ширины **64…240**; 5 повторов
каждой конфигурации; img/s = полосы / среднее время. Полные числа (среднее, σ, min, max) —
`reports/bench_models/T2_speed.json`.

### 4.1 CPU (Xeon E5-2697 v4)

| рантайм | потоки | batch 1, img/s | batch 32, img/s | batch 1: среднее ± σ |
|---|---|---|---|---|
| PyTorch fp32 | 8 (torch) | **202.2** | — | 593.5 ± 44.8 мс на 120 полос |
| **ORT fp32** | 1 | 114.2 | 118.8 | 1051.1 ± 49.0 мс |
| **ORT fp32** | 4 | 313.9 | 396.5 | 382.3 ± 36.1 мс |
| **ORT fp32** | 8 | **430.5** | 765.6 | 278.7 ± 22.4 мс |
| **ORT fp32** | 18 | 371.1 | 750.2 | 323.4 ± 20.5 мс |
| ORT int8 dynamic | 1 | 27.3 | 13.6 | 4397.1 ± 95.5 мс |
| ORT int8 dynamic | 4 | 46.4 | 31.3 | 2587.5 ± 56.9 мс |
| ORT int8 dynamic | 8 | 72.4 | 52.8 | 1657.9 ± 14.3 мс |
| **ORT int8 dynamic** | 18 | **107.2** | 88.0 | 1119.0 ± 14.5 мс |
| ORT int8 static+reduce | 1 | 87.7 | 89.0 | 1369.0 ± 45.9 мс |
| ORT int8 static+reduce | 4 | 206.9 | 239.2 | 579.9 ± 20.9 мс |
| ORT int8 static+reduce | 8 | 249.6 | 410.6 | 480.8 ± 9.7 мс |
| **ORT int8 static+reduce** | 18 | **259.4** | **578.8** | 462.6 ± 47.3 мс |

Выводы по CPU:

* **fp32 на 8 потоках — 430.5 img/s** (batch 1) и 765.6 img/s (batch 32). Это лучший CPU-режим;
  18 потоков уже хуже (371.1) — типичное перенасыщение.
* **int8 на этом CPU — медленнее fp32**: dynamic в 4 раза (107.2 против 430.5), static в 1.7 раза
  (259.4). Это ровно тот эффект, о котором предупреждает ORT на AVX2 без VNNI, и он совпадает с
  чужими сообщениями в треке ORT ([#20052](https://github.com/microsoft/onnxruntime/issues/20052)):
  «int8-модель оказалась медленнее fp32 на CPU». **Вывод: int8 у нас — это про размер, а не про
  скорость.**
* Никакой из этих режимов не является узким местом: солверу нужна десятая доля кадра в секунду.

### 4.2 GPU (GTX 1080 Ti, sm_61)

| рантайм | batch 1, img/s | batch 32, img/s | строки CPU vs GPU | max abs diff логитов |
|---|---|---|---|---|
| PyTorch fp32 (CUDA) | 97.8 | **1130.9** | — | — |
| **ORT fp32, CUDA EP** | 64.9 | **931.6** | **120/120** | 1.144·10⁻⁵ |
| ORT fp32, CPU (4 потока, тот же процесс) | 279.9 | 703.8 | | |
| **ORT int8 dynamic, CUDA EP** | 44.1 | 33.2 | **120/120** | **0.0** (бит в бит) |
| ORT int8 dynamic, CPU (4 потока) | 117.4 | 95.0 | | |
| **ORT int8 static+reduce, CUDA EP** | 66.1 | **1000.9** | **120/120** | **1.227·10⁻¹** |
| ORT int8 static+reduce, CPU (4 потока) | 288.5 | 630.5 | | |

Как это получено: пакет `onnxruntime-gpu==1.26.0` (последняя публичная сборка под CUDA 12; ORT
≥ 1.27 собирается под CUDA 13, а CUDA 13 выбросила Pascal — release notes CUDA, ссылка в §11) в
отдельном venv
`build/scratch/venv-ortgpu`; `cudart64_12.dll`, `cublas64_12.dll` и `cudnn64_9.dll` взяты из
`torch/lib` (тот же CUDA 12.6 и cuDNN 9). Сессия создаётся с провайдером
`CUDAExecutionProvider`, и **она действительно работает на sm_61** — это ровно тот вывод, к
которому пришла волна 1 (F, §9.4: «для 1080 Ti нужен пакет на CUDA 12.x (ORT ≤ 1.26)»).

Что из этого следует:

* **На одном кадре CPU выигрывает в 4.3 раза** (279.9 против 64.9 img/s): в модели почти нет
  параллелизма по кадрам, а LSTM последователен по времени — GPU тут нечего распараллеливать, и
  остаётся только накладные расходы на пересылку.
* **На батче 32 GPU выигрывает** (931.6 против 703.8) — но это fp32; для int8 dynamic GPU
  **проваливается** (33.2 img/s на батче 32 против 95.0 на CPU), потому что `DynamicQuantizeLSTM`
  — contrib-операция, у неё нет CUDA-ядра: часть графа уходит на CPU, и данные скачут между
  устройствами. Косвенно это подтверждается тем, что выход GPU **бит в бит равен** выходу CPU
  (diff 0.0): считала одна и та же реализация.
* Для int8 static логиты GPU и CPU расходятся на **1.227·10⁻¹** (это уровень «шум» квантизации:
  CUDA-EP и CPU считают QDQ по-разному), но **строки совпали 120/120** — на наших данных
  расхождение не перешло в ошибку.

---

## 5. Шаг 4 — «одна папка, без Python»

### 5.1 Что собрано

| вариант | файлы | размер | компиляция |
|---|---|---|---|
| **A. C (C API ORT + WIC)** | `bench/runtime_onnx.c` → `captcha_runtime.exe` | exe **194 048 Б** | `cl /O2 /I <ort>/include bench\runtime_onnx.c /Fe:captcha_runtime.exe /link /LIBPATH:<ort>/lib onnxruntime.lib windowscodecs.lib ole32.lib` |
| **B. C# (.NET)** | `build/scratch/csruntime/Program.cs` → `captcha.exe` + `captcha.dll` | для Windows: managed 2 220 376 Б + нативный `onnxruntime.dll` 16 462 648 Б = **17.84 МБ** (в папке сборки `dotnet build` 235 МБ, потому что NuGet кладёт нативные библиотеки для всех платформ — Linux `.so`, macOS `.dylib`, `.aar`) | `dotnet build -c Release` (NuGet: `Microsoft.ML.OnnxRuntime` 1.30.0, `System.Drawing.Common` 9.0.0) |
| **C. Python (обязательный)** | `bench/runtime_onnx.py` | 142 строки | только `onnxruntime` + `pillow` (+`numpy`), **без torch** |

Все три делают одно и то же: `crop по roi → grayscale → высота глифа → масштаб до 32 px →
нормализация → ORT → жадный CTC-декод`, и печатают JSON `{file, text, confidence, width}`.

### 5.2 Состав папки поставки

```
captcha-solver/
├── captcha_runtime.exe        194 048 Б   ← вариант A
├── onnxruntime.dll         16 462 648 Б   ← из релиза ORT 1.30.0 (win-x64)
├── crnn_fp32.onnx          18 499 690 Б   ← или crnn_int8_dynamic.onnx (4 668 471 Б)
├── config.json                    1 279 Б   ← charset, геометрия, нормализация
└── README.md
```

Итого **≈ 35.2 МБ** с fp32 или **≈ 21.3 МБ** с int8 dynamic. Никакого Python в рантайме; Python
нужен **один раз**, при сборке модели.

`config.json` (`bench/models/config.json`, 1.3 КБ — его можно коммитить) несёт всё, что рантайму
нужно: алфавит (62 знака + blank), `glyph_height=32`, `min_width=64`, `max_width=400`,
нормализацию (`mean=0.5`, `std=0.5`), правило кропа, имя входа/выхода, opset, динамические оси,
размер файла и исходный чекпоинт. Это ровно то, что в GGUF лежит в kv-метаданных.

### 5.3 Проверка «тот же результат, что PyTorch» (20 случайных полос)

20 полос, выбранных случайно (shuffle с сидом 20261022) из объединения 10 типов; фактически
попали **9 типов** (от 1 до 5 полос на тип, `n1zamu/NCaptcha/anvil` не попал); сравниваются и
текст, и препроцессинг, и логиты. Файл: `reports/bench_models/T2_runtime_parity.json`.

| модель | torch == Python(ORT) | torch == C | torch == C# | max abs diff препроцессинга | max abs diff логитов (ORT vs torch) |
|---|---|---|---|---|---|
| fp32 | **20/20** | **20/20** | **20/20** | 7.843·10⁻³ | 1.144·10⁻⁵ |
| int8 dynamic | 20/20 | 19/20 | 19/20 | 7.843·10⁻³ | 6.667·10⁻¹ |
| int8 static+reduce | 19/20 | 18/20 | 18/20 | 7.843·10⁻³ | 6.800·10⁻¹ |

Читать так:

* **Ширина полосы совпала с трейнерской 20/20** во всех трёх рантаймах — то есть геометрия
  (высота глифа, min/max width) воспроизведена точно.
* Препроцессинг C и C# отличается от PIL **не более чем на 1 уровень серого**
  (7.843·10⁻³ = (1/255)/0.5 в нормализованных единицах). Причина измерена отдельно: формула
  RGB→L в Pillow 13 — это округление `(299r + 587g + 114b)/1000` (проверено на 180 картинках
  12 076 640 пикселей: расхождение 259 пикселей на 1 уровень), а ресайз PIL BILINEAR — это
  треугольный фильтр с масштабированной поддержкой, горизонтальный проход **в 8-битный**
  промежуточный буфер и вертикальный проход; моя реализация совпала с PIL на ±1 уровень в 1.9 %
  пикселей (612 случайных ресайзов).
* **fp32 от этого не ломается: 20/20 во всех трёх вариантах.** На int8 одна полоса из 20
  переворачивается (`CaptchaVerifyZ/map/027.png`: torch `Mf6Q3` → C `Mf6Q0`) — причём на этой
  полосе разница препроцессинга всего 6·10⁻⁸, то есть переворот вызван **не** preprocess'ом, а
  тем, что int8-модель стоит на грани между двумя классами и любой шум в логитах (а он у int8
  достигает 0.67) переворачивает argmax. Это ещё один аргумент за fp32 как за режим по умолчанию.
* **Строка совпадает всегда; confidence — с точностью до 4-го знака.** Например, на целом кадре
  `JSH32/Minecaptcha/map/003.png` все три рантайма дают `77E4` и ширину 297, но confidence:
  Python 0.556486 (softmax в float32), C и C# 0.555760 (double). Расхождение — точность softmax,
  а не разные логиты.

### 5.4 Известные ограничения собранного рантайма

* C-вариант написан под **Windows SDK 10.0.26100**, где API WIC изменился
  (`IWICFormatConverter_Initialize` принимает формат вывода; в старых SDK он задавался в
  `CreateFormatConverter`). Под более старым SDK файл не соберётся без правки двух строк.
* Код декодирования PNG — WIC, то есть только Windows. Для Linux/macOS нужен другой декодер
  (libpng/stb_image) — это правка одной функции `load_grayscale`.
* C-вариант **не умеет** читать `roi` из `labels.jsonl` — `roi` передаётся аргументами
  командной строки (`x y w h`); для типов без полосы (`roi = null`) передавать нечего, и весь кадр
  уходит в модель (а модель обучена на высоте 32 — это отдельная задача, см. §7).
* Ни один из трёх вариантов не делает пост-обработку ответа (маска по алфавиту типа, маска по
  длине, «число словом → цифры», арифметика) — она описана в `train/README.md` и по логике
  принадлежит солверу, а не распознавателю.

---

## 6. Шаг 5 — что переносится из llama.cpp, а что нет

Ссылка на первоисточники: [llama.cpp README](https://github.com/ggml-org/llama.cpp/blob/master/README.md),
[ggml README](https://github.com/ggml-org/ggml), [gguf.md — спецификация GGUF](https://github.com/ggml-org/ggml/blob/master/docs/gguf.md),
[docs/ops.md — таблица операций llama.cpp](https://github.com/ggml-org/llama.cpp/blob/master/docs/ops.md),
[ONNX Runtime: сборка под C++/C](https://onnxruntime.ai/docs/get-started/with-cpp.html),
[ONNX Runtime: квантизация](https://onnxruntime.ai/docs/performance/model-optimizations/quantization.html),
[ONNX: оператор LSTM](https://onnx.ai/onnx/operators/onnx__LSTM.html),
[ONNX Runtime: таблица ядер](https://github.com/microsoft/onnxruntime/blob/main/docs/OperatorKernels.md),
[ncnn: слой LSTM](https://github.com/Tencent/ncnn/blob/master/src/layer/lstm.h).

| элемент llama.cpp | переносится? | что это значит для CaptchaOCR (проверено измерением) |
|---|---|---|
| **«Веса + метаданные в одном файле»** | **да** | наш `config.json` (1.3 КБ) + `.onnx` — это ровно та же идея, что kv-метаданные в GGUF. Проверено: рантайм читает charset/геометрию/нормализацию из конфига и ничего не знает о модели |
| **«Один .exe + файлы, без Python»** | **да, и сделано** | §5: 194 КБ exe + DLL + модель + конфиг. Ровно тот «опыт поставки», ради которого всё затевалось |
| **Квантизация ради размера** | **да** | dynamic int8: 18.5 МБ → 4.67 МБ, точность не пострадала (§3). Но на этом CPU int8 **медленнее** fp32 (§4.1) — то есть выигрыш только в размере дистрибутива |
| **importance matrix (imatrix)** | **нет, не нужно** | у нас нет трансформерных весов и «важных» токенов; роль imatrix играет калибровка на своих картинках (измерено: 600 полос не лучше 120, §3) |
| **CPU-ядра/SIMD** | **частично** | наш узкий участок — LSTM (последовательный), а не GEMM; ORT уже даёт AVX2-ядра. Свой SIMD-ядро для LSTM — это работа, а не выигрыш (в 100 раз хватает текущей скорости) |
| **Операция LSTM/GRU в ggml** | **нет** | проверено независимо: в `docs/ops.md` **0** вхождений `LSTM` и `GRU`, при этом `CONV_2D` есть. То есть CNN-часть на ggml собрать можно, а рекуррентную — только своими руками. В ONNX это решено готовым оператором: наш граф — 2 стандартных узла `LSTM` (§2.4) |
| **KV-кэш** | **нет** | CTC не авторегрессивен: между кадрами состояние не переносится, у каждого примера своё нулевое состояние. Место KV-кэша в нашем графе — пустое |
| **Токенизатор (BPE/SentencePiece)** | **да, тривиально** | «токенизатор» капчи — 62 знака + blank и правило «схлопнуть повторы, выкинуть blank»; это ~20 строк кода, а не словарь на 50 000 токенов |
| **Динамическая длина последовательности** | **в ONNX — штатная ситуация; в ggml — проблема** | измерено: один и тот же `.onnx` обработал ширины 60, 128, 400 и батчи со смешанными ширинами без пересборки. Для ggml пришлось бы бакеризовать ширину (7 корзин) или паддинг до 400 |
| **Сервер / OpenAI-совместимый REST / веб-UI** | **нет** | капче не нужен диалог; аналог «превью» — CLI, который на файл печатает строку и confidence (это и делает наш рантайм) |
| **Собственный конвертер PyTorch → свой формат** | **да, дёшево** | наш конвертер — это `torch.onnx.export` (10 строк) плюс `quantize_dynamic` (1 строка). Для GGUF-подобного формата это было бы ~200 строк, но **формат GGUF для капчи никто не исполняет** — готового исполнителя CRNN в GGUF не существует |

**Итог шага 5.** «llama.cpp для капчи» переносится как **опыт поставки** (папка, без Python,
веса с метаданными в одном файле, квантизация ради размера) — и он уже реализован. Как
**исполнитель** — не переносится: в ggml нет LSTM, а писать BiLSTM руками ради нули по
точности — это месяцы работы. ONNX Runtime даёт тот же «опыт поставки» без единой строки
рантайма, и его C API документирован как «тонкая обёртка над C API»
([with-cpp](https://onnxruntime.ai/docs/get-started/with-cpp.html)), а готовые `.zip` с
заголовками и библиотеками лежат ассетами каждого релиза.

---

## 7. Сводка решений для владельца

1. **Формат поставки: ONNX.** Он даёт «одну папку без Python» сегодня, работает на CPU и GPU,
   читается ncnn/MNN/TensorRT/OpenVINO, и не привязывает нас к одному рантайму. GGUF-подобный
   формат имеет смысл, только если мы готовы написать свой исполнитель для BiLSTM.
2. **Квантизация: dynamic int8** (4.67 МБ, точность 1.000/0.000) — если важен размер дистрибутива;
   **fp32** (18.5 МБ) — если важна скорость и стабильность на границах классов. Статическую int8
   с `reduce_range=True` использовать можно (1.000/0.000), но она почти не сжимает модель, потому
   что LSTM остаётся fp32.
3. **Режим по умолчанию: CPU, 8 потоков, 430.5 img/s** (fp32, batch 1). GPU на той же модели
   выигрывает только на батчах от ~32 (931.6 против 703.8 img/s у CPU с 4 потоками в том же
   процессе), а на одном кадре **проигрывает в 4.3 раза** (64.9 против 279.9 img/s).
4. **Публиковать на Hugging Face**: `.onnx` (fp32 + int8 dynamic), `config.json` и этот рантайм.
   Рантайм — то, что отличает HF-релиз от «просто весов».
5. **Рантайм не лечит главную проблему проекта.** Точность на невиданных типах — 0.000, и ни
   экспорт, ни int8, ни C, ни C#, ни GPU её не сдвинули ни на одну тысячную. Следующая работа —
   данные (обучение на публичном корпусе капч, как советует `TRAINING_MINIMAL_LATIN.md` §10).

---

## 8. Чего не сделано и что мешало

| пункт | статус | причина |
|---|---|---|
| ncnn-путь (pnnx → `.param`/`.bin`) | **не делал** | вне рамок брифа (T2 — ONNX/ORT). Волна 1 нашла, что слой LSTM в ncnn есть и bidirectional, и int8 — это стоит проверить отдельным тестом: `pnnx` → ncnn и сверка выходов с torch |
| ORT-GPU на ORT ≥ 1.27 | **не проверял** | проверял только 1.26.0 (последняя сборка под CUDA 12); по release notes CUDA 13 Pascal выброшен, так что 1.27+ на 1080 Ti ожидаемо не поедет — но это вывод из документации, а не измерение |
| int8 на GPU как «ускорение» | **не получилось** | измерено: dynamic int8 на CUDA EP медленнее CPU (33.2 против 95.0 img/s на батче 32) — contrib-операция `DynamicQuantizeLSTM` уходит на CPU |
| Статическая квантизация LSTM | **не получилась** | квантователь ORT оставил LSTM-веса во float32; отдельного «ручного» квантования LSTM в ORT нет (в стандарте ONNX int8-LSTM не существует) |
| Экспорт через современный dynamo-экспортёр (`dynamo=True`) | **не получилось** | `ConversionError: Failed to decompose the FX graph for ONNX compatibility` → `RuntimeError: stack expects each tensor to be equal size` — динамическая ось ширины ломает разложение `torch.stack` при экспорте LSTM. Рабочий путь — legacy-экспортёр (`dynamo=False`), §2.1 |
| Собственный препроцессинг в C/C# с точностью до бита | **не получилось** | PIL BILINEAR и RGB→L воспроизведены с точностью ±1 уровень серого; идеального совпадения нет (см. §5.3) |
| C-рантайм под Linux/gcc | **не собирал** | gcc в PATH нет, MSVC есть; в файле оставлена строка сборки для gcc/clang |
| Кросс-проверка C# на Linux | **не делал** | .NET на Windows требует `System.Drawing.Common` — Windows-only |
| «Одна папка» с батчевым режимом, HTTP-сервером, веб-UI | **не делал** | для капчи это лишнее (§6) |
| Обучение новой модели, новые чекпоинты | **не делал** | бриф запрещает трогать `train/**`; использованы существующие прогоны |
| Датасет | **не перегенерировался и не удалялся** | по правилам репозитория; `dataset/**` не менялся |

---

## 9. Воспроизведение

```powershell
# 1. экспорт + проверка совпадения с PyTorch + config.json
.venv-gpu\Scripts\python.exe bench\export_onnx.py export

# 2. квантизация (dynamic + три статических варианта)
.venv-gpu\Scripts\python.exe bench\export_onnx.py quantize

# 3. точность: torch (эталон) и каждая модель
.venv-gpu\Scripts\python.exe bench\export_onnx.py eval-torch --out reports\bench_models\T2_eval_torch_main.json
.venv-gpu\Scripts\python.exe bench\export_onnx.py eval --model bench\models\crnn_fp32.onnx            --out reports\bench_models\T2_eval_onnx_fp32.json
.venv-gpu\Scripts\python.exe bench\export_onnx.py eval --model bench\models\crnn_int8_dynamic.onnx     --out reports\bench_models\T2_eval_onnx_int8_dynamic.json
.venv-gpu\Scripts\python.exe bench\export_onnx.py eval --model bench\models\crnn_int8_static_reduce.onnx --out reports\bench_models\T2_eval_onnx_int8_static_reduce.json
# одна полоса за раз (как в рантайме):
.venv-gpu\Scripts\python.exe bench\export_onnx.py eval --model bench\models\crnn_fp32.onnx --batch-size 1 --out reports\bench_models\T2_eval_onnx_fp32_single.json

# 4. скорость (CPU: torch и ORT, 4 модели × 4 числа потоков)
.venv-gpu\Scripts\python.exe bench\export_onnx.py speed --models bench\models\crnn_fp32.onnx `
    bench\models\crnn_int8_dynamic.onnx bench\models\crnn_int8_static_reduce.onnx bench\models\crnn_int8_static.onnx `
    --out reports\bench_models\T2_speed.json

# 5. сборка C-рантайма (нужен распакованный релиз ORT: include/ + lib/)
$ort = "build\scratch\ort_dl\ort\onnxruntime-win-x64-1.30.0"
cmd /c "`"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat`" >nul && cl /nologo /O2 /I `"$ort\include`" bench\runtime_onnx.c /Fe:build\scratch\cruntime\captcha_runtime.exe /link /LIBPATH:`"$ort\lib`" onnxruntime.lib windowscodecs.lib ole32.lib"

# 6. запуск рантаймов
python bench\runtime_onnx.py --model bench\models\crnn_fp32.onnx --config bench\models\config.json `
    --image dataset\out\Archy-X\Krypton\map\001.png --roi 27 32 21 8
build\scratch\cruntime\captcha_runtime.exe bench\models\crnn_fp32.onnx bench\models\config.json `
    dataset\out\Archy-X\Krypton\map\001.png 27 32 21 8
```

GPU-часть (шаг 4.2) воспроизводится в отдельном окружении: `onnxruntime-gpu==1.26.0` в
`build/scratch/venv-ortgpu`, а `cudart64_12.dll`/`cublas64_12.dll`/`cudnn64_9.dll` берутся из
`.venv-gpu\Lib\site-packages\torch\lib` (через `os.add_dll_directory`).

---

## 10. Файлы

**Создано (владею):**

| файл | что |
|---|---|
| `bench/export_onnx.py` | экспорт, квантизация, оценка точности, замер скорости (4 подкоманды) |
| `bench/runtime_onnx.py` | минимальный рантайм без torch (вариант C) |
| `bench/runtime_onnx.c` | рантайм на C API ONNX Runtime + WIC (вариант A) |
| `bench/models/config.json` | конфиг модели для рантайма (1.3 КБ, коммитится) |
| `reports/research2/T2_onnx_runtime.md` | этот отчёт |
| `reports/bench_models/T2_*.json` | результаты измерений (9 файлов) |

**Не коммитится** (по правилу брифа — веса большие, `*.onnx` в `.gitignore`):
`bench/models/crnn_fp32.onnx`, `crnn_int8_dynamic.onnx`, `crnn_int8_static.onnx`,
`crnn_int8_static_reduce.onnx`, `crnn_int8_static_full.onnx`, `crnn_fp32_preproc.onnx`.

**Не тронуто:** `dataset/**`, `train/**` (только чтение), `agents/**`, `AGENTS.md`, `HANDOVER.md`,
`reports/bench_results*.json`, чужие отчёты в `reports/research2/`. Ничего не закоммичено.

**Сборочные артефакты (в `build/`, gitignore):** `build/scratch/ort_dl/` (релиз ORT 1.30.0 win-x64,
82 645 522 Б), `build/scratch/cruntime/` (exe + obj + dll), `build/scratch/csruntime/` (исходник
C#-рантайма `Program.cs`, `captcha.csproj` и сборка — исходник C#-варианта лежит в scratch, а не в
`bench/`, потому что бриф T2 перечисляет владение только для `bench/runtime_onnx.c` и
`bench/runtime_onnx.py`), `build/scratch/venv-ortgpu/` (venv с onnxruntime-gpu).

---

## 11. Ссылки

* ONNX Runtime: [сборка под C++/C](https://onnxruntime.ai/docs/get-started/with-cpp.html) ·
  [квантизация](https://onnxruntime.ai/docs/performance/model-optimizations/quantization.html) ·
  [таблица ядер операторов](https://github.com/microsoft/onnxruntime/blob/main/docs/OperatorKernels.md) ·
  [CUDA EP](https://onnxruntime.ai/docs/execution-providers/CUDA-ExecutionProvider.html)
* ONNX: [оператор LSTM](https://onnx.ai/onnx/operators/onnx__LSTM.html) ·
  [экспорт из PyTorch](https://docs.pytorch.org/docs/stable/onnx_export.html)
* llama.cpp / ggml: [README llama.cpp](https://github.com/ggml-org/llama.cpp/blob/master/README.md) ·
  [docs/ops.md](https://github.com/ggml-org/llama.cpp/blob/master/docs/ops.md) ·
  [спецификация GGUF](https://github.com/ggml-org/ggml/blob/master/docs/gguf.md) ·
  [README ggml](https://github.com/ggml-org/ggml)
* ncnn: [слой LSTM](https://github.com/Tencent/ncnn/blob/master/src/layer/lstm.h) ·
  [pnnx](https://github.com/Tencent/ncnn/blob/master/tools/pnnx/README.md)
* NVIDIA: [release notes CUDA](https://docs.nvidia.com/cuda/cuda-toolkit-release-notes/index.html)
* Внутренние: `reports/TRAINING_MINIMAL_LATIN.md` (протокол и базовые цифры) ·
  `reports/research2/F_runtime_llamacpp.md` (волна 1: рантаймы, ncnn, ggml) ·
  `reports/research2/C_how_it_works.md` (волна 1: конвейер и нормализация)
