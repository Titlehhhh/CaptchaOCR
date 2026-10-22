# Направление F — свой runtime по образцу llama.cpp, но для капчи

**Дата сбора материала:** 2026-10-22. **Инструменты:** навык `web-search` (ddgs) + `web_fetch`, чтение raw-файлов на GitHub, локальные измерения из репозитория CaptchaOCR.
**Задача направления:** разобрать, из чего состоит llama.cpp, что из этого переносится на CRNN+CTC; собрать список готовых рантаймов для маленьких OCR-сетей (лицензии/платформы/скорость); разобрать экспорт CRNN в ONNX и квантизацию int8; найти путь «одна папка с файлами и без Python»; сравнить «свой C++ runtime с готовыми весами» против «готовый runtime (ONNX Runtime) + свои веса».

---

## Выводы (кратко)

1. **llama.cpp — это не «модель», а три отдельные вещи:** формат-контейнер GGUF ([спецификация](https://github.com/ggml-org/ggml/blob/master/docs/gguf.md)), тензорная библиотека ggml (MIT, «plain C/C++ implementation without any dependencies», 2–8-битная квантизация, [README ggml](https://github.com/ggml-org/ggml)) и собственно исполнитель llama.cpp (MIT, [README](https://github.com/ggml-org/llama.cpp/blob/master/README.md)). Переносимы контейнер + идея «веса и метаданные в одном файле» + «ноль зависимостей»; **не переносимы** KV-кэш, сервер, веб-UI и сам формат LLM-графа.
2. **Главное техническое препятствие для ggml-подобного рантайма: в ggml нет операции LSTM.** В официальной таблице операций [`docs/ops.md`](https://github.com/ggml-org/llama.cpp/blob/master/docs/ops.md) есть `CONV_2D`, `CONV_2D_DW`, `IM2COL`, `POOL_2D`, но слов `LSTM`/`RNN`/`GRU` в файле — **0 вхождений**. Единственная найденная реализация LSTM поверх ggml — это R-пакет ggmlR, где LSTM развёрнут в **статический** граф BPTT ([rdrr.io/cran/ggmlR](https://rdrr.io/cran/ggmlR/man/ggml_layer_lstm.html)). У нас ширина входа вариативна (T = W/4, W ∈ [64…400]), то есть статический граф не подходит без бакетеризации ширины.
3. **Готовый рантайм «одна папка без Python» уже есть, и их два.** ONNX Runtime ([LICENSE](https://github.com/microsoft/onnxruntime/blob/main/LICENSE)), C/C++ API — тонкая обёртка над C API, `.zip`/`.tgz` лежат ассетами в каждом релизе ([docs/get-started/with-cpp](https://onnxruntime.ai/docs/get-started/with-cpp.html)); и **ncnn** (BSD-3, «no third-party runtime dependencies») — в нём **есть слой LSTM с `direction=bidirectional` и int8**, а pnnx экспортирует `nn.LSTM` из PyTorch напрямую ([`src/layer/lstm.h`](https://github.com/Tencent/ncnn/blob/master/src/layer/lstm.h), [tools/pnnx/README.md](https://github.com/Tencent/ncnn/blob/master/tools/pnnx/README.md)). Аналог «капчи в llama.cpp» в готовом виде — **RapidOCR**: модели PaddleOCR → ONNX, рантаймы на Python/C++/Java/C#, движки onnxruntime/tensorrt/paddle/openvino/pytorch/mnn, лицензия Apache-2.0 ([README](https://github.com/RapidAI/RapidOCR)).
4. **Квантизация int8 у нас упирается в две вещи:** (а) int8-LSTM в стандарте ONNX нет — оператор `LSTM` поддерживает только float/double/float16 ([таблица ядер ORT](https://github.com/microsoft/onnxruntime/blob/main/docs/OperatorKernels.md)), а ORT при статической квантизации подменяет LSTM на contrib-операцию `DynamicQuantizeLSTM` ([operators/lstm.py](https://github.com/microsoft/onnxruntime/blob/main/onnxruntime/python/tools/quantization/operators/lstm.py)); (б) наш CPU — Xeon E5-2697 v4 (Broadwell, AVX2 **без VNNI**), а ORT прямо предупреждает про переполнение VPMADDUBSW на AVX2/AVX512 без VNNI ([docs квантизации](https://onnxruntime.ai/docs/performance/model-optimizations/quantization.html)).
5. **Железо ограничивает именно GPU-ускорение, а не CPU.** CUDA 13 «Removed support for Maxwell, Pascal, and Volta GPUs, corresponding to compute capabilities earlier than Turing» ([release notes CUDA](https://docs.nvidia.com/cuda/cuda-toolkit-release-notes/index.html)), а ORT ≥1.27 GPU-пакеты по умолчанию собраны на CUDA 13.0 ([CUDA EP](https://github.com/microsoft/onnxruntime/gh-pages/docs/execution-providers/CUDA-ExecutionProvider.md)) → на GTX 1080 Ti (sm_61) они не поедут; int8 на GPU требует Tensor Core int8 (T4/A100), «Older hardware will not benefit from quantization».
6. **Скорость рантайма — не наш узкий момент.** Локально измерено: наш CRNN на CPU даёт **451 img/s** при 32×128 (70.9 мс/кадр) и 104 img/s при 64×256 ([../MODEL_PLAN.md:104-109](../MODEL_PLAN.md)); базовая линия EasyOCR — 388 мс/кадр ([MODEL_PLAN.md:364](../MODEL_PLAN.md)). Солверу нужна десятая доля кадра в секунду.
7. **Всё нужное для пути «ONNX» уже стоит на машине:** в `.venv-gpu` есть `onnx 1.23.2`, `onnxscript 0.7.2`, `onnxruntime 1.30.0` (и в системном Python `onnxruntime 1.30.0`), MSVC 14.51 + встроенный cmake есть в `C:\Program Files\Microsoft Visual Studio\18\Community`. Ничего доустанавливать не нужно, чтобы сделать экспорт + int8 + C++-CLI.
8. **Итог по направлению:** «llama.cpp для капчи» как *собственный рантайм* — это работа на несколько недель с нулевым влиянием на точность; как *формат поставки* (папка с .exe + модель + charset, без Python) — это уже решено готовыми средствами. Правильная очередь работ — сначала данные (type-held-out = 0.000), потом формат поставки.

---

## 0. Опорные факты: что уже есть на машине и в репозитории

Это измерения и состав окружения, на которые опираются выводы отчёта. Всё локальное проверено командами, приведёнными рядом.

| Факт | Значение | Источник / как проверено |
|---|---|---|
| Наша модель | CRNN: 4 conv-блока + 2-слойный BiLSTM (hidden 256) + CTC, **4 623 615 параметров**, 63 класса | `../../train/captcha_crnn.py:327-373`; `AGENTS.md` §6 |
| Вход | `(B, 1, 32, W)`, W — ширина по глифу, `T = W/4` | `../../train/captcha_crnn.py:340-373` |
| Нормализация | `(a/255 - 0.5)/0.5` → [-1, 1] | `../../train/captcha_crnn.py:261-262` |
| Скорость инференса (torch, CPU, 8 потоков) | 32×128 → **70.9 мс = 451 img/s**; 32×160 → 86.9 мс = 368 img/s; 48×192 → 78.9 мс = 203 img/s; 64×256 → 77.0 мс = 104 img/s | `../MODEL_PLAN.md:104-109` (модель 2.02 M) |
| То же для модели 5.28 M | **371 img/s** | `../../docs/adr/0002-recogniser-architecture-and-data.md:1081` |
| Базовая линия EasyOCR | **388 мс/кадр** на CPU | `../MODEL_PLAN.md:364` |
| Обучение | 99 img/s CPU против **920 img/s** на GTX 1080 Ti | `AGENTS.md` §6; `../MODEL_PLAN.md:92` |
| Локальный замер чужих ONNX-капч | captCHAD fp32 acc 0.0 / CER 1.0115; captCHAD int8 acc 0.0 / CER 0.9865; phpwind acc 0.0 / CER 0.9904 | `../bench_results_onnx.json` (замер через `../bench/bench_onnx.py`) |
| Python-пакеты | `.venv-gpu`: `onnx 1.23.2`, `onnxscript 0.7.2`, `onnxruntime 1.30.0`, `torch 2.14.1+cu126`; системный Python: `onnxruntime 1.30.0`, `torch 2.14.1` | `pip list` в обоих окружениях |
| C++-тулчейн | MSVC **14.51.36231** (VS 18 Community), `vcvars64.bat`, встроенный `cmake.exe`; в PATH нет ни `cl`, ни `g++`, ни `cmake` (есть `ninja` из pip) | `Get-Command`; `C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC` |
| CPU | Intel Xeon E5-2697 v4 @ 2.30 GHz, 18 ядер / 36 потоков, Broadwell → AVX2, **без AVX-512 и без VNNI** | `Get-CimInstance Win32_Processor` (Family 6 Model 79) |
| GPU | GTX 1080 Ti, sm_61, драйвер 581.57 | `AGENTS.md` §7 |

Расчёт (мой, не измерение): fp32-веса нашей модели ≈ 4.62 M × 4 Б ≈ **18.5 МБ**, int8 ≈ **4.6 МБ**. Для сравнения, DLL ONNX Runtime весит больше, чем весь наш fp32-модель, — то есть квантизация весов ради « размера » тут не даёт ничего.

---

## 1. Анатомия llama.cpp: из чего она на самом деле состоит

### 1.1 GGUF — контейнер

Источник: [ggml/docs/gguf.md](https://github.com/ggml-org/ggml/blob/master/docs/gguf.md) (спецификация GGUF v3).

Заявленные свойства формата:

* **Single-file deployment** — «they can be easily distributed and loaded, and do not require any external files for additional information»;
* **mmap-compatible** — модель грузится отображением в память, отсюда мгновенный старт;
* **Key-value метаданные** вместо списка безымянных значений (наследие GGJT);
* **Little-endian по умолчанию**, выравнивание задаётся `general.alignment` (по умолчанию 32);
* **Структура файла**: заголовок (`magic` = `GGUF`, `version` = 3, `tensor_count`, `metadata_kv_count`) → массив `gguf_tensor_info_t` (имя, число измерений, размеры, `ggml_type`, смещение) → padding → `tensor_data`.

Что там лежит помимо весов:

* `general.architecture` (обязательное), `general.quantization_version` (обязательное, если что-то квантовано), `general.alignment`, `general.file_type` (перечисление `MOSTLY_F32 … MOSTLY_Q6_K`), `general.license` (SPDX-выражение), `general.name/author/version/…`;
* гиперпараметры архитектуры (`[llm].context_length`, `[llm].embedding_length`, `[llm].block_count`, `[llm].attention.head_count`, …);
* **токенизатор**: `tokenizer.ggml.model` (`llama`/`replit`/`gpt2`/`rwkv`), `tokenizer.ggml.tokens`, `.scores`, `.token_type` (1=normal, 2=unknown, 3=control, 4=user defined, 5=unused, 6=byte), `.merges`, `.added_tokens`, плюс `tokenizer.ggml.bos_token_id` и т.д.;
* раздел «Computation graph» помечен как **будущее расширение** — то есть на момент спецификации граф в файле не хранится, исполнитель знает архитектуру из кода.

### 1.2 Квантизации Q4/Q8

Типы тензоров перечислены в `enum ggml_type` спецификации GGUF: `F32, F16, Q4_0, Q4_1, Q5_0, Q5_1, Q8_0, Q8_1, Q2_K…Q8_K, IQ1_S…IQ4_XS, I8/I16/I32/I64, F64, IQ1_M, BF16, TQ1_0, TQ2_0, MXFP4` (всего 40). Это **блочные** форматы: Q4_0 — 32 веса в блоке, Q4_K/Q5_K/Q6_K — k-кванты с суперблоками, IQ* — адаптивные («i-quant») с кодовыми книгами.

Как это устроено в llama.cpp ([tools/quantize/README.md](https://github.com/ggml-org/llama.cpp/blob/master/tools/quantize/README.md)):

* две фазы: (1) конвертация исходной модели в GGUF (`convert_hf_to_gguf.py`, требует Python), (2) собственно `llama-quantize`;
* **importance matrix (imatrix)** — файл с важностью каждого веса; `--imatrix`, `--include-weights`, `--exclude-weights`; imatrix минимизирует потери качества;
* точечные инструменты: `--pure` (все тензоры одним типом), `--tensor-type` (regex по имени тензора), `--leave-output-tensor`, `--token-embedding-type`, `--prune-layers`, `--override-kv`, `--keep-split`, `--allow-requantize` (с предупреждением «can severely reduce quality»);
* качество измеряется через perplexity и KL-дивергенцию.

**Измеренная таблица из того же README (Llama-3.1-8B)** — это единственная публичная измеренная таблица «размер ↔ скорость ↔ битность», которую я нашёл в первоисточнике:

| Метрика | IQ2_S | Q4_K_S | Q4_K_M | Q5_K_M | Q6_K | Q8_0 | F16 |
|---|---|---|---|---|---|---|---|
| bits/weight | 2.7403 | 4.6672 | 4.8944 | 5.7036 | 6.5633 | 8.5008 | 16.0005 |
| размер, GiB | 2.56 | 4.36 | 4.58 | 5.33 | 6.14 | 7.95 | 14.96 |
| prompt processing t/s @512 | 783.55 ±13.73 | 818.55 ±9.58 | 821.81 ±21.44 | 758.69 ±7.43 | 812.01 ±10.82 | 865.09 ±8.30 | 923.49 ±0.53 |
| text generation t/s @128 | 77.30 ±2.47 | 76.71 ±0.20 | 71.93 ±1.52 | 67.23 ±1.08 | 58.67 ±3.13 | 50.93 ±0.08 | 29.17 ±0.04 |

(Источник: [tools/quantize/README.md](https://github.com/ggml-org/llama.cpp/blob/master/tools/quantize/README.md), таблица «Quantization».) Обратите внимание на две вещи, важные для нас: (1) выигрыш квантизации тут — это **память/пропускная способность**, а не арифметика: F16-генерация в этой таблице *медленнее* Q8_0; (2) чем ниже битность, тем ближе к Q4/Q5 падение качества, поэтому для нашей задачи «сжимаем и теряем» — плохая сделка.

Ещё один важный факт для нашей задачи: **ggml сам по себе умеет 2–8-битную квантизацию** ([README ggml](https://github.com/ggml-org/ggml)), а «нулевые аллокации во время рантайма» — заявленное свойство ggml. То есть библиотека, на которой стоит llama.cpp, годится и как основа для captcha-подобного рантайма.

### 1.3 CPU-ядра и бэкенды

* llama.cpp: «AVX, AVX2, AVX512 and AMX support for x86 architectures», ARM NEON/Accelerate/Metal для Apple, RVV/ZVFH для RISC-V, свои CUDA-ядра, Vulkan и SYCL, гибрид CPU+GPU ([README](https://github.com/ggml-org/llama.cpp/blob/master/README.md)).
* Список бэкендов: BLAS, BLIS, CANN, CUDA, HIP, Hexagon, IBM zDNN, MUSA, Metal, OpenCL, OpenVINO (в процессе), RPC, SYCL, VirtGPU, Vulkan, WebGPU, ZenDNN ([там же]).
* Таблица покрытия операций по бэкендам — [`docs/ops.md`](https://github.com/ggml-org/llama.cpp/blob/master/docs/ops.md): `CONV_2D` (полностью поддержан на CPU, CUDA, Metal, SYCL, Vulkan, OpenCL, WebGPU), `CONV_2D_DW`, `IM2COL`, `POOL_2D` — и **ни одного** `LSTM`/`RNN`/`GRU`.

### 1.4 Токенизатор

В GGUF словарь встроен в файл (`tokenizer.ggml.tokens` и т.д.), при этом спецификация честно предупреждает: «implementations of tokenization using this vocabulary (i.e. `llama.cpp`'s tokenizer) may have lower accuracy than the original tokenizer» ([gguf.md, раздел Tokenizer](https://github.com/ggml-org/ggml/blob/master/docs/gguf.md)). Для LLM это BPE/SentencePiece; для капчи «токенизатор» — это 63 символа и правило CTC-схлопывания, то есть задача на порядок проще.

### 1.5 Превью, сервер, веб-UI

* Инструменты llama.cpp: `cli`, `completion`, `server` (REST API, совместимый с OpenAI), грамматики GBNF ([README, раздел Documentation](https://github.com/ggml-org/llama.cpp/blob/master/README.md)).
* В README показаны скриншоты «Built-in web UI against `llama serve`» и `llama serve -hf ggml-org/Qwen3.5-0.8B-GGUF` — то есть «превью» = встроенный веб-интерфейс к локальному серверу.
* Ни то, ни другое для капчи не нужно: у капчи нет диалога и нет промпта. Аналог «превью» здесь — это CLI, который на файл отвечает строкой распознавания и confidence.

### 1.6 Отсутствие зависимостей и лицензия

* llama.cpp — MIT ([README, бейдж](https://github.com/ggml-org/llama.cpp/blob/master/README.md)).
* ggml — MIT, «Plain C/C++ implementation without any dependencies», «Zero memory allocations during runtime», «Broad backend support — CPU, GPU, NPU, and browser» ([README ggml](https://github.com/ggml-org/ggml)).
* В llama.cpp подтянуты только single-header библиотеки: cpp-httplib (MIT), stb (public domain), nlohmann/json (MIT), miniaudio (public domain), subprocess.h (public domain) ([README, Acknowledgements](https://github.com/ggml-org/llama.cpp/blob/master/README.md)).

---

## 2. Что из llama.cpp переносится на CRNN+CTC, а что нет

| Элемент llama.cpp | Переносится? | Комментарий для CaptchaOCR |
|---|---|---|
| **Формат-контейнер «веса + метаданные в одном файле»** | **Да** | Нам в файле модели нужны: charset (63 символа + blank), `glyph_height=32`, диапазон ширины, правило нормализации (mean 0.5/std 0.5), версия и лицензия модели, тип файла (fp32/int8). GGUF как формат это умеет (kv-метаданные + тензоры + `general.license` в SPDX). |
| **Тип файла `general.file_type` (MOSTLY_*) и блочные Q-типы** | **Да** | Для наших 4.6 M параметров смысла почти нет: fp32 ≈ 18.5 МБ, int8 ≈ 4.6 МБ, а DLL рантайма весит больше. Квантизация оправдана ради скорости, не ради размера. |
| **importance matrix (imatrix)** | **Да, но не по назначению** | У нас нет «важных» и «неважных» трансформерных весов; калибровка решается обычным PTQ по нашему датасету (см. §5). |
| **CPU-ядра/SIMD (AVX2/AVX512, NEON)** | **Частично** | ggml даёт SIMD-ядра, но оптимизированы под большие GEMM; у нас вычислительно тяжёлыми являются свёртки 3×3 и рекуррентный шаг BiLSTM, а не матричное умножение. |
| **Операция CONV_2D / IM2COL / POOL_2D** | **Да** | Есть в ggml (см. §1.3) — то есть CNN-часть CRNN на ggml собрать реально. |
| **Операция LSTM/GRU** | **Нет** | В ggml её не существует (0 вхождений в `docs/ops.md`). Единственная найденная реализация — статически развёрнутый BPTT-граф в R-пакете ggmlR ([rdrr.io](https://rdrr.io/cran/ggmlR/man/ggml_layer_lstm.html)). |
| **KV-кэш** | **Нет** | CTC не авторегрессивен: у нас нет генерации токенов, состояние между кадрами не переносится. Для батча из N картинок LSTM-состояние обнуляется на каждом примере. |
| **Токенизатор** | **Да, но тривиально** | 63 символа + blank + правило «схлопнуть повторы, выкинуть blank» + опционально confidence = геометрическое среднее по posterior'ам выбранных классов (у нас это уже реализовано в `greedy_decode`, `../../train/captcha_crnn.py:378-403`). В GGUF это ложится в `tokenizer.ggml.tokens` + `tokenizer.ggml.token_type`. |
| **Динамическая длина последовательности** | **Проблема** | У llama.cpp длина задаётся пользователем и граф перестраивается. В ggml граф статический; наш T = W/4 меняется от 16 до 100 → либо бакеризация (например, 6 корзин), либо всегда паддинг до 400 (до ~6× лишнего вычисления). |
| **Сервер / OpenAI-совместимый REST / веб-UI** | **Нет** | Для солвера капч нужен CLI/библиотека, а не HTTP-сервер. Если позже понадобится — `llama-server` показывает, как это делается на cpp-httplib, но это отдельная работа. |
| **Отсутствие зависимостей, один .exe + один файл модели** | **Да — это и есть цель** | Именно этот «опыт поставки» нам и нужен: папка с `captcha.exe`, `model.onnx`/`model.gguf`, `charset.txt`, без Python. |
| **Экосистема конвертеров (`convert_hf_to_gguf.py`)** | **Да, в упрощённом виде** | Свой конвертер из PyTorch → свой формат — это ~200 строк, потому что мы знаем свою архитектуру. |

**Промежуточный вывод:** из llama.cpp переносится *упаковка и поставка*, а не *исполнение*. Исполнять LSTM в ggml — писать с нуля.

---

## 3. Готовые рантаймы для маленьких OCR-сетей

| Рантайм | Лицензия | Платформы | Что умеет для нашей задачи | Формат модели | Замечания |
|---|---|---|---|---|---|
| **ONNX Runtime** | **MIT** ([LICENSE](https://github.com/microsoft/onnxruntime/blob/main/LICENSE)) | Windows/Linux/macOS x64/x86/ARM64; Android/iOS; Web (WASM/WebGPU) | C/C++ API (тонкая обёртка над C API), Python/Java/C#/JS; CPU EP + CUDA/TensorRT/DirectML/OpenVINO/oneDNN/XNNPACK/QNN/RKNPU EP; PTQ int8 (static/dynamic), FP16, ORT-формат модели, минимальные сборки | `.onnx`, `.ort` | Самый практичный выбор: есть готовые CPU/CUDA EP, int8, mobilе; `.zip` с DLL+заголовками+либами — в каждом релизе ([with-cpp](https://onnxruntime.ai/docs/get-started/with-cpp.html)) |
| **ncnn** (Tencent) | **BSD 3-Clause** ([README](https://github.com/Tencent/ncnn/blob/master/README.md)) | Windows/Linux/macOS/Android/iOS/WASM/RPi/Jetson; CPU + **Vulkan** | «no third-party runtime dependencies», «no BLAS / NNPACK requirement»; pnnx конвертирует PyTorch/ONNX; int8 PTQ-тулы (ncnnoptimize/ncnn2table/ncnn2int8); **есть слой LSTM** (в т.ч. bidirectional) с int8-веткой; есть примеры PP-OCR | `.param` + `.bin` | Сильный кандидат на «свой рантайм без Python»: очень маленький, без зависимостей, **и умеет нашу архитектуру целиком** (см. §3.2) |
| **MNN** (Alibaba) | **Apache-2.0** ([README](https://github.com/alibaba/MNN/blob/master/README.md)) | iOS/Android/встраиваемые; CPU (ARM/x86), OpenCL/Vulkan/Metal/**CUDA**, NNAPI/QNN | «no dependencies»; **FP16/Int8 quantize, can reduce model size 50%-70%**; конвертер из ONNX/TF/Caffe/TorchScript; CNN/RNN поддержаны | `.mnn` | Промышленный, работает в Taobao/钉钉; MNN-LLM — уже «llama.cpp-подобный» продукт от Alibaba |
| **LiteRT** (бывший TFLite) | **Apache-2.0** (TensorFlow, [LICENSE](https://github.com/tensorflow/tensorflow/blob/master/LICENSE)) | Android/iOS/Linux/Windows/Web/Microcontrollers | C++ API, готовые C++ библиотеки, спецификация квантизации (int8, включая LSTM-варианты), Task Library | `.tflite` | Строгая модель операций; экспорт из PyTorch — через LiteRT CLI |
| **OpenVINO** | **Apache-2.0** ([README](https://github.com/openvinotoolkit/openvino/blob/master/README.md)) | x86/ARM, CPU/GPU/NPU | API на C++/C/Python/NodeJS; **INT8 через NNCF**; принимает ONNX/TF/TFLite/Paddle/JAX; OpenVINO EP в ORT | IR | Лучше всего для Intel-железа; у нас Xeon Broadwell — подходит |
| **Paddle Lite** | **Apache-2.0** ([README](https://github.com/PaddlePaddle/Paddle-Lite)) | x86 Linux, ARM Linux, Android, iOS; OpenCL; NPU через NNAdapter (Huawei Kirin/Ascend, Kunlunxin XPU, Eeasytech) | «встраивается в мобильные и встраиваемые устройства», FP16/INT8 | Paddle model → Lite | Тесно связан с PaddleOCR; для нашей модели лишняя обвязка |
| **RKNN-Toolkit2** (Rockchip) | **BSD-3-Clause** ([LICENSE](https://github.com/rockchip-linux/rknn-toolkit2/blob/master/LICENSE), «Copyright 2020 Rockchip Electronics Co.,Ltd») | Только NPU Rockchip (RK3588/RK3568/…) + PC для конвертации | Конвертирует в `.rknn`; v1.6.0 добавил модели OCR и распознавания номеров ([README](https://github.com/rockchip-linux/rknn-toolkit2)) | `.rknn` | Специализированный NPU-рантайм; нам не нужен (у нас не Rockchip) |
| **TensorRT** | NVIDIA EULA (не OSS) | NVIDIA GPU | Быстрый, int8-калибровка | `.engine`/`.plan` | Лицензия не свободная + на Pascal/старых CUDA есть ограничения; для нашего размера модели избыточен |
| **ggml** (без llama.cpp) | **MIT** ([README](https://github.com/ggml-org/ggml)) | CPU/GPU/NPU/браузер | Тензорная библиотека с SIMD-ядрами и 2–8-битной квантизацией, **но без LSTM** | свой (GGUF) | Единственный путь к «настоящему» llama.cpp-стилю; требует написать BiLSTM |

**Ключевой вывод по таблице:** для «одна папка, без Python» на Windows/x64 есть минимум три готовых ответа — **ONNX Runtime (MIT)**, **ncnn (BSD-3)** и **MNN (Apache-2.0)**. Все три умеют CPU-инференс маленьких CNN; для CRNN критично наличие LSTM-операции, и её нет только в ncnn/ggml — там её придётся писать руками.

### 3.1 Ближайший прецедент: RapidOCR

[RapidAI/RapidOCR](https://github.com/RapidAI/RapidOCR) — Apache-2.0, «модели PaddleOCR конвертируются в ONNX», рантаймы «Python, C++, Java, C#», движки `onnxruntime-cpu / onnxruntime-gpu / tensorrt / paddle / openvino / pytorch / mnn`, сборка C++-части через `make build-onnxruntime-cpu`. То есть «OCR-движок в стиле llama.cpp, собранный из чужих моделей и готового рантайма» — **уже существует и широко используется**. В описании проекта заявлено ускорение в 4–5× относительно движка на PaddlePaddle — это цифра самого проекта (китайский README/блог), а не независимое измерение; воспроизводить её я не мог.

Для нас это снижает ценность собственного рантайма ещё больше: аналог уже есть, и наш отличие может состоять только в собственных весах и специализированном препроцессинге (crop по `roi`, нормализация по глифу, CTC-декодер).

### 3.2 ncnn: слой LSTM есть, и он bidirectional + int8

Это была ключевая проверка, и она **изменила** мой предварительный вывод (я сначала записал, что в ncnn нет LSTM — это неверно, ниже факты).

* Файл слоя: [`src/layer/lstm.h`](https://github.com/Tencent/ncnn/blob/master/src/layer/lstm.h) — класс `ncnn::LSTM` с полями `num_output`, `weight_data_size`, `direction` (**0=forward, 1=reverse, 2=bidirectional**), `hidden_size`, `int8_scale_term` и, при `NCNN_INT8`, `weight_hc_data_int8_scales` / `weight_xc_data_int8_scales`. Реализация — [`src/layer/lstm.cpp`](https://github.com/Tencent/ncnn/blob/master/src/layer/lstm.cpp) (BSD-3-Clause, Copyright 2017 Tencent), читает `direction = pd.get(2, 0)` и `num_directions = direction == 2 ? 2 : 1`. Есть и слой `RNN` ([`src/layer/rnn.cpp`](https://github.com/Tencent/ncnn/blob/master/src/layer/rnn.cpp)).
* Конвертер pnnx умеет наш слой напрямую: в таблице поддержки операций `nn.LSTM` помечен как «Is Supported ✔ / Export to ncnn ✔», а ONNX-оператор `LSTM` — «✔ / ✔, with post squeeze/transpose+reshape» ([tools/pnnx/README.md](https://github.com/Tencent/ncnn/blob/master/tools/pnnx/README.md)).
* Значит путь `PyTorch CRNN → pnnx → ncnn (.param + .bin) → один .exe` **покрывает нашу архитектуру целиком**: 4 свёртки, пулы, 2-слойный BiLSTM, линейный классификатор — без единой строки ручного кода рантайма.

Практическое следствие: ncnn (BSD-3, без зависимостей, один .exe + два файла модели) — это **самая близкая к «llama.cpp для капчи» готовая конструкция**, которую можно получить сегодня. Платформа: Windows x64 есть в списке готовых сборок VS2015…VS2026, Linux/Android/iOS/WASM — тоже ([README, раздел Download & Build status](https://github.com/Tencent/ncnn/blob/master/README.md)).

---

## 4. Экспорт CRNN в ONNX

### 4.1 Чем экспортировать

PyTorch ≥ 2.6/2.9 по умолчанию использует **dynamo-экспортёр на базе `torch.export`** ([docs/source/onnx_export.md](https://github.com/pytorch/pytorch/blob/main/docs/source/onnx_export.md)): граф нормализуется в функциональный ATen, убирается Python-control-flow, фиксируются ограничения по форме; результат — объект `torch.onnx.ONNXProgram` с `.model_proto` и методом `.save()`. Зависимости экспортёра: `onnx` и `onnxscript` (`pip install --upgrade onnx onnxscript`).

У нас `onnx 1.23.2` и `onnxscript 0.7.2` уже стоят в `.venv-gpu` — то есть экспорт возможен немедленно, без установок.

### 4.2 Особенности нашей модели при экспорте

1. **Два выхода.** `CRNN.forward` возвращает `(logits, w)`, где `w` — число тайм-шагов ([`../../train/captcha_crnn.py:362-373`](../../train/captcha_crnn.py)). Для экспорта нужен один выход: обернуть в модуль, возвращающий только `logits`.
2. **Высота фиксирована, ширина — нет.** Модель жёстко проверяет, что `H/8 == rows == 32//8 == 4` ([`captcha_crnn.py:366-369`](../../train/captcha_crnn.py)), поэтому вход — `(B, 1, 32, W)` с динамическим `W`. Экспортировать надо с `dynamic_axes`/`dynamic_shapes` по оси W (и, при желании, по батчу).
3. **BatchNorm.** Перед экспортом обязательно `model.eval()` — иначе в графе останется training-режим BN. Дополнительно ORT умеет сливать Conv+BN при препроцессинге ([docs квантизации](https://onnxruntime.ai/docs/performance/model-optimizations/quantization.html): «A Convolution operator followed by BatchNormalization can be fused into one during the optimization»), а препроцессинг это отдельный шаг `quant_pre_process()`, который рекомендуют делать **до** квантизации.
4. **LSTM.** ONNX-оператор `LSTM` имеет атрибуты `activations`, `clip`, `direction` (forward/reverse/bidirectional), `hidden_size`, `input_size`, `layout`, `peephole`, `triplet` — и **атрибута `num_layers` у него нет** (проверено: 0 вхождений на [странице оператора](https://onnx.ai/onnx/operators/onnx__LSTM.html)). Значит наш 2-слойный `nn.LSTM(num_layers=2, bidirectional=True)` должен выгрузиться как **две цепочки LSTM-узлов** (каждая bidirectional). Это ожидание — проверить на реальном экспорте (см. §10).
5. **Вход/выход LSTM.** ONNX-LSTM ждёт X в раскладке `[seq_length, batch, input]`; у нас `batch_first=True`, поэтому экспорт вставит транспонирование — это нормально, но лишние копии стоит проверить в профиле.

Минимальный скрипт (мы его **не запускали** — обучение и экспорт в этой сессии не выполнялись; код дан как следующий шаг):

```python
# export_onnx.py  (в train/, файла в репозитории пока нет)
import torch
from train.captcha_crnn import CRNN, CHARSET

class CRNNOnnx(torch.nn.Module):
    def __init__(self, base):
        super().__init__()
        self.base = base
    def forward(self, x):            # только логиты, без числа шагов
        logits, _ = self.base(x)
        return logits

m = CRNN(num_classes=len(CHARSET) + 1).eval()
m.load_state_dict(torch.load("best.pt", map_location="cpu"))
torch.onnx.export(
    CRNNOnnx(m),
    (torch.zeros(1, 1, 32, 128),),
    "captha_crnn.onnx",
    input_names=["image"], output_names=["logits"],
    dynamic_shapes={"image": {0: "batch", 3: "width"}, "logits": {0: "batch", 1: "time"}},
    opset_version=17,               # opset >= 10 обязателен для квантизации
)
```

### 4.3 Что даёт ONNX по сравнению с GGUF

Формат ONNX — это **граф + веса**, а GGUF — **только веса + метаданные** (граф в GGUF по спецификации — «future extension»). Для CRNN с CTC-головой и BiLSTM ONNX существенно практичнее: не нужно вручную описывать граф и не нужно писать самому рекуррентный слой.

---

## 5. Квантизация int8: dynamic vs static

Источник: [Quantize ONNX models](https://onnxruntime.ai/docs/performance/model-optimizations/quantization.html) (официальный док).

### 5.1 Что говорит документация

* **Формат представления:** QOperator (QLinearConv, MatMulInteger…) либо QDQ (QuantizeLinear/DeQuantizeLinear). По умолчанию для статической квантизации — **S8S8 + QDQ**.
* **Dynamic**: scale/zero-point активаций считаются на лету, «These calculations increase the cost of inference, while usually achieve higher accuracy». API — `quantize_dynamic()`.
* **Static**: параметры активаций считаются офлайн по калибровочной выборке; методы калибровки — **MinMax, Entropy, Percentile**; API — `quantize_static()`.
* **Правило выбора метода, дословно:** «In general, it is recommended to use **dynamic quantization for RNNs** and transformer-based models, and **static quantization for CNN models**». Наша модель — гибрид: CNN-часть статикой, RNN-часть динамикой.
* **Ограничения:** квантовать можно модели с opset ≥ 10; на CPU работают U8U8, U8S8, S8S8; «**S8S8 with QOperator will be slow on x86-64 CPUs and should be avoided** in general»; на x86-64 с AVX2/AVX512 ORT использует `VPMADDUBSW` для U8S8, и он может переполняться — отсюда рекомендация `reduce_range` или U8U8; на x64 с **VNNI** и на Arm с dot-product переполнения нет.
* **GPU:** «You need a device that supports Tensor Core int8 computation, like T4 or A100. Older hardware will not benefit from quantization»; на GPU поддерживается только S8S8.
* **FP16 как альтернатива:** «Tuning data is not needed for float16 conversion, which can make it preferable to quantization»; конвертация — `onnxconverter_common.float16.convert_float_to_float16` ([float16.md](https://github.com/microsoft/onnxruntime/gh-pages/docs/performance/model-optimizations/float16.md)). При этом CPU-версия ORT **не поддерживает float16-операции** для инструмента mixed precision (сам инструмент требует GPU) — то есть FP16 на нашем CPU бесполезен.

### 5.2 Что происходит с нашим BiLSTM

* В реестре квантизаторов ORT операция `LSTM` присутствует **только** в `IntegerOpsRegistry` (то есть только для статической квантизации), рядом с `ConvInteger`, `MatMulInteger`, `AttentionQuant` ([registry.py](https://github.com/microsoft/onnxruntime/blob/main/onnxruntime/python/tools/quantization/registry.py)).
* Квантизатор `LSTMQuant` квантует W и R в int8 **per-channel**, перекладывает их в раскладку ONNX (транспонирование осей) и подменяет узел `LSTM` на contrib-операцию **`DynamicQuantizeLSTM`** домена `com.microsoft` ([operators/lstm.py](https://github.com/microsoft/onnxruntime/blob/main/onnxruntime/python/tools/quantization/operators/lstm.py)).
* При этом в таблице поддержки ядер ORT оператор `LSTM` имеет типы `T = tensor(double), tensor(float)` (opset 7+) и `tensor(float), tensor(float16)` (opset 14+) — **int8-LSTM в стандарте ONNX не существует** ([docs/OperatorKernels.md](https://github.com/microsoft/onnxruntime/blob/main/docs/OperatorKernels.md)).

**Практический вывод:** int8 для CRNN = int8-свёртки (статическая калибровка по нашим картинкам) + LSTM либо во float32, либо через `DynamicQuantizeLSTM` (contrib-операция, работает только в ORT — переносимость в ncnn/MNN теряется). Если нужна максимальная переносимость формата, LSTM оставляем float32.

### 5.3 Ожидание для нашего железа

* CPU: Broadwell = AVX2 **без VNNI** → int8-ускорение на CPU не гарантировано: ORT прямо предупреждает про насыщение `VPMADDUBSW` на AVX2/AVX512 без VNNI и советует `reduce_range`/U8U8.
* GPU: GTX 1080 Ti = Pascal (sm_61), int8 tensor cores появились с Turing → по документации ORT «Older hardware will not benefit from quantization» в части int8 на GPU.

**Вывод:** int8 в нашем случае — это не про скорость, а про размер (18.5 МБ → ~5 МБ) и про «как у всех». Реальный выигрыш, если он есть, надо измерить на наших картинках: пользовательские отчёты в треке ORT противоречивы — в одном случае «2x–10x faster inference depending on the model» ([issue #14439](https://github.com/microsoft/onnxruntime/issues/14439)), в другом int8-модель оказалась **медленнее** fp32 на CPU ([issue #20052](https://github.com/microsoft/onnxruntime/issues/20052)).

---

## 6. «Одна папка с файлами и без Python» — как это получается

Три реалистичных варианта:

### Вариант A. ONNX Runtime + своя модель (рекомендуется)

Папка релиза:

```
captha-solver/
├── captha.exe            # наш C++-клиент: C API ORT + декодер CTC + препроцесс
├── onnxruntime.dll       # из zip-ассета релиза ORT
├── onnxruntime_providers_cuda.dll   # (опционально, для GPU)
├── captha_crnn_int8.onnx # наши веса
├── charset.txt           # 63 символа + blank (или метаданные внутри модели)
└── README.md
```

Факты: ORT MIT; C++ API — тонкая обёртка над C API ([with-cpp](https://onnxruntime.ai/docs/get-started/with-cpp.html)); «.zip and .tgz files are also included as assets in each Github release»; есть минимальные сборки и ORT-формат модели для уменьшения бинаря ([ort-format-models.md](https://github.com/microsoft/onnxruntime/gh-pages/docs/performance/model-optimizations/ort-format-models.md), `session.use_ort_model_bytes_directly`). Никакого Python в рантайме: Python нужен только **один раз** при сборке модели (экспорт + квантизация).

### Вариант B. ncnn + своя модель

`.param` + `.bin`, один `.exe`, **ноль зависимостей**, BSD-3-Clause, и — в отличие от ggml — **в ncnn есть слой LSTM с направлением `bidirectional` и int8-веткой** ([`src/layer/lstm.h`](https://github.com/Tencent/ncnn/blob/master/src/layer/lstm.h)), а pnnx экспортирует `nn.LSTM` из PyTorch напрямую ([tools/pnnx/README.md](https://github.com/Tencent/ncnn/blob/master/tools/pnnx/README.md)). То есть нашу архитектуру он берёт «из коробки».

Что остаётся сделать: препроцессинг (crop по `roi`, вычисление высоты глифа, ресайз, нормализация) и CTC-декодер — обе задачи решаются в C++ на 100–200 строк, а препроцесс можно вынести в наш же существующий Python только на этапе подготовки. Квантизация int8 — штатными тулами ncnn (ncnnoptimize/ncnn2table/ncnn2int8, описан в [wiki](https://github.com/Tencent/ncnn/wiki/quantized-int8-inference)).

Оговорка: pnnx — Python-тул (запускается один раз при подготовке модели), сам рантайм — чистый C++ без Python.

### Вариант C. Свой рантайм на ggml (это и есть «captcha.cpp»)

Что придётся написать: собственный конвертер PyTorch→GGUF (простой), собственный препроцессинг (crop/нормализация/ресайз), **собственный BiLSTM** (в ggml нет такой операции), декодер CTC, CLI. Плюс решение проблемы переменной ширины (статический граф → бакеризация ширины: 64/96/128/160/224/320/400 → 7 корзин, либо всегда максимум).

Смета: это отдельный проект размером с `llama.cpp` в минимуме (там только экспортёры + сервер + веб-UI, а архитектура одна и фиксированная).

### Вариант D (гибрид). ggml только как библиотека, но LSTM через распаковку в ONNX

Не имеет смысла: если в проекте уже есть ONNX-рантайм, второй рантайм не нужен.

**Про «формат GGUF для капчи» отдельно.** Если владелец всё же хочет именно формат llama.cpp (однофайловая модель с метаданными), это реализуемо: GGUF — открытый формат ([спецификация](https://github.com/ggml-org/ggml/blob/master/docs/gguf.md)), и в него кладутся наши тензоры (FP32/FP16/Q8_0) + метаданные (charset, высота глифа, нормализация, лицензия). Но **исполнять** это можно только своим кодом; готового исполнителя для CRNN в формате GGUF не существует.

---

## 7. Свой C++-рантайм с готовыми весами vs готовый рантайм со своими весами

| Критерий | Свой runtime (ggml/GGUF) | ONNX Runtime + наши веса | ncnn + наши веса |
|---|---|---|---|
| Время до первого работающего инференса | дни–недели (написать BiLSTM, конвертер, препроцесс, декодер, тесты) | **часы** (экспорт + `quantize_static` + ~100 строк C++) | **часы–дни** (pnnx + ~150 строк C++ на препроцесс/декодер) |
| Число поддерживаемых операций | ровно те, что мы напишем | вся онnx-операторная база + все EP | фиксированный, но достаточный набор: Conv/Pool/InnerProduct/**LSTM (bidirectional, int8)** |
| Переносимость формата | только наш код | ONNX — де-факто стандарт: ncnn, MNN, TFLite, OpenVINO, Paddle Lite, TensorRT умеют его читать | `.param`/`.bin` — только ncnn |
| Квантизация int8 | своя (ggml Q8_0/Q4_0 — блочные, для GEMM; для свёрток и int8-активаций ничего готового нет) | готовая: static/dynamic, QOperator/QDQ, калибровка MinMax/Entropy/Percentile ([docs](https://onnxruntime.ai/docs/performance/model-optimizations/quantization.html)) | штатные тулы ncnn (ncnnoptimize/ncnn2table/ncnn2int8), int8-ветка в слое LSTM |
| Динамическая ширина входа | проблема (статический граф ggml) | штатный случай (динамические оси в ONNX) | штатный случай (ncnn Mat — динамический размер) |
| Лицензия | MIT (ggml) | MIT (ORT) + наш код под MIT | BSD-3 (ncnn) + наш код под MIT |
| Скорость | потенциально выше теоретически, но нет LSTM-ядра → писать самому | MLAS/CUDA-ядра, ручная оптимизация x86 | SIMD-ядра ncnn, слой LSTM с int8 |
| Размер дистрибутива | маленький (один .exe + .gguf) | больше (DLL ORT — десятки МБ), но есть минимальные сборки и ORT-формат | **маленький**: один .exe + `.param` + `.bin`, без зависимостей |
| Риск | весь риск на нас: баги в LSTM = тихая деградация точности | риск минимален | риск мал: чужой, но простой слой LSTM; главное — сверить выходы с torch |
| Что это даёт точности модели | **0** | **0** | **0** |

Ключевой тезис: **выбор рантайма не влияет на точность распознавания**. Измеренная проблема проекта — обобщение на невиданные типы (type-held-out = 0.000 при 1.000 на обученных) — это проблема данных и валидации, а не рантайма. Доказательство из наших же замеров: чужие ONNX-модели, запущенные через ORT, дали acc 0.0 / CER ≈ 0.99–1.01 (`../bench_results_onnx.json`) — рантайм был исправен, модели были негодны.

---

## 8. Измеренные цифры (сводка)

### 8.1 Локальные измерения CaptchaOCR (torch, CPU)

| Что | Результат | Где |
|---|---|---|
| Инференс CRNN 32×128 | 70.9 мс/кадр = **451 img/s** | `../MODEL_PLAN.md:106` |
| Инференс CRNN 32×160 / 48×192 / 64×256 | 368 / 203 / 104 img/s | `../MODEL_PLAN.md:107-109` |
| Инференс CRNN 5.28 M | 371 img/s | `../../docs/adr/0002-recogniser-architecture-and-data.md:1081` |
| Обучение | 99 img/s CPU, **920 img/s** GPU | `../MODEL_PLAN.md:92` |
| EasyOCR (чужая база) | **388 мс/кадр** | `../MODEL_PLAN.md:364` |
| ONNX-капчи (captCHAD fp32/int8, phpwind) | acc 0.0, CER 0.9865–1.0115 | `../bench_results_onnx.json` |

### 8.2 Внешние измерения

| Источник | Цифра | Ссылка |
|---|---|---|
| llama.cpp, Llama-3.1-8B | Q4_K_M: 4.8944 bit/weight, 4.58 GiB, prompt 821.81 t/s, gen 71.93 t/s; Q8_0: 8.5008 bit/w, 7.95 GiB, prompt 865.09, gen 50.93; F16: 16.0005 bit/w, 14.96 GiB, prompt 923.49, gen 29.17 | [tools/quantize/README.md](https://github.com/ggml-org/llama.cpp/blob/master/tools/quantize/README.md) |
| ONNX Runtime, пользовательские замеры | «2x–10x faster inference depending on the model» | [issue #14439](https://github.com/microsoft/onnxruntime/issues/14439) |
| ONNX Runtime, пользовательские замеры | int8 **медленнее** fp32 на CPU для простого CNN | [issue #20052](https://github.com/microsoft/onnxruntime/issues/20052) |
| MNN | FP16/Int8 «can reduce model size 50%-70%»; x86 AVX512 — int8 уровня S, ARMv8 с sdot — «2.5 faster» | [README MNN](https://github.com/alibaba/MNN) |
| ncnn (агрегированная сводка, не первоисточник) | int8: ~4× уменьшение размера, 2–3× ускорение на поддерживаемых платформах | [DeepWiki: ncnn INT8](https://deepwiki.com/Tencent/ncnn/4.4-int8-quantization-and-inference) |
| RapidOCR (заявление проекта) | onnxruntime-движок в 4–5× быстрее движка на PaddlePaddle | [README RapidOCR](https://github.com/RapidAI/RapidOCR) |

Числа из DeepWiki и README RapidOCR — вторичные/заявленные самими авторами, не независимые измерения; воспроизвести их здесь я не мог.

---

## 9. Что это значит для CaptchaOCR

1. **«Свой runtime» — не та работа, которая сейчас нужна.** Мы измерили: наш CRNN даёт 451 img/s на CPU (70.9 мс/кадр), а чужие базы — 388 мс/кадр (EasyOCR). Солверу нужна ~1 капча за несколько секунд. Узкое место проекта — обобщение на невиданные типы (0.000 при type-held-out), а это данные и протокол валидации. Рантайм на точность не влияет **0**; на скорость — тоже (запас ×100).
2. **Формат поставки «как у llama.cpp» берётся готовым, и теперь у нас два кандидата.** (а) **ONNX Runtime (MIT) + наш C++-клиент** — «одна папка, ноль Python, один файл модели» без месяцев работы; прецедент того же класса: RapidOCR (Apache-2.0) — PaddleOCR-модели → ONNX → рантаймы на C++/Java/C#/Python. (б) **ncnn (BSD-3, без зависимостей) + pnnx** — это ближе всего к «llama.cpp для капчи»: один `.exe` + `.param` + `.bin`, и в ncnn **есть слой LSTM с `direction=bidirectional` и int8-веткой**, а pnnx экспортирует `nn.LSTM` из PyTorch напрямую ([`src/layer/lstm.h`](https://github.com/Tencent/ncnn/blob/master/src/layer/lstm.h), [tools/pnnx/README.md](https://github.com/Tencent/ncnn/blob/master/tools/pnnx/README.md)). Планируя релиз на Hugging Face, кладём туда `.onnx` (+ при желании `.ort`) и, если пойдём по ncnn, — `.param`/`.bin`.
3. **Если «формат llama.cpp» всё же хочется — это отдельная необязательная задача, и вот почему она дорогая.** В ggml нет операции LSTM (0 вхождений в `docs/ops.md`), а наша модель — CNN + 2-слойный BiLSTM. Значит: писать BiLSTM руками, решать проблему статического графа при переменной ширине (T = W/4 от 16 до 100 → бакеризация), писать свой препроцесс и декодер. Оценка: работа на несколько недель с нулевым влиянием на точность. Практичный промежуточный шаг, если хочется «ggml-ощущения» без своего рантайма: **взять ncnn** — это тот же «один .exe + файлы модели, без Python, без зависимостей», но с готовым слоем LSTM; либо сделать собственный однофайловый формат поверх готовой ONNX-структуры (файл с метаданными + ссылкой на граф) — дешевле и переносимее.
4. **Железо диктует режим, а не наоборот.** CPU — Broadwell без VNNI → int8 на CPU может и не ускорить (ORT предупреждает про насыщение `VPMADDUBSW` и рекомендует `reduce_range`/U8U8). GPU — Pascal sm_61 → int8 tensor cores недоступны, а **CUDA 13 вообще выбросила Pascal**: ORT ≥1.27 GPU-пакеты собраны на CUDA 13.0 по умолчанию, значит для 1080 Ti нужен пакет на CUDA 12.x (ORT ≤1.26) либо CPU EP. Практический вывод: **считать CPU-инференс основным режимом**, GPU — как опцию для тренировки и для FP32-ускорения (в `.venv-gpu` уже стоит `torch 2.14.1+cu126` под sm_61).
5. **Что делать на практике (следующие шаги, ни одно из них здесь не выполнялось):** (а) экспортировать чекпоинт в ONNX и убедиться, что logits ONNX совпадают с torch (max abs diff < 1e-4); (б) снять `quantize_static` (S8S8 + QDQ) с калибровкой по 200–500 нашим картинкам, сравнить CER fp32 vs int8 и замерить скорость на CPU; (в) написать ~100-строчный C++-клиент на C API ORT с препроцессом из `CaptchaDataset._load/_line_height` и CTC-декодером — это и есть «одна папка без Python»; (г) **параллельно проверить альтернативу**: `pnnx` → ncnn (`.param`/`.bin`) и сравнить выходы ncnn-LSTM с torch-LSTM (если совпадут — можно отдавать релиз в ncnn, это ближе всего к «llama.cpp для капчи»); (д) опубликовать на HF: `.onnx` (+ optionally `.ort` и/или `.param`/`.bin`) + `charset.txt` + пример запуска.

---

## 10. Чего не нашёл / не проверил

**Не нашёл (искал именно это):**

* **Ни одной публичной измеренной таблицы скорости для связки «CRNN+CTC → ONNX → ORT int8» на CPU.** Искал: `onnxruntime int8 quantization speedup measured`, `CRNN C++ inference captcha onnxruntime`, `ocr.cpp llama.cpp`, `ggml lstm`, `rapidocr onnxruntime C++ deploy`. Что нашлось — только пользовательские отчёты в треке ORT ([#14439](https://github.com/microsoft/onnxruntime/issues/14439), [#20052](https://github.com/microsoft/onnxruntime/issues/20052)) и заявления самих проектов. **Первое, что стоит сделать, — измерить у себя**: fp32/int8 × CPU/GPU на наших 4600 картинках.
* **Официальных измерений int8 для ncnn/MNN/Paddle Lite/RKNN** в первоисточниках не нашёл: цифра «4× размер, 2–3× скорость» для ncnn есть только в агрегированной вики-статье [DeepWiki](https://deepwiki.com/Tencent/ncnn/4.4-int8-quantization-and-inference), а не в документации Tencent. Для MNN официальная отсылка — OSDI'22 paper ([USENIX](https://www.usenix.org/conference/osdi22/presentation/lv)), но на странице публикации числовых результатов нет (только аннотация); PDF не разбирал.
* **Не нашёл готового «llama.cpp для OCR/капч»** — то есть проекта, который делает ровно то, что описано в задаче (свой формат + свой рантайм для маленькой сети). Ближайшие аналоги: ggmlR (R-обёртка ggml с развёрнутым LSTM, [rdrr.io](https://rdrr.io/cran/ggmlR/man/ggml_layer_lstm.html)), RapidOCR (чужие модели + готовый рантайм), MNN-LLM и ncnn_llm (llm-подобные рантаймы на MNN/ncnn). Поиск вёлся по: `ocr.cpp`, `ggml lstm`, `CRNN C++ inference captcha onnxruntime`, `rapidocr onnxruntime C++ deploy`.
* **Не нашёл измерений CPU-инференса ONNX Runtime для CRNN-подобной сети** — тоже нет.
* **Не нашёл информации о том, поддерживает ли nn.LSTM с `num_layers=2` экспорт в ONNX ровно двумя chained-LSTM-узлами.** Факт «у ONNX-оператора LSTM нет атрибута `num_layers`» проверен по [странице оператора](https://onnx.ai/onnx/operators/onnx__LSTM.html) (0 вхождений), но сам экспорт на нашей модели я не запускал.

**Не проверил (технически было можно, но не сделал):**

* **Не запускал** экспорт CRNN→ONNX, квантизацию int8 и не собирал C++-клиент: задача направления — исследование, а обучение/экспорт в этой сессии запрещены. Все примеры кода в §4.2 и §9 — это предложения, а не выполненные действия.
* **Не проверил фактический состав prebuilt-пакета ONNX Runtime для Windows** (размер `onnxruntime.dll`, наличие headers/lib в zip-ассете) — размеры в отчёте не привожу, чтобы не выдумывать цифры.
* **Не проверил, содержит ли официальная сборка `onnxruntime-gpu` для CUDA 12.x SASS для sm_61.** Вывод «нужен пакет ≤1.26, собранный под CUDA 12.x» следует из [release notes CUDA 13](https://docs.nvidia.com/cuda/cuda-toolkit-release-notes/index.html) и таблицы версий CUDA в [CUDA EP ORT](https://github.com/microsoft/onnxruntime/gh-pages/docs/execution-providers/CUDA-ExecutionProvider.md), но конкретные `CUDA_ARCHITECTURES` в сборке я не смотрел.
* **Не проверил, поддерживает ли `DynamicQuantizeLSTM` (contrib-операция ORT) CUDA EP** — по коду видно, что это contrib-операция ORT, но матрица EP-поддержки contrib-операций не изучалась.
* **Не читал** PDF статей MNN (OSDI'22) и arXiv-препринт «Which Quantization Should I Use? A Unified Evaluation of llama.cpp Quantization» ([arXiv:2601.14277](https://arxiv.org/html/2601.14277v1)) — только заголовок/сниппет из поиска; числа оттуда в отчёт не переносил.
* **Не изучал** TFLite/LiteRT-спецификацию квантизации подробно (только наличие C++ API, микроконтроллерной поддержки и общий Apache-2.0) — [документация LiteRT](https://developers.google.com/edge/litert).
* **Не проверял** лицензию и ограничения NVIDIA TensorRT под нашу задачу (это EULA, а не OSS; подробно не разбирал).
* **Не проверял, что pnnx корректно конвертирует наш 2-слойный BiLSTM (`num_layers=2`, `bidirectional=True`) в слой ncnn.** Поддержка `nn.LSTM` заявлена в [tools/pnnx/README.md](https://github.com/Tencent/ncnn/blob/master/tools/pnnx/README.md), а в слое ncnn есть `direction=2` (bidirectional) ([`src/layer/lstm.cpp`](https://github.com/Tencent/ncnn/blob/master/src/layer/lstm.cpp)), но совпадение выходов ncnn-LSTM с torch-LSTM я не измерял — это первый обязательный тест, если пойдём по ncnn. **Промежуточная поправка к собственному черновику:** сначала я записал, что «в ncnn нет LSTM»; проверка исходников это опровергла, в отчёт вошла исправленная версия.
* **Не измерял** ни скорость ncnn, ни скорость ORT на нашей модели — обе цифры надо снять самим.

---

### Приложение: ссылки, использованные в отчёте

* llama.cpp: [README](https://github.com/ggml-org/llama.cpp/blob/master/README.md) · [tools/quantize/README.md](https://github.com/ggml-org/llama.cpp/blob/master/tools/quantize/README.md) · [docs/ops.md](https://github.com/ggml-org/llama.cpp/blob/master/docs/ops.md)
* ggml: [README](https://github.com/ggml-org/ggml) · [docs/gguf.md](https://github.com/ggml-org/ggml/blob/master/docs/gguf.md)
* ONNX Runtime: [LICENSE](https://github.com/microsoft/onnxruntime/blob/main/LICENSE) · [get-started C++](https://onnxruntime.ai/docs/get-started/with-cpp.html) · [quantization](https://onnxruntime.ai/docs/performance/model-optimizations/quantization.html) · [float16](https://github.com/microsoft/onnxruntime/gh-pages/docs/performance/model-optimizations/float16.md) · [CUDA EP](https://github.com/microsoft/onnxruntime/gh-pages/docs/execution-providers/CUDA-ExecutionProvider.md) · [OperatorKernels.md](https://github.com/microsoft/onnxruntime/blob/main/docs/OperatorKernels.md) · [ort-format-models.md](https://github.com/microsoft/onnxruntime/gh-pages/docs/performance/model-optimizations/ort-format-models.md) · [registry.py](https://github.com/microsoft/onnxruntime/blob/main/onnxruntime/python/tools/quantization/registry.py) · [operators/lstm.py](https://github.com/microsoft/onnxruntime/blob/main/onnxruntime/python/tools/quantization/operators/lstm.py) · [issues #14439](https://github.com/microsoft/onnxruntime/issues/14439), [#20052](https://github.com/microsoft/onnxruntime/issues/20052)
* PyTorch: [docs/source/onnx_export.md](https://github.com/pytorch/pytorch/blob/main/docs/source/onnx_export.md)
* ONNX: [оператор LSTM](https://onnx.ai/onnx/operators/onnx__LSTM.html)
* ncnn: [README](https://github.com/Tencent/ncnn) · [wiki: quantized int8 inference](https://github.com/Tencent/ncnn/wiki/quantized-int8-inference) · [src/layer/lstm.h](https://github.com/Tencent/ncnn/blob/master/src/layer/lstm.h) · [src/layer/lstm.cpp](https://github.com/Tencent/ncnn/blob/master/src/layer/lstm.cpp) · [tools/pnnx/README.md](https://github.com/Tencent/ncnn/blob/master/tools/pnnx/README.md)
* MNN: [README](https://github.com/alibaba/MNN) · [OSDI'22 (USENIX)](https://www.usenix.org/conference/osdi22/presentation/lv)
* LiteRT: [developers.google.com/edge/litert](https://developers.google.com/edge/litert) · [TensorFlow LICENSE](https://github.com/tensorflow/tensorflow/blob/master/LICENSE)
* OpenVINO: [README](https://github.com/openvinotoolkit/openvino)
* Paddle Lite: [README](https://github.com/PaddlePaddle/Paddle-Lite)
* RKNN-Toolkit2: [README](https://github.com/rockchip-linux/rknn-toolkit2) · [LICENSE](https://github.com/rockchip-linux/rknn-toolkit2/blob/master/LICENSE)
* RapidOCR: [README](https://github.com/RapidAI/RapidOCR) · [cpp](https://github.com/RapidAI/RapidOCR/tree/main/cpp)
* ggmlR: [rdrr.io/cran/ggmlR](https://rdrr.io/cran/ggmlR/man/ggml_layer_lstm.html)
* NVIDIA: [CUDA Toolkit release notes](https://docs.nvidia.com/cuda/cuda-toolkit-release-notes/index.html)
