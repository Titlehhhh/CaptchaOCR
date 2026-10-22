# Архив отчётов CaptchaOCR

Здесь лежат **старые и заменённые** отчёты. Ничего не удалено: всё переехало сюда через `git mv`,
история файлов сохранилась (`git log --follow <путь>`).

**Правило архива:** в `reports/` остаётся только то, что нужно владельцу прямо сейчас —
живые отчёты текущей сессии и **измеренные результаты** (JSON, который никогда не правится руками).
Всё, что было заменено более свежим измерением или документом, — здесь.

| Куда | Что было | Когда | Почему в архиве | Чем заменено |
|---|---|---|---|---|
| `2026-10-02-old-html/captcha_report.html` | первый HTML-отчёт проекта (маленький, без картинок) | 02.10.2026 | формат устарел, числа — из первых JSON-замеров | `reports/HTML/index.html`; числа — `reports/bench_models/*.json` |
| `2026-10-02-old-html/captcha_pdf_embedded.html` | тот же отчёт с картинками, вшитыми в base64 (321 КБ) — для печати в PDF | 02.10.2026 | картинки вшиты в разметку, отчёт нечитаем без HTML | `reports/HTML/index.html` + `reports/HTML/img/*.png` (картинки отдельными файлами) |
| `2026-10-21-old-baselines/CAPTCHA_OCR_REPORT.md` | «Поиск готовых CAPTCHA/OCR-моделей» с базовыми линиями по **старому** протоколу (104 картинки: EasyOCR 0.115 / CER 1.835, anuashok 0.077) | 21–22.10.2026 | цифры считались на сломанном рендере и по 104 картинкам, а не по 920; рецензия `reviews/C2_technical.md` это подтвердила | числа — `reports/bench_models/*.json` (единый протокол, 920 предметов); обзор моделей — `reports/HTML/index.html` §4 и `reports/research3/MODEL_LANDSCAPE.md` |
| `2026-10-21-old-baselines/PUBLISH_NOTES.md` | заметки о публикации (46 типов × 100 = 4600 PNG, репозиторий приватный) | 21.10.2026 | датасет перегенерирован 22.10 (500 на тип), публикация переделана | `reports/HF_DATASET_UPLOAD.md` и `reports/HF_PUBLISH_REPORT.md` |
| `2026-10-21-research-wave1/research/00_SYNTHESIS.md` | первый синтез по исследованию: «мешает не архитектура, а разнообразие данных» | 21.10.2026 | числа (4600 сэмплов) устарели — датасет перегенерирован; выводы переписаны волнами 2–3 | `reports/research3/*` и сводный `reports/HTML/index.html` |
| `2026-10-21-research-wave1/research/00_SYNTHESIS.pdf` | PDF-версия того же синтеза | 21.10.2026 | дубликат `.md` в том же каталоге | `.../research/00_SYNTHESIS.md` |
| `2026-10-21-research-wave1/research/briefs/A_ocr_engines.md` | одноразовое ТЗ субагента «современные OCR-движки» | 21.10.2026 | это процесс, а не результат; результат — в отчётах волн 2–3 | `reports/research3/MODEL_LANDSCAPE.md`, `reports/HTML/index.html` §4 |
| `2026-10-21-research-wave1/research/briefs/B_vlm_ocr.md` | ТЗ «VLM: как GPT/Qwen/DeepSeek читают текст» | 21.10.2026 | то же: входной бриф, а не результат | `reports/research3/MODEL_LANDSCAPE.md` |
| `2026-10-21-research-wave1/research/briefs/C_str_architectures.md` | ТЗ «архитектуры распознавателей строки» | 21.10.2026 | то же | `reports/research3/TRAINING_METHODS.md`, `reports/research3/MODEL_LANDSCAPE.md` |
| `2026-10-21-research-wave1/research/briefs/D_data_corpora.md` | ТЗ «корпуса и синтетика» | 21.10.2026 | то же | `reports/research3/TRAINING_METHODS.md` |
| `2026-10-21-research-wave1/research/briefs/E_unknown_plugin_pipeline.md` | ТЗ «рецепт для неизвестного плагина» | 21.10.2026 | то же | `reports/HTML/index.html` §3, `docs/pipeline-design.md` |
| `2026-10-22-overview/CAPTCHA_SYSTEM_OVERVIEW.md` | большой сводный документ «как устроено решение капч изнутри, что готово, что делать» (880 строк) | 22.10.2026 | это предшественник нынешнего HTML-отчёта: те же разделы, но часть чисел устарела (§6.6: PP-OCRv6 «0.768 по полосе / 0.145 по кадру» вместо нынешних 0.552 / 0.035) | `reports/HTML/index.html` (тот же синтез со свежими числами) |
| `2026-10-22-research-wave2/research2/A_ready_projects.md` | обзор готовых проектов и фреймворков end-to-end | 22.10.2026 | нарратив-обзор, заменён обзором волны 3 и таблицей моделей | `reports/research3/MODEL_LANDSCAPE.md`, `reports/HTML/index.html` §4 |
| `2026-10-22-research-wave2/research2/B_ready_models.md` | обзор моделей на Hugging Face | 22.10.2026 | то же | `reports/research3/MODEL_LANDSCAPE.md` + измеренные `reports/bench_models/*.json` |
| `2026-10-22-research-wave2/research2/C_how_it_works.md` | как внутри устроено распознавание (образовательный разбор) | 22.10.2026 | разбор устарел по сравнению со свежим документом о моделях | `docs/OCR_MODELS_101.md`, `reports/HTML/index.html` §3 |
| `2026-10-22-research-wave2/research2/E_training_methods.md` | методики обучения (литература: разнообразие vs объём, аугментации, self-training) | 22.10.2026 | **прямо помечен как заменённый** в `reports/research3/TRAINING_METHODS.md` (поле `prior_report_superseding`) | `reports/research3/TRAINING_METHODS.md` |
| `2026-10-22-research-wave2/research2/F_runtime_llamacpp.md` | свой runtime по образцу llama.cpp, но для капч | 22.10.2026 | нарратив заменён **измерениями** рантайма | `reports/bench_models/T2_*.json` (паритет torch/ONNX, int8, скорость) |
| `2026-10-22-research-wave2/research2/G_test_plan.md` | план «честного тестирования» | 22.10.2026 | протокол реализован и выполнен; числа в тексте (0.115, 0.768/0.145) заменены измеренными | `bench/bench_models.py` + `reports/bench_models/*.json` |
| `2026-10-22-research-wave2/research2/H_v1_family.md` | семейство «стандартные капчи V1» из группы GalleryCaptcha | 22.10.2026 | не измерение, а нарратив-исследование; свежая версия по этому семейству | `reports/SITE_CAPTCHAS.md` |
| `2026-10-22-research-wave2/research2/T1_models_test.md` | тест 12 готовых моделей по единому протоколу (родитель отчётов `bench_models/`) | 22.10.2026 | **цифры остаются актуальными**, но первоисточник — измеренные JSON, которые остались на месте; нарратив — в HTML-отчёте | `reports/bench_models/*.json` (остались в `reports/`), `reports/HTML/index.html` §4–5 |
| `2026-10-22-research-wave2/research2/T2_onnx_runtime.md` | наш CRNN → ONNX → int8 → «одна папка без Python» | 22.10.2026 | то же: числа живут в `T2_*.json`, нарратив — в HTML-отчёте | `reports/bench_models/T2_*.json` (остались в `reports/`), `reports/HTML/index.html` §5.1 |
| `2026-10-22-reviews/reviews/C1_professor.md` | рецензия «глазами преподавателя» по README на коммите `84d181f` | 22.10.2026 | снимок старого состояния README (номера строк уже не сходятся) | `reports/HTML/index.html`, `docs/` |
| `2026-10-22-reviews/reviews/C2_technical.md` | техническая рецензия «честны ли цифры» | 22.10.2026 | проверяла старые `reports/bench_results*.json` (104 картинки) и старую карточку HF; её претензии закрыты новыми измерениями | `reports/bench_models/*.json`, `reports/TRAINING_*_BIG.*` |
| `2026-10-22-reviews/reviews/C3_hygiene.md` | ревизия чистоты публикации, вердикт «публиковать нельзя» по коммиту `84d181f` | 22.10.2026 | состояние публикации изменилось: датасет и карточка модели уже на HF | `reports/HF_PUBLISH_REPORT.md`, `reports/HF_DATASET_UPLOAD.md` |
| `2026-10-22-reviews/reviews/V1_visual.md` | визуальная проверка README и страниц HF (снимок v1/v2) | 22.10.2026 | README переписывался прямо во время проверки; выводы описывают прошлую версию | `reports/HTML/index.html` (нынешняя витрина проекта) |

## Важно про ссылки

Внутренние ссылки **архивных** документов ведут на прежние пути (`reports/research2/…`, `reports/bench_results*.json` и т. п.) —
они не переписаны: содержимое файлов не менялось, менялся только путь.
Карта «старый путь → новый путь» — в `reports/README.md` (раздел «Архив»).

Измеренные результаты, на которые ссылаются архивные тексты, **остались на месте** в `reports/`:
`reports/bench_models/*.json`, `reports/bench_results*.json`, `reports/bench_results_onnx.json`,
`reports/bench_results_others.json`, `reports/eval_main_final.json`, `reports/bench_per_type.json`.
