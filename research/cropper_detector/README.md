# Прототип «крошечного детектора» полосы ответа

Следующая задача проекта — заменить эвристическую часть кроппера (`webapp/cropper.py`) обученной
сетью, которая сама находит строку с ответом. Здесь — заготовка этой сети и измеритель к ней;
**измерений пока нет** (см. «Что не проверено»).

| файл | что делает |
|---|---|
| `detector.py` | `classical_detect()` — детектор на numpy + Pillow (квантование цветов → маски → морфологическое закрытие → связные компоненты своим union-find → фильтр «похож на глиф» → кластеризация в строки → оценка строки); `LearnedDetector` — крошечный U-Net `TinyUNet` (~170 тыс. параметров, холст 128×128, веса `detector.pt` рядом со скриптом); `ink_bbox` — копия `train/ppocr_data.py::ink_bbox` (текущий кроппер, база сравнения) |
| `eval_detector.py` | измеритель: на одних и тех же сэмплах — oracle-полоса (метка `roi`), полоса детектора и весь кадр; IoU, «содержит ли полосу», exact match через ту же модель, что отдаёт приложение (`webapp/app.py::PPOCRBackend`); плюс 6 скриншотов владельца (`test/*.png`) и контактный лист `crops.png` |
| `explore.py` | контактные листы кадров датасета с нарисованной меткой `roi` → `explore_a.png`, `explore_b.png` |
| `explore2.py` | насколько `ink_bbox` отстаёт от метки `roi` (IoU и «содержит» по типам) |
| `explore3.py` | цветовые гистограммы 6 реальных скриншотов → `real_<id>.png` (картинки `explore_*.png` и `real_*.png` — результаты этих прогонов) |

Запуск (из корня репозитория; флаги: `--method {classical,learned,ink}`, `--all`, `--n`, `--seed`, `--types <подстрока>`, `--device cuda|cpu`, `--shots`, `--out <json>`):

```powershell
.venv-gpu\Scripts\python.exe research\cropper_detector\eval_detector.py --method classical --n 20 --seed 1234
.venv-gpu\Scripts\python.exe research\cropper_detector\eval_detector.py --method learned   --n 20 --seed 1234
.venv-gpu\Scripts\python.exe research\cropper_detector\eval_detector.py --all --n 30 --seed 1234 --shots
```

**Что не проверено.** `classical_detect()` падает на каждом проверенном кадре (5/5 из 5 разных типов):
в `_cluster_rows()` перебираются ключи словаря-строки вместо `row["items"]` → `TypeError`. Обученный
детектор не запускается — файла весов `detector.pt` в папке нет. Не стартует и измеритель: он зовёт
`webapp._ck(...)`, а веб-приложение после разбивки на модули экспортирует `resolve_checkpoint` →
`AttributeError: module 'app' has no attribute '_ck'`. Пути внутри скриптов ещё указывают на прежнее
место папки (`build/cropper_detector/`).

**Supervision** — готовые метки `roi` в `labels.jsonl`: локально **129 984** кадра в **13** типах
(из 210 000; 80 016 без полосы), в опубликованных 20 типах — 119 984. Разметку не перегенерировать.
