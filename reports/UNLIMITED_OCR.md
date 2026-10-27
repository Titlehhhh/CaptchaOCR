# UNLIMITED OCR 2 — что можно взять для CaptchaOCR

- **Дата:** 2026-10-27 · **Роль:** research+reuse-analysis (субагент), scratch — `build/unlimited_ocr/**`
- **Апстрим:** `github.com/baidu/Unlimited-OCR` (MIT), веса `baidu/Unlimited-OCR-2` на Hugging Face (MIT),
  статья arXiv **2606.23050** («Unlimited OCR Works», CC BY 4.0)
- **Машина:** Windows, GTX 1080 Ti (11.81 GB, sm_61), `.venv-gpu` = torch 2.14.1+cu126, transformers 5.19.0
- **Что НЕ делалось:** веса не скачивались (6.23 GiB > лимита 2 GB), ничего не устанавливалось,
  ни один файл вне `reports/UNLIMITED_OCR.md` и `build/unlimited_ocr/**` не менялся

---

## 0. Короткий ответ (TL;DR)

| вопрос | ответ |
|---|---|
| Что это | 3.34-параметровый VLM-декодер (DeepSeek-V2-подобный MoE, 12 слоёв) + **визуальный энкодер «SAM ViT-B + CLIP-L»**; SR-SWA вместо полного внимания. Код — **MIT**, веса — **MIT** |
| Пойдёт ли на 11.8 GB | **Нет.** Веса одни занимают **6.23 GiB** (53 % карты) до любых активаций; Triton на Windows нет (а DASH-внимание на нём построено); `einops`/`addict` не установлены; transformers нужен 4.52.1, стоит 5.19.0 |
| SAM в их коде — это детектор? | **Нет.** SAM ViT-B — это **энкодер картинки** (95.6 M параметров, 179 тензоров в весах, подключён обязательно). Прямоугольники выдаёт **сам LLM** в тексте: `<BLOCK>label[x1,y1,x2,y2]`, координаты нормализованы к 0..999 |
| Есть ли в репозитории детектор | **Нет.** Ни одного модуля, выдающего боксы. Единственная «нарезка» — входная: `dynamic_preprocess`, фиксированная сетка 640×640 по aspect ratio |
| Что даёт «gundam» на кадре 128×128 | **Ничего.** Код: если обе стороны ≤ 640 px, тайлов нет вообще (`ratio = (1,1)`), остаётся один глобальный вид 1024×1024 = **273 токена**. Для 458×343 — то же самое |
| Что реально стоит взять | (1) идея «покажи распознавателю несколько масштабов кадра, выбери самый уверенный» — это и есть gundam в нашем масштабе; (2) дисциплина «сырой выход → структурированные блоки → рендер»; (3) **идея сквозного детектора** (модель сама выдаёт бокс ответа) — но это требует обучения |
| Самый дешёвый следующий эксперимент | **Уже выполнен** (§2.6): полосы-кандидаты k=3,4 поверх нынешнего кроппера → **0.4952 → 0.5429** (+4.8 п.п.) на 105 сэмплах, скриншоты владельца **6/6 не сломались**, но 6 сэмплов испортились |

---

## 1. Файлы, созданные

Ровно два места (по брифу):

| путь | что |
|---|---|
| `reports/UNLIMITED_OCR.md` | этот отчёт (новый файл) |
| `build/unlimited_ocr/**` | scratch: зеркало апстрима, пробы, лог эксперимента |

Содержимое scratch:

```
build/unlimited_ocr/
  _fetch.py                 скрипт зеркалирования GitHub + HF (кода, без весов)
  _probe.py                 проба: дерево HF, заголовок safetensors, bf16 на этой GPU
  _probe2.py                проба: компонентные размеры (оба шарда) + попытка прочитать PDF
  _tilegrid_probe.py        ЭКСПЕРИМЕНТ: полосы-кандидаты поверх кроппера
  tilegrid.json             результат эксперимента (измеренный JSON)
  tilegrid.log              лог эксперимента
  api_tags.json             GitHub API: список тегов
  api_git_trees_UnlimitedOCR1.0.json   GitHub API: дерево тега v1
  LICENSE README.md CONTRIBUTING.md .gitattributes .gitignore
  infer.py
  utils/README.md utils/process_unlimitedOCR2.py
  Unlimited-OCR-2.pdf              ← 132 байта, LFS-указатель
  wheel/sglang-0.5.20.dev10+g8d62f5fb9c-py3-none-any.whl  ← 133 байта, LFS-указатель
  hf/  (16 файлов из baidu/Unlimited-OCR-2: config.json, modeling_unlimitedocr.py,
        deepencoder.py, modeling_deepseekv2.py, configuration_deepseek_v2.py,
        dash_attention.py, packing_patch.py, _sparse_base_impl.py,
        sparse_gather_triton.py, sparse_gather_e2e_triton.py, conversation.py,
        generation_config.json, tokenizer_config.json, special_tokens_map.json,
        model.safetensors.index.json, README.md)
  v1/  (README.md, LICENSE, infer.py из тега UnlimitedOCR1.0)
```

Ничего больше не создавалось и не менялось: `webapp/**`, `train/**`, `dataset/**`, `docs/**`, `tools/**`,
`reports/**` (кроме этого файла) — только читались. `git add/commit/push` не выполнялись.

---

## 2. Что проверено

### 2.0 Как вообще удалось получить код (клона не было)

`git clone` на этой машине **не работает** — TLS-конфиг сломан:

```
PS> git clone --depth 1 https://github.com/baidu/Unlimited-OCR build\unlimited_ocr
fatal: unable to access 'https://github.com/baidu/Unlimited-OCR/': schannel: AcquireCredentialsHandle failed: SEC_E_NO_CREDENTIALS (0x8009030e)
PS> git -c http.sslBackend=openssl clone ...
fatal: unable to access '...': error adding trust anchors from file: H:/testGG/emudhra-check/curl-ca-bundle.pem
PS> Invoke-WebRequest https://codeload.github.com/baidu/Unlimited-OCR/zip/refs/heads/main
Базовое соединение закрыто: Непредвиденная ошибка при приеме.
```

Причина видна в конфиге:

```
PS> git config --list --show-origin | Select-String 'ssl|ca'
file:C:/Program Files/Git/etc/gitconfig  http.sslbackend=schannel
file:C:/Users/Title/.gitconfig            http.sslcainfo=H:/testGG/emudhra-check/curl-ca-bundle.pem
```

`git` и .NET-WebClient на этой машине не работают, а **Python — работает**:

```
PS> python -c "import urllib.request; r=urllib.request.urlopen('https://raw.githubusercontent.com/baidu/Unlimited-OCR/main/LICENSE'); print(r.status, len(r.read()))"
OK 200 1061
```

Поэтому весь апстрим получен **скриптом `build/unlimited_ocr/_fetch.py`** (обычные HTTP-запросы к
`raw.githubusercontent.com` и `huggingface.co/.../resolve/main/`), а дерево репозитория — через GitHub REST API
(2 запроса, без токена, лимит 60/час не выбит). Вывод скрипта:

```
=== GitHub main ===
LICENSE                                                 200      1061  ok
README.md                                               200     13864  ok
CONTRIBUTING.md                                         200      1529  ok
.gitattributes                                          200       210  ok
.gitignore                                              200       374  ok
infer.py                                                200      9589  ok
utils/README.md                                         200      2236  ok
utils/process_unlimitedOCR2.py                          200     14923  ok
Unlimited-OCR-2.pdf                                     200       132  ok      ← LFS-указатель
wheel/sglang-0.5.20.dev10+g8d62f5fb9c-py3-none-any.whl  200       133  ok      ← LFS-указатель
=== HuggingFace code (no weights) ===
hf/config.json                             200      5525  ok
hf/modeling_unlimitedocr.py                200     55724  ok
hf/deepencoder.py                          200     37939  ok
hf/modeling_deepseekv2.py                  200     25572  ok
hf/configuration_deepseek_v2.py            200     10720  ok
hf/dash_attention.py                       200     71465  ok
hf/packing_patch.py                        200      8110  ok
hf/conversation.py                         200      9253  ok
hf/generation_config.json                   200       111  ok
hf/tokenizer_config.json                   200    166632  ok
hf/special_tokens_map.json                 200       549  ok
hf/model.safetensors.index.json            200    254054  ok
hf/README.md                               200     13073  ok
hf/_sparse_base_impl.py                    200    221755  ok
hf/sparse_gather_triton.py                 200     23860  ok
hf/sparse_gather_e2e_triton.py             200     18058  ok
=== GitHub API: tags + v1 tree (2 requests) ===
api_tags                                200       453  -> api_tags.json
   tags: [{"name": "UnlimitedOCR1.0", ... "commit": {"sha": "92ad94b53a51950fea0416aced42331dfb4dd59e" ...
api_git/trees/UnlimitedOCR1.0?recursive=1               200      2906  -> api_git_trees_UnlimitedOCR1.0.json
   v1 tree (12 entries):
      .gitignore CONTRIBUTING.md LICENSE README.md Unlimited-OCR.pdf
      assets assets/Unlimited-OCR.png assets/baidu.png assets/long-horizon-ocr.gif
      infer.py wheel wheel/sglang-0.0.0.dev11416+g92e8bb79e-py3-none-any.whl
=== v1 raw files (probe) ===
v1/README.md                                            200     11586  ok
v1/LICENSE                                              200      1061  ok
v1/infer.py                                             200     11180  ok
v1/utils/process_unlimitedOCR.py                        404         0  HTTP 404
```

### 2.1 Что это такое (архитектура, из кода — не из README)

**Репозиторий — не код модели.** В `main` лежат только README, LICENSE, `infer.py` (клиент бенчмарка к
SGLang-серверу) и `utils/process_unlimitedOCR2.py` (пост-обработка). Вся модель — в Hugging Face
`baidu/Unlimited-OCR-2` под `trust_remote_code` (`auto_map` → `modeling_unlimitedocr.py`).

Ветки и теги:

```
PS> (api) GET /repos/baidu/Unlimited-OCR/branches
[{"name":"Unlimited-OCR-2","commit":{"sha":"0cdd7877868bd0e17715d742911b9ce937c53d3f"}},
 {"name":"main","commit":{"sha":"0cdd7877868bd0e17715d742911b9ce937c53d3f"}}]
PS> (api) GET /repos/baidu/Unlimited-OCR/tags
[{"name":"UnlimitedOCR1.0", ... "commit":{"sha":"92ad94b53a51950fea0416aced42331dfb4dd59e"}}]
```

**Декодер** (`config.json` → `language_config`): DeepSeek-V2-подобный MoE-LM — 12 слоёв, `hidden_size` 1280,
10 голов, `v_head_dim` 128, **64 routed + 2 shared эксперта, 6 экспертов на токен**, `vocab_size` 129280,
`max_position_embeddings` 131072, yarn-RoPE (`factor 4.0`), `sliding_window_size` 128, MLA выключен
(`use_mla: false`).

**Визуальный энкодер** (`config.json` → `vision_config`): `image_size 1024`, две ветви:
`sam_vit_b` (12 слоёв, width 768, `downsample_channels [512,1024]`) и `clip-l-14-224` (24 слоя, width 1024);
`projector` — линейный 2048 → 1280.

**Сборка фичей** (`hf/modeling_unlimitedocr.py:731-762`) — вот ключевой кусок, он отвечает на вопрос про SAM:

```python
if do_crop:
    n_tiles = width_crop_num * height_crop_num
    patches = patches_all[tile_cursor:tile_cursor + n_tiles]
    local_features_1 = sam_model(patches)              # SAM ViT-B на тайлах
    local_features_2 = vision_model(patches, local_features_1)   # CLIP-L на тех же тайлах
    local_features = torch.cat((local_features_2[:, 1:], local_features_1.flatten(2).permute(0, 2, 1)), dim=-1)
    local_features = self.projector(local_features)

    global_features_1 = sam_model(image_ori_p)         # SAM ViT-B на глобальном виде 1024x1024
    global_features_2 = vision_model(image_ori_p, global_features_1)
    global_features = torch.cat((global_features_2[:, 1:], global_features_1.flatten(2).permute(0, 2, 1)), dim=-1)
    global_features = self.projector(global_features)
    ...
    global_local_features = torch.cat([local_features, global_features, self.view_seperator[None, :]], dim=0)
```

**Внимание: это DeepSeek-OCR-овская схема, а не «SAM-предложение кропов».** SAM используется как
**энкодер изображения** (Segment Anything **ViT-B**, без prompt-энкодера и без mask decoder'а — только
`patch_embed` + `blocks` + `neck`), CLIP-L идёт вторым энкодером, фичи склеиваются и линейно проецируются
в 1280. Никаких масок, промптов и предложений кропов в коде нет.

**«Gundam» = динамическая нарезка входа** (`hf/modeling_unlimitedocr.py:229-267`, 39 строк, чистый Python):

```python
def dynamic_preprocess(image, min_num=2, max_num=16, image_size=640, use_thumbnail=False):
    aspect_ratio = orig_width / orig_height
    target_ratios = set((i, j) for n in range(min_num, max_num + 1) for i in range(1, n+1) for j in range(1, n+1)
                         if i * j <= max_num and i * j >= min_num)
    ...  # выбирает ближайший aspect ratio, ресайзит, режет на квадраты image_size x image_size
```

**Бюджет токенов** (`hf/modeling_unlimitedocr.py:531-580`, `_uocr_build_inputs`):

```python
nq  = math.ceil((image_size // patch_size) / downsample_ratio)   # ceil(640/16/4)  = 10
nqb = math.ceil((base_size  // patch_size) / downsample_ratio)   # ceil(1024/16/4) = 16
...
tok  = [image_token_id] * (nqb * (nqb + 1)) + [image_token_id]   # глобальный вид: 16*17+1 = 273
if w_t > 1 or h_t > 1:
    tok += ([image_token_id] * (nq * w_t + 1)) * (nq * h_t)      # тайлы: (10*w+1)*(10*h)
globals_.append(transform(ImageOps.pad(image, (base_size, base_size), color=pad_color)))  # леттербокс в 1024x1024
```

Считаем: глобальный вид = **273 токена** (совпадает с `config.json: per_page_image_tokens: 273`);
тайлы 2×2 = (10·2+1)·(10·2) = **420** токенов, 2×3 = 620, 3×3 = 960. Итого «gundam»-страница = 273 + 420…960.

**Внимание, «gundam» не включается на маленьких картинках** — тот же `_uocr_build_inputs`:

```python
if image.size[0] <= image_size and image.size[1] <= image_size:
    ratio = (1, 1)          # ← ТАЙЛОВ НЕТ ВООБЩЕ
elif cropping:
    tiles, ratio = dynamic_preprocess(image, min_num=min_crops, max_num=max_crops, image_size=image_size)
```

Для наших кадров (128×128 и 458×343) обе стороны ≤ 640 → `ratio = (1,1)` → **тайлов ноль**, только глобальный
вид 1024×1024 (апскейл 128×128 в 8 раз) = 273 токена. Флаг `crop_mode=True` для наших кадров **ничего
не меняет**.

**Внимание (как выглядит выход)** — модель **не выдаёт markdown**:

```
<PAGE><BLOCK>title<LEVEL1>[x1,y1,x2,y2]<FORK>text ...
<BLOCK>text[x1,y1,x2,y2]<FORK>body ...
<BLOCK>cross_table[bbox]<FORK><table>...</table><PAGE><BLOCK>append_table[bbox]<FORK>...
```

Markdown собирает пост-процессор `utils/process_unlimitedOCR2.py` (379 строк, **только стандартная библиотека**):
сплит по `<PAGE>` (пустые страницы сохраняются, чтобы не съезжала нумерация), `title<LEVELn>` → заголовок,
`image/figure/chart/seal` → `![](pageN_x1_y1_x2_y2.jpg)`, `table/append_table` → HTML со слиянием
кросс-страничных фрагментов и склейкой повторяющихся шапок, `cross_*`/`append_*`/`<MERGE>` — группировка
union-find в порядке чтения, чистка мусорных токенов, одно-корневое дерево заголовков.

**Система координат боксов — нормализованная, а не пиксели** (`hf/modeling_unlimitedocr.py:161-165`):

```python
x1 = int(x1 / 999 * image_width)
y1 = int(y1 / 999 * image_height)
x2 = int(x2 / 999 * image_width)
y2 = int(y2 / 999 * image_height)
```

и `_scale()` в пост-процессоре (`utils/process_unlimitedOCR2.py:73-74`) клампит в 0..1000. То есть **их модель
действительно выдаёт прямоугольники, которые можно превратить в пиксели** (`x_px = x/999·W`) — но это
прямоугольники *текстовых блоков страницы*, а не «строка с ответом».

**Внимание (что это за «детектор»)**: никакого отдельного модуля-детектора нет. Прямоугольники появляются
**в тексте, который декодер генерирует**: `re_match()` (`hf/modeling_unlimitedocr.py:98-113`) ищет
`<|ref|>label<|/ref|><|det|>[x1,y1,x2,y2]<|/det|>`. То есть «bbox» — это токены LLM.

**Внимание (данные обучения)**: в репозитории **нет** ни смеси, ни рецепта, ни скриптов обучения — репозиторий
это только inference. Смесь данных не публиковалась в проверяемых мной источниках (см. §3).

### 2.2 Размеры и лицензии (измерено)

**Код** — `LICENSE` целиком:

```
MIT License

Copyright (c) 2026 Baidu

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

**Веса** — метаданные HF (`GET https://huggingface.co/api/models/baidu/Unlimited-OCR-2`):

```
"tags": [..., "license:mit", ...],
"cardData": {"pipeline_tag":"image-text-to-text","language":["multilingual"],
             "tags":["baidu","vision-language","ocr","custom_code"],"license":"mit",
             "library_name":"transformers"},
"safetensors": {"parameters": {"I64": 257, "BF16": 3343978240}, "total": 3343978497},
"usedStorage": 7102782199
```

→ **MIT и на код, и на веса.** Единственное ограничение MIT — сохранить уведомление об авторских правах.

**Точный размер весов** — из `model.safetensors.index.json` и заголовков обоих шардов (запрошены
**только заголовки** через HTTP `Range: bytes=0-4194303`, 4 МБ, без данных тензоров):

```
PS> GET https://huggingface.co/api/models/baidu/Unlimited-OCR-2/tree/main
   model-00001-of-00002.safetensors           4998430312
   model-00002-of-00002.safetensors           1689875264
   model.safetensors.index.json                  254054
   tokenizer.json                              9980278
   Unlimited-OCR-2.pdf                         1515854
   _sparse_base_impl.py                        221755
   dash_attention.py                            71465
   modeling_unlimitedocr.py                     55724
   deepencoder.py                               37939
   ... (остальные .py — кода, десятки КБ)

index.json metadata: {'total_size': 6687958536}

--- model-00001-of-00002.safetensors (2093 tensors) ---
    LLM decoder (12 MoE layers)      2090 tensors   2333605760 params   4667.2 MB bf16
    embed_tokens                        1 tensor     165478400 params    331.0 MB bf16
    model.image_newline                 1 tensor           1280 params      0.0 MB bf16
    model.view_seperator                1 tensor           1280 params      0.0 MB bf16
    TOTAL                                    2499086720 params
--- model-00002-of-00002.safetensors (726 tensors) ---
    vision_model (CLIP-L)             294 tensors     303177985 params    606.4 MB bf16
    LLM decoder (12 MoE layers)       249 tensors     278042240 params    556.1 MB bf16
    lm_head                              1 tensor     165478400 params    331.0 MB bf16
    sam_model (SAM ViT-B encoder)     179 tensors      95569152 params    191.1 MB bf16
    projector (linear 2048->1280)       2 tensors       2622720 params      5.2 MB bf16
    final norm                           1 tensor           1280 params      0.0 MB bf16
    TOTAL                                     844891777 params
```

Итого: **3 343 978 497 параметров**, **6 687 958 536 байт = 6.23 GiB** в bf16. SAM ViT-B внутри весов —
**95 569 152 параметра (191.1 MB)**, CLIP-L — 303 177 985 (606.4 MB).

### 2.3 Может ли это работать на нашем железе — измерено на нашей карте

```
PS> .venv-gpu\Scripts\python.exe build\unlimited_ocr\_probe.py
torch 2.14.1+cu126 cuda 12.6 avail True
device: NVIDIA GeForce GTX 1080 Ti
compute capability: sm_61
VRAM total 11.81 GB, free 10.70 GB
torch.float16 matmul OK (sample 8629.565)
torch.bfloat16 matmul OK (sample 11598.043)
bf16 conv2d on 1024x1024 OK -> (1, 64, 64, 64)
```

**Первое расхождение с брифом**: «на Pascal нет bf16» — **неверно как утверждение о работоспособности**:
bf16-матмул и bf16-conv на sm_61 **работают** (программная эмуляция, без tensor cores → выигрыша в скорости
нет, fp16 на этой карте лучше). Настоящие блокеры — другие:

```
PS> import triton
triton MISSING: ModuleNotFoundError("No module named 'triton'")
triton kernel FAILED on sm_61: ModuleNotFoundError("No module named 'triton'")
PS> import deepencoder   (build/unlimited_ocr/hf)
deepencoder import FAILED: ModuleNotFoundError("No module named 'einops'")
vision encoder test FAILED: ModuleNotFoundError("No module named 'einops'")
```

А `config.json` требует именно Triton-путь:

```json
"sparse_attention_config": { "dash_use_triton": true, "use_flex_attention": false,
                              "use_xformers": false, "dash_router": "entmax_topk_perlayer",
                              "dash_topk_blocks": 12, "sparse_topk_blocks": 16,
                              "sparse_block_size": 32, "training_stage": "dash" }
```

Triton в сборках torch для **Windows отсутствует в принципе**, а `sparse_gather_triton.py` /
`sparse_gather_e2e_triton.py` — это ядро DASH-внимания, на котором стоит вся «unlimited-horizon» часть.

Итог по железу:

| | значение |
|---|---|
| веса (bf16) | 6.23 GiB из 11.81 GB — **53 % карты до единой активации** |
| квантование в 8 бит | в репозитории **нет** ни тренировки, ни конвертации под quantization; `config.json` жёстко `torch_dtype: bfloat16` |
| vision-энкодер | SAM ViT-B на 1024×1024 = 4096 патчей + CLIP-L; активации **не измерены** (см. §3) |
| трансформеры | требуется `transformers==4.52.1` (README), стоит 5.19.0; кастомный код импортирует `transformers.cache_utils.Cache/DynamicCache` — API v5 отличается |
| рекомендованный путь | SGLang-колесо `sglang-0.5.20.dev10+g8d62f5fb9c-py3-none-any.whl` — в репозитории **LFS-указатель (133 байта)**, версия под Linux/py3.10 |
| стоимость одного кадра | 273 визуальных токена → префилл 3.34 B MoE + авторегрессивная декодировка; для сравнения наш CTC-распознаватель (19 M) читает один кандидат за ~22 мс (§2.6) |

**Вердикт: НЕ ЗАПУСКАЕТСЯ** в этом окружении как есть. С огромными компромиссами (скачать 6.23 GiB, поставить
einops/easydict/addict, откатить transformers до 4.52.1, отказаться от DASH-Triton-пути, fp16, только
base-режим, одна страница) — запустить можно, но: карта 11.81 GB против 6.23 GiB весов + активации
визуального энкодера + KV — это впритык, и **выход не даёт ничего**, чего не даёт наш 19 M CTC
(см. §4.1).

### 2.4 Ответ на главный вопрос: кроппер

**(а) Как предлагаются области кропа?** — **никак**. В репозитории и в HF-коде нет ни одного модуля, который
выдаёт боксы. Три разных «похожих» вещи, и их надо различать:

| механизм | что это на самом деле | где |
|---|---|---|
| `sam_model` (SAM ViT-B) | **энкодер изображения** (даёт фичи, не маски и не боксы); prompt-энкодера и mask decoder'а в весах нет | `modeling_unlimitedocr.py:635, 735, 740, 765`; `deepencoder.build_sam_vit_b` |
| `dynamic_preprocess` | фиксированная сетка 640×640 по aspect ratio — нарезка **входа**, а не предложение кропов | `modeling_unlimitedocr.py:229-267` |
| `<BLOCK>label[x1,y1,x2,y2]` | **текст, который сгенерировал LLM**; координаты нормализованы к 0..999 | `modeling_unlimitedocr.py:98-113, 161-165` |

Проверка «есть ли детектор» — поиск по всему зеркалу: ни `detect`, ни `bbox`-модуля, ни скрипта, который
рисует/ищет прямоугольники по картинке, кроме визуализации уже готовых боксов
(`draw_bounding_boxes`, `process_image_with_refs`).

**(б) SAM — часть весов или опциональный ускоритель?** — **часть весов и обязателен**:
`UnlimitedOCRModel.__init__` всегда строит `self.sam_model = build_sam_vit_b()` и `self.vision_model = build_clip_l()`
(`modeling_unlimitedocr.py:635-636`), в чекпоинте лежат 179 тензоров `sam_model.*` (95.6 M параметров) и
294 тензора `vision_model.*` (303.2 M). Флага «выключить SAM» нет. Модель **не может** работать без него.

**(в) Что даёт тайлинг на кадре 128×128?** — **ничего** (см. §2.1: `ratio = (1,1)`, 273 токенов, апскейл ×8).
На 458×343 — тоже ничего (обе стороны ≤ 640).

**(г) Есть ли маленький пермиссивный компонент, который можно прикрутить?** — **нет, и не потому что лицензия,
а потому что задача не такая**:

* SAM (даже MobileSAM, Apache-2.0, `mobile_sam.pt` ≈ 40 MB) выдаёт **маски**, а не боксы, и отвечает на
  вопрос «где объект», а не «какая строка — ответ». Для наших тонких цветных глифов с помехами он, скорее
  всего, выделит строку целиком — ту же самую строку, которую наш кроппер и так находит. Плюс: новая
  зависимость (сегментация → 40 МБ весов + код + numpy→torch-пайплайн) ради результата, который не отвечает
  на наш вопрос.
* Настоящая наша проблема **не** «найти текст» — кроппер текст находит (0.5357 против 0.4357 у всего кадра).
  Наша проблема — **«найти строку с ответом»** (на `haq/mapcha/map` — 0.950 → 0.075). Это **семантический**
  вопрос, а не вопрос детекции: никакой DBNet/CRAFT/SAM его не решит, потому что они и не пытаются.
* Единственный апстрим-компонент, который умеет «выбрать правильную строку», — это **3.34 B LLM**, которая
  читает страницу целиком и рассуждает. Это не переносится ни в каком виде: весит 6.23 GiB и не влезает.

**(д) Сравнение с нашими измерениями:**

| | наш кроппер (`webapp/cropper.py`) | Unlimited OCR 2 |
|---|---|---|
| скриншоты владельца (`test/*.png`) | **6/6** | не проверялось (веса не грузились) |
| датасет, тип неизвестен (21 тип, 840) | **0.5357** (oracle-полоса 0.6679, весь кадр 0.4357) | не применимо |
| датасет, полоса выучена по типу | **0.6429** | не применимо |
| задержка на кадр 458×343 | ~1.5–3.5 с (32 вызова CTC) | 3.34 B VLM: секунды-десятки секунд на страницу |
| вес | 19 M параметров (PP-OCRv6_medium_rec, 18 762 класса) | 3.34 B + MIT-веса 6.23 GiB |

### 2.5 Что можно взять без их весов

1. **Идея «несколько масштабов, решает самый уверенный»** — это и есть суть gundam в нашем масштабе.
   Их код (`dynamic_preprocess`, 39 строк, MIT) копируется свободно, но **нам он не нужен**: наш кадр
   458×343, их тайл — 640×640 страницы. Наш аналог — горизонтальные полосы (см. §2.6). Это единственная
   идея, которая реально переносится.
2. **Дисциплина «сырой выход → структурированные блоки → рендер»** (`utils/process_unlimitedOCR2.py`,
   379 строк, только stdlib). Ценна **методом**: не смешивать распознавание и интерпретацию. У нас это уже
   есть в `webapp/eval_cropper.py` (`vote()` собирает по каждому кандидату method/box/text/confidence) —
   то есть метод уже внедрён, брать нечего; можно лишь взять их «блочный» формат (метка + bbox + уровень)
   для наших записей.
3. **«Crop + no-repeat n-gram»** (`DeepseekOCRNoRepeatNGramLogitProcessor`, `ngram_size=35`,
   `window_size=128` для одной страницы / 1024 для многостраничных). **Нам не переносится вообще.**
   Механизм — запрет повторов токен-n-грамм во время авторегрессивной декодировки. У нас CTC: выход — это
   решения по кадрам с blank-классом, повторяющихся «n-грамм токенов» там нет. Ближайший аналог в CTC-мире —
   beam search с символьной n-грамм-моделью, но наш промах — это **промах кропа**, а не промах языка
   (модель на правильной полосе даёт 0.8875). Переносится только **идея «ограничить декодер приором»** —
   а это уже есть в `docs/pipeline-design.md` §4 (алфавитная маска + приор длины) и **ещё не реализовано**.
4. **Обучение**: смесь данных **не опубликована** (в репозитории нет вообще скриптов обучения); длинногоризонтная
   программа (R-SWA/SR-SWA) к CTC-распознавателю на полосе 32 px неприменима; **аугментация масштабом**
   переносится — но у нас она уже сделана на уровне вывода (`keep`/`keep2`/`keep4` в `webapp/cropper.py`
   — это те же «масштабы», только без обучения).
5. **Идея, которую стоит украсть (среднесрочно)**: «модель сама выдаёт и текст, и его прямоугольник»
   (end-to-end). У нас ровно эта проблема: кроппер решает, а не модель. Аналог: **CRNN+CTC с добавочной
   головой локализации**, обученная на наших 210 000 PNG с `roi`-метками. Это требует обучения, поэтому в
   «самый дешёвый эксперимент» не идёт — но это единственная идея из апстрима, бьющая точно в нашу
   открытую проблему.

### 2.6 ЭКСПЕРИМЕНТ (выполнен): полосы-кандидаты как «gundam в нашем масштабе»

Идея: их gundam = показать распознавателю картинку на нескольких масштабах и выбрать уверенный ответ.
Наш аналог для кадра 458×343 — **полноширинные горизонтальные полосы** (единица, в которой живёт строка
текста): k=3 и k=4 полосы с шагом 1/k. Кандидаты добавляются к списку нынешнего кроппера, правило выбора —
то же (максимум уверенности).

Скрипт: `build/unlimited_ocr/_tilegrid_probe.py` (пишет только в `build/`, `webapp/**` не тронут).

```
PS> .venv-gpu\Scripts\python.exe -u build\unlimited_ocr\_tilegrid_probe.py --n 5 --ks 3 4 --out build\unlimited_ocr\tilegrid.json
loading the model ...
  ppocrv6, 18762 classes
--- the owner's screenshots (file name = gold) ---
  1651.png     gold=1651    base=1651      OK  | aug=1651      OK   (3138 ms)
  2013.png     gold=2013    base=2013      OK  | aug=2013      OK   (2738 ms)
  3620.png     gold=3620    base=3620      OK  | aug=3620      OK   (1842 ms)
  5932.png     gold=5932    base=5932      OK  | aug=5932      OK   (2725 ms)
  5968.png     gold=5968    base=5968      OK  | aug=5968      OK   (2584 ms)
  7488.png     gold=7488    base=7488      OK  | aug=7488      OK   (2527 ms)
  screenshots: base 6/6, +strips 6/6
--- the dataset (5 samples per type) ---
  out/Archy-X/Krypton/map                              n=5   base 1.000  +strips 1.000  (fixed 0, broken 0)
  out/InstantlyMoist/Captcha/textcaptcha               n=5   base 0.000  +strips 0.000  (fixed 0, broken 0)
  out/JSH32/Minecaptcha/map                            n=5   base 0.200  +strips 0.600  (fixed 2, broken 0)
  out/LagBug/XProtect/code                             n=5   base 0.600  +strips 0.200  (fixed 0, broken 2)
  out/LagBug/XProtect/map                              n=5   base 0.400  +strips 0.400  (fixed 0, broken 0)
  out/haq/mapcha/map                                   n=5   base 0.200  +strips 0.000  (fixed 0, broken 1)
  out/irootdev/AnBot/captcha                            n=5   base 1.000  +strips 1.000  (fixed 0, broken 0)
  out/jonesdevelopment/sonar/complex                   n=5   base 0.600  +strips 0.800  (fixed 1, broken 0)
  out/jonesdevelopment/sonar/legacy                    n=5   base 0.800  +strips 0.600  (fixed 0, broken 1)
  out/jonesdevelopment/sonar/standard                  n=5   base 0.400  +strips 0.200  (fixed 0, broken 1)
  out/just-captcha/ProstoCaptcha/map                   n=5   base 0.000  +strips 1.000  (fixed 5, broken 0)
  out/ringoame196-s-mcPlugin/ReproductionCAPTCHA/map   n=5   base 1.000  +strips 1.000  (fixed 0, broken 0)
  out_ru/BotFilter/map                                 n=5   base 1.000  +strips 0.800  (fixed 0, broken 1)
  out_ru/CaptchaVerifyZ/map                            n=5   base 0.400  +strips 1.000  (fixed 3, broken 0)
  out_ru/GalleryCaptcha/ru-numberword                  n=5   base 0.000  +strips 0.000  (fixed 0, broken 0)
  out_ru/GalleryCaptcha/ru-numberword-caption          n=5   base 0.000  +strips 0.000  (fixed 0, broken 0)
  out_ru/GalleryCaptcha/ru-symbols                     n=5   base 0.800  +strips 0.800  (fixed 0, broken 0)
  out_ru/GalleryCaptcha/ru-web                         n=5   base 0.800  +strips 0.800  (fixed 0, broken 0)
  out_ru/LimboFilter/digits                            n=5   base 0.800  +strips 0.800  (fixed 0, broken 0)
  out_ru/LimboFilter/map                               n=5   base 0.000  +strips 0.000  (fixed 0, broken 0)
  out_ru/LimboFilter/symbols                           n=5   base 0.400  +strips 0.400  (fixed 0, broken 0)
  TOTAL n=105  base 0.4952  +strips 0.5429  (92 s)
written build\unlimited_ocr\tilegrid.json
```

Читать эти числа надо так:

* **+4.8 п.п. (0.4952 → 0.5429)** на тех же 105 сэмплах; починено 11, испорчено 6.
* **Крупнейший выигрыш — ровно на «больной» тип**: `just-captcha/ProstoCaptcha/map` **0.000 → 1.000** (починено 5)
  — тот самый тип, где в `reports/CROPPER.md` §2.2 кроппер даёт 0.150 при oracle 0.950. Плюс
  `out_ru/CaptchaVerifyZ/map` 0.400 → 1.000 и `out/JSH32/Minecaptcha/map` 0.200 → 0.600.
* **Испорчено 6**: `LagBug/XProtect/code` 0.600 → 0.200 (2), `haq/mapcha/map` 0.200 → 0.000 (1),
  `sonar/legacy` 0.800 → 0.600, `sonar/standard` 0.400 → 0.200, `BotFilter/map` 1.000 → 0.800.
  Механизм тот же, что описан в `reports/CROPPER.md` §4: **модель бывает уверенно неправа**, а правило
  «побеждает максимум уверенности» при росте числа кандидатов чаще находит *уверенную муку*.
* Скриншоты владельца **не сломались**: 6/6 → 6/6. Стоимость: 92 с на 105 сэмплов × 71 вызов
  распознавателя (32 базовых + 32 + 7 расширенных) ≈ **12 мс на вызов**; полосы добавляют 7 кандидатов к 32.
* **Важная оговорка о числах**: абсолютный baseline здесь **0.4952**, а не 0.5357 из `reports/CROPPER.md` —
  потому что выборка n=5 на тип вместо n=40. Сравнение base↔aug **внутри одних и тех же сэмплов** — корректное;
  переносить абсолютные числа нельзя.
* Эксперимент **не** доказывает, что полосы надо вставлять «как есть»: 6 испорченных сэмплов показывают,
  что нужен либо порог по уверенности (применять полосы, только если лучший базовый кандидат неуверен),
  либо ограничение области полос (искать полосу рядом с найденной строкой глифов), либо приоритет.

---

## 3. Что НЕ проверено

| что | почему |
|---|---|
| **Сам прогон модели** (качество на капчах, реальное время, пиковое VRAM) | веса 6.23 GiB > лимита «не скачивать >2 GB»; ничего не устанавливал |
| **Пиковое потребление VRAM визуального энкодера** | `deepencoder.py` не импортируется (`einops` не установлен), обойти нельзя без установки пакета; активации SAM ViT-B на 1024×1024 не измерены — в отчёте только расчёт по config |
| **Смесь данных и рецепт обучения** | в репозитории нет ни одного скрипта обучения; PDF статьи не распарсен (нет `pypdf`/`fitz`, устанавливать не стал) — прочитан только **абстракт** arXiv 2606.23050 |
| **PDF статьи версии 2** | `Unlimited-OCR-2.pdf` в git — 132-байтный LFS-указатель; настоящий PDF (1 515 854 Б) лежит в HF-репозитории, но текст извлечь нечем |
| **Качество на наших кадрах** | не измерялось: без весов модель не запустить |
| **Тег `UnlimitedOCR1.0`** | скачаны только README/LICENSE/infer.py (дерево — 12 записей, `utils/` там нет вообще: `utils/process_unlimitedOCR.py` → 404) |
| **Путь через SGLang** | колесо — LFS-указатель (133 Б), версия Linux/py3.10; на этой машине не проверялось |
| **Реальная стоимость 32-вызовного голосования «полосы» в проде** | замерен один прогон на 105 сэмплах; на 210 000 сэмплов не пересчитывал |
| **Работа их `infer.py`** | требует `sglang.srt.sampling.custom_logit_processor` (в README это сказано явно), т.е. кастомное колесо |
| **Что делает `dash_attention.py` по существу** | файл на 71 КБ, я читал только точки интеграции (конфиг + импорт), а не реализацию DASH-роутера |
| **Ничего не проверено «на нашем датасете» кроме эксперимента §2.6** | датасет не перегенерировался, `labels.jsonl` не менялись, модель не дообучалась |

---

## 4. Что сломано

### 4.1 В апстриме

1. **Репозиторий — не то, что читают.** README называет репозиторий источником модели, но модели там нет:
   весь код модели лежит в Hugging Face и грузится через `trust_remote_code=True` — то есть при загрузке
   выполняется произвольный Python из хаба. Для публикуемого проекта это плохая практика, и это надо
   проговорить, прежде чем что-то «брать».
2. **PDF статьи в git — указатель, а не статья.** `Unlimited-OCR-2.pdf` = 132 байта (LFS), `assets/*.png` =
   131–134 байта, `wheel/*.whl` = 133 байта. Человек, скачавший репозиторий, получит три «битых» файла,
   если у него не настроен LFS.
3. **`infer.py` не самодостаточен:** он импортирует `DeepseekOCRNoRepeatNGramLogitProcessor` из
   `sglang.srt.sampling.custom_logit_processor`, то есть требует кастомного колеса из репозитория
   (это прямо написано в `utils/README.md`). «Evaluation» в README выглядит как две команды, но вторая
   половина (SGLang-сервер) — отдельная установка Linux-колеса.
4. **В теге `UnlimitedOCR1.0` нет `utils/`** вообще, хотя README первой версии обещает пост-обработку;
   `v1/utils/process_unlimitedOCR.py` → **404**.
5. **Непоследовательность «README ↔ код»:** README говорит «A single page is encoded with dynamic tiling
   (gundam mode) by default», но код (`_uocr_build_inputs`) для картинок ≤ 640 px по обеим сторонам
   **тайлы не строит вовсе** — то есть для небольших картинок «gundam by default» неверно.
6. **Непоследовательность «config ↔ код»:** `config.json` содержит `"use_cache": false`, а
   `_uocr_generate` явно работает с `DynamicCache` и `use_cache=True`.
7. **Путь к статье в README ведёт в git (`blob/Unlimited-OCR-2/Unlimited-OCR-2.pdf`)**, где лежит LFS-указатель;
   arXiv 2606.23050 — это **v1** («Unlimited OCR Works», R-SWA), а в `main` — **v2** (SR-SWA). То есть
   arXiv-статья описывает не тот код, который в `main`, и второй статьи в проверяемых мной местах нет.
8. **Windows не поддержан:** DASH-внимание построено на Triton (`dash_use_triton: true`), Triton для
   Windows в сборках torch отсутствует; рекомендованный сервер — Linux-колесо.

### 4.2 В нашем проекте (найдено попутно, не чинил — файлы не мои)

9. **Правило «побеждает максимум уверенности» хрупко при росте числа кандидатов.** Измерено в §2.6:
   +7 кандидатов-полос дали +11 и −6 сэмплов. Т.е. добавление предложений без приоритизации **ухудшает**
   систему на типах, где модель уверенно ошибается (`LagBug/XProtect/code`, `haq/mapcha/map`).
   Это прямое указание на следующий шаг: нужен либо порог по уверенности, либо приоритет полосы,
   либо ограничение полос окрестностью найденной строки глифов.
10. **`webapp/cropper.py` не имеет понятия «строка с ответом»** — только «строка с глифами». Это
    подтверждено ещё раз: на `haq/mapcha/map` кроппер даёт 0.075 при oracle 0.950 (`reports/CROPPER.md` §2.2).
11. **Ничего не сломано в сети веб-приложения** — не проверял (задача не про это).

---

## 5. Расхождения

| утверждение | где | что на самом деле |
|---|---|---|
| «Unlimited OCR 2 использует SAM-механизм, которая предлагает кропы, на которые смотрит декодер» | бриф задачи (по наводке из README) | **Неверно.** SAM ViT-B — **энкодер изображения** (`modeling_unlimitedocr.py:635`); в весах 179 тензоров `sam_model.*`, prompt-энкодера/mask-decoder нет. Кропов никто не предлагает: прямоугольники — токены LLM. Единственное, что похоже на «SAM в логах», — env-переменная README `SGLANG_OPT_UOCR_SAM_REL_POS_BIAS_MB` («chunk cap for the SAM attention bias») — это **лимит чанка смещения внимания**, а не сегментация |
| «на Pascal нет bf16» | бриф задачи | **Неверно как утверждение о работоспособности:** bf16-матмул и bf16-conv на sm_61 работают (измерено). Настоящего tensor cores нет → bf16 эмулируется, выигрыша в скорости нет, fp16 лучше. Реальные блокеры — 6.23 GiB весов, отсутствие Triton на Windows, `einops`/`addict`, transformers 4.52.1 vs 5.19.0 |
| «`crop_mode=True` (gundam) меняет сетку тайлов, бюджет разрешения и цену токенов» | бриф задачи | Для **наших** кадров — **не меняет ничего**: `image.size[0] <= 640 and image.size[1] <= 640` → `ratio=(1,1)`, тайлов 0, глобальный вид 273 токенов. Изменения начинаются только для страниц > 640 px |
| «README: single page кодируется gundam по умолчанию» | README апстрима | Верно только для страниц > 640 px; для малых картинок код молча уходит в base-режим |
| «статья arXiv 2606.23050 описывает Unlimited OCR 2» | бриф задачи / README | arXiv 2606.23050 = **v1** (R-SWA, «Unlimited OCR Works»); v2 — SR-SWA, и его статьи в проверяемых местах нет (в git — LFS-указатель) |
| «веса ~2 ГБ / влезают» | бриф задачи | Веса **6.23 GiB** в bf16 (6 687 958 536 Б) — это 53 % карты до активаций; лимит «не скачивать >2 ГБ» соблюдён |
| «0.5357 на датасете — это baseline для сравнения» | бриф задачи | В эксперименте §2.6 baseline на выборке n=5/тип = **0.4952**; числа из `reports/CROPPER.md` (n=40) не переносятся на другую выборку — сравнивать можно только внутри одной выборки |
| `LICENSE` = MIT, `license:mit` в HF | код и веса | **Подтверждено обоими источниками** — расхождений нет (для сравнения: `AGENTS.md` проекта требует проверки лицензий по семействам плагинов; здесь всё чисто) |

---

## 6. Вердикт

### 6.5 Таблица решений

| item | what | licence | size | effort | expected gain for CaptchaOCR | verdict |
|---|---|---|---|---|---|---|
| **Веса Unlimited-OCR-2** | 3.34 B VLM-OCR | MIT | **6.23 GiB** (2 шарда) | очень высокий (скачать, `einops`/`addict`, transformers 4.52.1, обойти Triton) | ≈0: капча — не документ, CTC-распознаватель на полосе лучше и в 100 раз легче | **ignore** |
| **SAM ViT-B внутри модели** | энкодер, обязателен | MIT | 191 MB bf16 | очень высокий | 0 (это энкодер, не детектор) | **ignore** |
| **«SAM-based crop attention»** | **не существует** в коде | — | — | — | — | **ignore** (заблуждение брифа) |
| **Детектор в репозитории** | **не существует** | — | — | — | — | **ignore** |
| **`dynamic_preprocess` (gundam)** | сетка 640×640 по aspect ratio | MIT | 39 строк | 15 мин | средняя — но не в их виде: на кадре ≤640 px их код не даёт тайлов вообще | **adapt** (переписать как полосы) |
| **Идея «несколько масштабов, побеждает уверенный»** | суть gundam | идея (MIT-исходник) | 0 | <1 ч | **измерено +4.8 п.п.** (§2.6), 11 починено / 6 испорчено | **adapt** (+ починить приоритизацию) |
| **No-repeat n-gram logit processor** | запрет повторов n-грамм при декодировании | MIT | 15 строк | 0 | **0** — у нас CTC, повторяющихся токен-n-грамм нет | **ignore** |
| **`_uocr_no_repeat_ngram`** (их реализация, vLLM-парити) | то же | MIT | 15 строк | 0 | 0 | **ignore** |
| **`utils/process_unlimitedOCR2.py`** | пост-обработка «сырой вывод → markdown», только stdlib | MIT | 379 строк | 1 ч | низкая — метод уже есть у нас в `eval_cropper.vote()` | **adapt** (формат записи) |
| **`infer.py`** | клиент бенчмарка к SGLang | MIT | 9.6 КБ | — | 0 (нужен SGLang-сервер на Linux) | **ignore** |
| **SR-SWA / DASH block-sparse внимание** | «безграничный» контекст | MIT | — | очень высокий | 0 — нам не нужен длинный контекст | **ignore** |
| **Формат выхода `<BLOCK>label[bbox]`** | структурированные блоки с координатами | MIT | — | 0 | понятие — полезно для записей о кандидатах | **adapt** (как формат, не как код) |
| **MobileSAM / FastSAM** (внешний) | маски, не боксы | Apache-2.0 (MobileSAM) | ≈40 MB | 2–3 ч | ≈0: отвечает на вопрос «где текст», а не «какая строка — ответ» | **ignore** |
| **Идея «модель выдаёт и текст, и его прямоугольник» (end-to-end)** | сквозной детектор+распознаватель | идея | +2–4 M параметров к нашей сети | 1–2 дня обучения | **высокая** — это прямой ответ на нашу открытую проблему («решает кроппер, а не модель») | **steal (идея)** |

### 6.6 Самый дешёвый следующий эксперимент (один)

**Что:** полосы-кандидаты (k=3, 4) поверх нынешнего кроппера — «gundam в масштабе капчи». **Уже выполнен**
(§2.6), результат ниже; следующий шаг — починить приоритизацию, чтобы перестало ломать 6 сэмплов.

**Команда (ровно та, что выполнялась):**

```powershell
$env:PYTHONIOENCODING="utf-8"
.venv-gpu\Scripts\python.exe -u build\unlimited_ocr\_tilegrid_probe.py --n 5 --ks 3 4 --out build\unlimited_ocr\tilegrid.json
```

Время — 92 с на 105 сэмплов + ~20 с на модель. Новых зависимостей нет, обучения нет, сети в рантайме нет,
`webapp/**` не меняется.

**Что считать успехом** (порог, зафиксированный до результата):

1. скриншоты владельца остаются **6/6** — иначе эксперимент провален;
2. на датасете exact **не ниже** базового (0.4952 на этой выборке);
3. целевой скачок — **≥ +2 п.п.**, а главный интерес — `just-captcha/ProstoCaptcha/map` и
   `out_ru/CaptchaVerifyZ/map` (это и есть «строка с ответом», а не «строка с текстом»).

**Факт:** порог выполнен — **0.4952 → 0.5429 (+4.8 п.п.)**, скриншоты 6/6, починено 11 / испорчено 6.
`just-captcha/ProstoCaptcha/map`: **0.000 → 1.000**.

**Что делать дальше (одна строка, без новых зависимостей):** применять полосы **только когда лучший
базовый кандидат неуверен** (например, conf < 0.9), либо ограничить полосу окрестностью найденной строки
глифов — тогда 6 испорченных сэмплов должны уйти, а 11 починенных — остаться. Это следующий заход, он
требует правки `webapp/cropper.py` (файл не мой) — в отчёт не входит.

### 6.7 Общий вердикт по апстриму

**Unlimited OCR 2 — хорошая работа, но не наш инструмент.** Это документный VLM-парсер: 3.34 B параметров,
MoE-декодер, SAM+CLIP-энкодер, SR-SWA для «безграничного» контекста, MIT-лицензия на код и веса.
Для капчи (4–6 символов на кадре 128×128) это **неправильный масштаб класса**: он в 175 раз тяжелее нашей
модели, его вход-энкодер всё равно получает 273 токена (апскейл ×8 нашего 128×128), а его «кроппер» —
это он сам, 3.34 B модель, которую надо кормить картинкой целиком.

Что реально остаётся: (1) **идея нескольких масштабов** — единственное, что мы уже измерили как
работающее (+4.8 п.п.); (2) **дисциплина структурированного выхода**; (3) **идея сквозного «текст+бокс»**,
которую стоит украсть в нашу сеть — но это уже обучение, а не «взять и прикрутить».

---

## 7. Протокол раундов исследования (6 раундов, как в брифе)

| # | что смотрел | что вышло |
|---|---|---|
| 1 | `git clone` (main + тег v1), `webapp/cropper.py`, `reports/TRAINING_LIMBO_DIGITS.md` | клон **упал** (schannel SEC_E_NO_CREDENTIALS); прочитан кроппер и стиль отчёта |
| 2 | codeload-zip, openssl-backend, README апстрима, `reports/CROPPER.md` | zip тоже не скачался; README получен; измерения кроппера (6/6, 0.5357, 0.6429) |
| 3 | диагностика TLS + дерево GitHub API | причина клона найдена (`http.sslcainfo` → несуществующий PEM); дерево `main` получено (кода модели нет) |
| 4 | проверка сети из Python, список веток, метаданные HF | Python ходит в сеть → можно зеркалить код; найдено: модель в HF-репо, `license:mit`, 3.34 B |
| 5 | скрипт зеркалирования + абстракт arXiv | скачано 30 файлов (GitHub + HF-код, **без весов**); прочитан абстракт (R-SWA, v1) |
| 6 | запуск зеркала, чтение `docs/pipeline-design.md` | получен полный код; подтверждено, что кода модели в git нет |
| 7 | `LICENSE`, `config.json`, `utils/README.md`, поиск по SAM | найдено: SAM = энкодер; gundam = входная нарезка; bbox = токены LLM |
| 8 | проба: заголовки safetensors + bf16 на GPU + чтение `modeling_unlimitedocr.py` | точные размеры компонентов; bf16 **работает** на sm_61; TRT/SAM-пути в коде |
| 9 | `dynamic_preprocess` / `_uocr_build_inputs` / `infer()` | точный бюджет токенов (273 + 420…960) и вывод «на кадре ≤640 px тайлов нет» |
| 10 | проба 2 (компоненты обоих шардов) + PDF | точные параметры (SAM 95.6 M, CLIP 303.2 M); PDF не распарсен → смесь данных **не проверена** |
| 11 | **эксперимент** (фон) + `agents/AGENT_LOG.md` §1.3 | +4.8 п.п., скриншоты 6/6 |

Формат отчёта — по `agents/AGENT_LOG.md` §1.3 (files touched / verified / not verified / broken / discrepancies)
и по форме `reports/TRAINING_LIMBO_DIGITS.md`. Ни один измеренный JSON в `reports/` не редактировался;
новый измеренный JSON эксперимента лежит в `build/unlimited_ocr/tilegrid.json`.
