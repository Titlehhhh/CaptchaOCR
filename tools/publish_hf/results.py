import json
import os
import re
from pathlib import Path

from .constants import BENCH_JSON, MODEL_CARD_TEMPLATES, REPO_ROOT, TRAINING_REPORT_JSON
from .utils import warn

# =====================================================================================
# Карточка PP-OCRv6: числа берутся из отчёта об обучении, а не пишутся руками
# =====================================================================================

def load_json_file(path: Path) -> dict | None:
    """Прочитать JSON-файл. Нет файла или битый JSON — ``None`` (числа не выдумываются)."""
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError) as exc:
        warn(f"Не удалось прочитать {path}: {type(exc).__name__}: {exc}")
        return None
    return data if isinstance(data, dict) else None


def num(value, digits: int = 4) -> str:
    """Число для карточки: float округляется, ``None`` превращается в прочерк."""
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{round(value, digits)}"
    return str(value)


def grouped_int(value) -> str:
    """Целое с пробелами-разделителями: 19134326 → ``19 134 326``."""
    if not isinstance(value, int):
        return str(value)
    return f"{value:,}".replace(",", " ")


def zero_step_table(report: dict) -> str:
    """Таблица «нулевой шаг» (базовая модель до дообучения) по удержанным типам."""
    zero = report.get("zero_step") or {}
    per_type = zero.get("per_type") or {}
    agg = zero.get("aggregate") or {}
    lines = ["| held-out type | exact match | CER |", "|---|---|---|"]
    for name in sorted(per_type):
        row = per_type[name] or {}
        lines.append(f"| `{name}` | {num(row.get('exact_match'))} | {num(row.get('cer'))} |")
    items = sum(int((row or {}).get("n") or 0) for row in per_type.values())
    types = agg.get("types", len(per_type))
    lines.append(f"| **median over {types} types** | **{num(agg.get('exact_match_median'))}** "
                 f"| **{num(agg.get('cer_median'))}** |")
    lines.append(f"| **micro ({items} images)** | **{num(agg.get('exact_match_micro'))}** "
                 f"| **{num(agg.get('cer_micro'))}** |")
    return "\n".join(lines)


def train_run_block(report: dict, source: str) -> str:
    """Блок «что отработало»: команда, эпохи, шаги, лосс, скорость, чекпоинт."""
    run = report.get("training_run") or {}
    command = str(run.get("command") or "—")
    epochs = run.get("epochs_completed")
    steps = run.get("steps_completed")
    planned_steps = run.get("planned_steps")
    match = re.search(r"--epochs\s+(\d+)", command)
    planned_epochs = match.group(1) if match else "—"
    timeline = run.get("loss_timeline") or []
    loss_first = (timeline[0] or {}).get("loss") if timeline else None
    loss_last = (timeline[-1] or {}).get("loss") if timeline else None
    speeds = [(t or {}).get("img_per_s") for t in timeline if (t or {}).get("img_per_s")]
    speed = f"{min(speeds)}–{max(speeds)} img/s" if speeds else "—"
    lines = [
        "| | |",
        "|---|---|",
        f"| command | `{command}` |",
        f"| epochs completed | **{num(epochs)} of {planned_epochs} planned** — "
        f"stopped: {run.get('stopped', 'by the author')} |",
        f"| steps completed | **{num(steps)} of {num(planned_steps)}** |",
        f"| train loss | {num(loss_first)} (epoch 0) → {num(loss_last)} "
        f"(epoch {len(timeline) - 1}) |",
        f"| speed | {speed} |",
        f"| checkpoint (not published) | `{run.get('checkpoint', '—')}` |",
        f"| source | `{source}` → `training_run` |",
    ]
    return "\n".join(lines)


def bench_values(report: dict) -> dict[str, str]:
    """Числа архивного бенчмарка базовой модели (полоса / кадр)."""
    modes = report.get("modes") or {}
    band = ((modes.get("band") or {}).get("full") or {}).get("metrics") or {}
    frame = ((modes.get("frame") or {}).get("full") or {}).get("metrics") or {}
    roi_band = band.get("roi_types") or {}
    roi_frame = frame.get("roi_types") or {}
    all_band = band.get("all_types") or {}
    return {
        "BAND_ACC_ROI": num(roi_band.get("acc_micro")),
        "FRAME_ACC_ROI": num(roi_frame.get("acc_micro")),
        "ALL_TYPES_BAND_ACC": num(all_band.get("acc_micro")),
        "N_ROI_TYPES": str(roi_band.get("types", "—")),
    }


def ppocrv6_card_values(args, info: dict, dataset_totals: dict | None) -> dict[str, str]:
    """Значения для шаблона карточки PP-OCRv6.

    Все числа — из ``reports/TRAINING_PPOCR_V6.json`` и
    ``reports/bench_models/ppocrv6-medium.json``. Если файла нет, плейсхолдер
    остаётся плейсхолдером и инструмент предупреждает: ничего не выдумывается.
    """
    dataset_repo = args.dataset_repo or "Titlehhhh/captchaocr-dataset"
    values: dict[str, str] = {
        "REPO_ID": args.repo_id,
        "DATASET_REPO": dataset_repo,
        "DATASET_URL": f"https://huggingface.co/datasets/{dataset_repo}",
        "BASE_MODEL": "PaddlePaddle/PP-OCRv6_medium_rec_safetensors",
        "BASE_MODEL_URL": ("https://huggingface.co/PaddlePaddle/"
                           "PP-OCRv6_medium_rec_safetensors"),
        "BASE_LICENCE": "Apache-2.0",
        "MODEL_CLASS": "PPOCRV6SmallRecForTextRecognition",
        "BACKBONE": "PP-LCNetV4",
        "N_PARAMS": "—",
        "HIDDEN_SIZE": "—",
        "HEAD_CLASSES": "—",
        "EPOCHS_COMPLETED": "—",
        "PLANNED_EPOCHS": "—",
        "STEPS_COMPLETED": "—",
        "PLANNED_STEPS": "—",
        "ZERO_STEP_MEDIAN": "—",
        "AFTER_MEDIAN": "—",
        "BEST_EPOCH": "—",
        "LAST_EVAL_EPOCH": "—",
        "LAST_EVAL_MEDIAN": "—",
        "TRAIN_RUN_BLOCK": "_(отчёт об обучении не найден)_",
        "ZERO_STEP_TABLE": "_(отчёт об обучении не найден)_",
    }
    if dataset_totals:
        values.update({
            "N_TYPES": str(dataset_totals.get("types", "—")),
            "N_SAMPLES": str(dataset_totals.get("samples", "—")),
            "N_PNG_FILES": str(dataset_totals.get("png_files", "—")),
            "N_PLUGINS": str(dataset_totals.get("plugins", "—")),
            "N_ROI_TYPES": str(dataset_totals.get("types_with_roi", "—")),
        })

    report = load_json_file(TRAINING_REPORT_JSON)
    if report:
        source = Path(os.path.relpath(TRAINING_REPORT_JSON, REPO_ROOT)).as_posix()
        model = report.get("model") or {}
        values["BASE_MODEL"] = model.get("repo") or values["BASE_MODEL"]
        values["BASE_MODEL_URL"] = f"https://huggingface.co/{values['BASE_MODEL']}"
        values["BASE_LICENCE"] = model.get("license") or values["BASE_LICENCE"]
        values["MODEL_CLASS"] = str(model.get("class") or "").split(".")[-1] \
            or values["MODEL_CLASS"]
        values["BACKBONE"] = model.get("backbone") or values["BACKBONE"]
        values["N_PARAMS"] = grouped_int(model.get("params"))
        values["HIDDEN_SIZE"] = num(model.get("hidden_size"))
        values["HEAD_CLASSES"] = grouped_int(model.get("head_out_channels"))
        zero = (report.get("zero_step") or {}).get("aggregate") or {}
        values["ZERO_STEP_MEDIAN"] = num(zero.get("exact_match_median"))
        run = report.get("training_run") or {}
        command = str(run.get("command") or "")
        match = re.search(r"--epochs\s+(\d+)", command)
        values["EPOCHS_COMPLETED"] = num(run.get("epochs_completed"))
        values["PLANNED_EPOCHS"] = match.group(1) if match else "—"
        values["STEPS_COMPLETED"] = num(run.get("steps_completed"))
        values["PLANNED_STEPS"] = num(run.get("planned_steps"))
        after = report.get("after_training") or {}
        values["AFTER_MEDIAN"] = num((after.get("aggregate") or {}).get("exact_match_median"))
        values["BEST_EPOCH"] = num(after.get("best_epoch"))
        last = after.get("last_evaluation") or {}
        values["LAST_EVAL_EPOCH"] = num(last.get("epoch"))
        values["LAST_EVAL_MEDIAN"] = num(last.get("exact_match_median"))
        values["TRAIN_RUN_BLOCK"] = train_run_block(report, source)
        values["ZERO_STEP_TABLE"] = zero_step_table(report)
    else:
        warn(f"Отчёт об обучении не прочитан ({TRAINING_REPORT_JSON}) — в карточке модели "
             f"останутся плейсхолдеры.")

    bench = load_json_file(BENCH_JSON)
    if bench:
        values.update(bench_values(bench))
    else:
        warn(f"Файл бенчмарка не прочитан ({BENCH_JSON}) — в карточке модели останутся "
             f"плейсхолдеры.")
    return values


def detect_model_template(args, info: dict) -> tuple[str, str]:
    """Выбрать шаблон карточки модели.

    Порядок: явный ``--template`` → ``model_type`` из ``config.json`` → вид ключей
    весов. Если тип определить не удалось, инструмент **останавливается**: молча
    выбрать шаблон CRNN значило бы затереть хорошую карточку PP-OCRv6.
    """
    choice = getattr(args, "template", "auto") or "auto"
    if choice != "auto":
        if choice not in MODEL_CARD_TEMPLATES:
            raise SystemExit(f"Неизвестный шаблон --template {choice!r}. "
                             f"Допустимо: auto, {', '.join(sorted(MODEL_CARD_TEMPLATES))}.")
        return choice, f"выбран флагом --template {choice}"

    model_type = str(info.get("model_type") or "").strip().lower()
    if model_type:
        flat = model_type.replace("_", "")
        if "ppocrv6" in flat:
            return "ppocrv6", f"model_type={model_type}"
        if model_type == "captha":
            return "crnn", f"model_type={model_type}"

    keys = list(info.get("state_keys") or [])
    joined = " ".join(keys)
    if "backbone." in joined or any(k.startswith("head.") for k in keys):
        return "ppocrv6", "ключи весов похожи на PP-OCRv6 (model.backbone.* / head.*)"
    if any(k.startswith("rnn.") or k == "fc.weight" for k in keys):
        return "crnn", "ключи весов похожи на наш CRNN (rnn.* / fc.weight)"

    raise SystemExit(
        "Не удалось определить тип модели — шаблон карточки не выбран.\n"
        "  Укажите шаблон явно: --template ppocrv6 или --template crnn.\n"
        "  (Это защита от перезаписи карточки PP-OCRv6 шаблоном CRNN.)")


def _round(value) -> str:
    """Число в карточке: округлить до 4 знаков, если это float."""
    if isinstance(value, float):
        return f"{round(value, 4)}"
    return str(value)


def extract_results(path: Path | None) -> tuple[str, str]:
    """Достать честные метрики из файла результатов.

    Возвращает (блок markdown, предупреждение). Если файла нет или в нём нет
    знакомых ключей — возвращается явный плейсхолдер, а не выдуманные числа.
    """
    placeholder = (
        "**Метрики не указаны.** Файл результатов не передан (`--results`) или в нём "
        "нет знакомых полей. Числа ниже **не выдуманы** — их нужно вписать вручную "
        "после замера.\n\n"
        "| метрика | значение |\n|---|---|\n"
        "| exact match | — |\n| CER | — |\n| число сэмплов | — |"
    )
    if path is None:
        return placeholder, ("Файл результатов не передан (--results): метрики в карточке "
                             "оставлены плейслдером.")
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError) as exc:
        return placeholder, (f"Не удалось прочитать файл результатов {path}: "
                             f"{type(exc).__name__}: {exc}")

    overall = data.get("overall") if isinstance(data, dict) else None
    per_type = data.get("per_type") if isinstance(data, dict) else None
    if not isinstance(overall, dict):
        overall = data if isinstance(data, dict) else {}

    def _pick(*names):
        for name in names:
            if name in overall and overall[name] is not None:
                return overall[name]
        return None

    exact = _pick("exact", "exact_match", "accuracy", "acc")
    cer = _pick("cer", "mean_cer", "CER")
    n = _pick("n", "n_samples", "count", "total")

    if exact is None and cer is None:
        return placeholder, (f"В файле результатов {path} не найдено полей exact/cer — "
                             f"метрики оставлены плейслдером.")

    lines = ["| метрика | значение |", "|---|---|"]
    if n is not None:
        lines.append(f"| число сэмплов | {n} |")
    if exact is not None:
        lines.append(f"| exact match | {_round(exact)} |")
    if cer is not None:
        lines.append(f"| CER | {_round(cer)} |")
    if isinstance(per_type, dict) and per_type:
        lines.append(f"| типов в отчёте | {len(per_type)} |")
    block = "\n".join(lines) + f"\n\nИсточник: `{path.name}` (файл передан через `--results`)."
    return block, ""


