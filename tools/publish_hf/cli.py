import argparse
import json
import shutil
from pathlib import Path

from .auth import resolve_token
from .cards import dataset_card_values, render_dataset_license, render_template
from .check import check_repo
from .constants import DATASET_CARD_TEMPLATE, EXIT_ERROR, EXIT_OK, MODEL_CARD_TEMPLATES, REPO_ROOT
from .dataset import build_inventory, collect_type, find_type_dirs
from .model import collect_model, model_card_values, upload_model
from .results import detect_model_template, extract_results, ppocrv6_card_values
from .upload import upload_dataset
from .utils import human_bytes, log, warn

# =====================================================================================
# CLI
# =====================================================================================

def build_parser() -> argparse.ArgumentParser:
    """Разобрать аргументы командной строки."""
    parser = argparse.ArgumentParser(
        prog="publish_hf.py",
        description="Публикация датасета и модели CaptchaOCR на Hugging Face Hub.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Примеры:\n"
            "  publish_hf.py dataset --repo-id user/repo --data-dir dataset --dry-run\n"
            "  publish_hf.py dataset --repo-id user/repo --data-dir dataset\n"
            "  publish_hf.py model --repo-id user/model --checkpoint train/run/main\n"
            "  publish_hf.py check --repo-id user/repo\n"
        ),
    )
    parser.add_argument("--token", default=None,
                        help="токен Hugging Face (по умолчанию $HF_TOKEN или токен CLI)")
    sub = parser.add_subparsers(dest="command", required=True)

    ds = sub.add_parser("dataset", help="выложить датасет")
    ds.add_argument("--repo-id", required=True, help="id репозитория, напр. user/repo")
    ds.add_argument("--data-dir", default=str(REPO_ROOT / "dataset"),
                    help="каталог с деревьями датасета (по умолчанию dataset)")
    ds.add_argument("--dry-run", action="store_true",
                    help="только показать план, ничего не отправляя")
    ds.add_argument("--private", action="store_true", help="создать приватный репозиторий")
    ds.add_argument("--confirm-create", action="store_true",
                    help="разрешить создание репозитория в чужом namespace")
    ds.add_argument("--include-external-url", action="store_true",
                    help="включить типы, у которых source указывает на внешний URL "
                         "(по умолчанию они исключены — правила проекта их не публикуют)")

    md = sub.add_parser("model", help="выложить модель")
    md.add_argument("--repo-id", required=True, help="id репозитория модели")
    md.add_argument("--checkpoint", required=True,
                    help="каталог с чекпоинтом или сам файл .pt")
    md.add_argument("--results", default=None,
                    help="JSON с результатами замера для карточки")
    md.add_argument("--dataset-repo", default=None,
                    help="id репозитория датасета (для ссылки в карточке)")
    md.add_argument("--data-dir", default=None,
                    help="каталог датасета — из него берётся размер обучающей выборки")
    md.add_argument("--image-height", type=int, default=48, help="высота входа модели")
    md.add_argument("--image-width", type=int, default=320, help="ширина входа модели")
    md.add_argument("--mean", type=float, default=0.5, help="mean препроцессора")
    md.add_argument("--std", type=float, default=0.5, help="std препроцессора")
    md.add_argument("--dry-run", action="store_true",
                    help="только показать план, ничего не отправляя")
    md.add_argument("--template", default="auto",
                    choices=["auto", "ppocrv6", "crnn"],
                    help="шаблон карточки модели: auto (по model_type/ключам весов, "
                         "по умолчанию), ppocrv6 — tools/hf_model_card.md, "
                         "crnn — tools/hf_model_card_crn.md")
    md.add_argument("--private", action="store_true", help="создать приватный репозиторий")
    md.add_argument("--confirm-create", action="store_true",
                    help="разрешить создание репозитория в чужом namespace")

    ck = sub.add_parser("check", help="проверить содержимое репозитория")
    ck.add_argument("--repo-id", required=True, help="id репозитория")
    ck.add_argument("--repo-type", default="dataset", choices=["dataset", "model"],
                    help="тип репозитория")
    return parser


def cmd_dataset(args) -> int:
    """Команда dataset."""
    data_dir = Path(args.data_dir).resolve()
    if not data_dir.is_dir():
        raise SystemExit(f"Каталог с данными не найден: {data_dir}")

    types = find_type_dirs(data_dir)
    if not types:
        raise SystemExit(f"В {data_dir} не найдено ни одного labels.jsonl — "
                         f"данные не собраны.")
    for t in types:
        collect_type(t)

    # По правилам проекта (AGENTS.md §8) материалы сторонних коммерческих сервисов
    # не публикуются. Признак такого происхождения выводится из самих `labels.jsonl`:
    # тип исключается, только если его `source` указывает на внешний URL (схема
    # http(s):// или доменное имя). Собственные рендеры наших генераторов — в том числе
    # чисто-румные реконструкции, собранные по референсным скриншотам, — внешнего URL
    # не содержат и публикуются. Имён типов в скрипте нет: переименование каталога
    # ничего в этом правиле не ломает.
    external = [t for t in types if t.inventory["external_url"]]
    if external:
        log(f"Типы с внешним URL в source: {len(external)} — "
            + ", ".join(t.type_id for t in external))
        if args.include_external_url:
            warn("Флаг --include-external-url: эти типы попадут в публикацию. "
                 "Убедитесь, что это допустимо по правилам проекта.")
        else:
            log("По правилам проекта материалы, взятые с чужого сайта, "
                "не публикуются — эти типы ИСКЛЮЧЕНЫ из загрузки.")
            log("Чтобы всё же включить их (осознанно), добавьте --include-external-url.")
            types = [t for t in types if not t.inventory["external_url"]]

    inventory = build_inventory(types, data_dir)

    template = DATASET_CARD_TEMPLATE.read_text(encoding="utf-8")
    card, leftovers = render_template(template, dataset_card_values(inventory, args.repo_id))
    if leftovers:
        warn("В шаблоне карточки остались неподставленные плейсхолдеры: "
             + ", ".join(leftovers))

    license_text, license_leftovers = render_dataset_license(inventory, args.repo_id)
    if license_leftovers:
        warn("В шаблоне файла лицензии остались неподставленные плейсхолдеры: "
             + ", ".join(license_leftovers))

    totals = inventory["totals"]
    log("=== План загрузки датасета ===")
    log(f"  репозиторий:      {args.repo_id} (dataset)")
    log(f"  каталог данных:   {inventory['data_dir']}")
    log(f"  раскладка в репо: {inventory['layout']}")
    log(f"  деревьев:         {totals['trees']}  ({', '.join(t['tree'] for t in inventory['trees'])})")
    log(f"  типов:            {totals['types']}")
    log(f"  плагинов:         {totals['plugins']}")
    log(f"  сэмплов (строк):  {totals['samples']}")
    log(f"  PNG-файлов:       {totals['png_files']}")
    log(f"  меток labels.jsonl: {totals['types']}")
    log(f"  суммарный размер: {human_bytes(totals['bytes'])} ({totals['bytes']} Б)")
    log(f"  типов с полосой:  {totals['types_with_roi']} "
        f"(строк с roi: {totals['rows_with_roi']}, без: {totals['rows_without_roi']})")
    log(f"  типов text != answer: {totals['types_text_ne_answer']}")
    log(f"  режимы: faithful {totals['types_faithful']}, clean-room "
        f"{totals['types_clean_room']}, reconstructed {totals['types_reconstructed']}, "
        f"не определён {totals['types_mode_unknown']}")
    log(f"  размер карточки:  {len(card.encode('utf-8'))} Б")
    log(f"  размер LICENSE:   {len(license_text.encode('utf-8'))} Б")
    log(f"  размер инвентаря: {len(json.dumps(inventory, ensure_ascii=False).encode('utf-8'))} Б")
    log("  первые файлы:")
    shown = 0
    for t in types:
        for png in t.pngs[:1]:
            log(f"    {t.repo_dir()}/{png.name}")
            shown += 1
            break
        if shown >= 8:
            break
    log(f"    ... и ещё {max(0, totals['png_files'] + totals['types'] + 2 - shown)} файлов")

    if args.dry_run:
        log("")
        log("--dry-run: ничего не отправлял, сеть не трогал.")
        token = resolve_token(args.token)
        if not token:
            log("")
            log("Токен не найден — для реальной загрузки понадобится:")
            log("  $env:HF_TOKEN = \"hf_...\"   или   .venv-gpu\\Scripts\\hf.exe auth login")
        return EXIT_OK

    uploaded = upload_dataset(args, inventory, card, types, license_text)
    log(f"Готово: загружено {uploaded} файлов в {args.repo_id}.")
    return EXIT_OK


def cmd_model(args) -> int:
    """Команда model."""
    meta, files, staging = collect_model(args)
    info = meta["info"]
    try:
        results_block, results_warning = extract_results(
            Path(args.results) if args.results else None)
        info["results_block"] = results_block
        info["results_warning"] = results_warning

        # Шаблон карточки выбирается по типу модели (model_type / ключи весов) или
        # флагом --template. Молча взять шаблон CRNN нельзя: это затрёт карточку
        # PP-OCRv6. Если тип определить не удалось — инструмент останавливается.
        template_key, template_reason = detect_model_template(args, info)
        template_path = MODEL_CARD_TEMPLATES[template_key]

        # Сводка по датасету — для чисел карточки (типы, сэмплы, плагины).
        dataset_totals: dict | None = None
        data_dir = Path(args.data_dir).resolve() if args.data_dir \
            else (REPO_ROOT / "dataset")
        if data_dir.is_dir():
            types = find_type_dirs(data_dir)
            for t in types:
                collect_type(t)
            inv = build_inventory(types, data_dir)
            dataset_totals = inv["totals"]
            info["n_train_types"] = str(inv["totals"]["types"])
            info["n_train_samples"] = str(inv["totals"]["samples"])
        else:
            warn(f"Каталог {data_dir} не найден — числа датасета в карточке не указаны.")

        if template_key == "ppocrv6":
            info["card_values"] = ppocrv6_card_values(args, info, dataset_totals)
        else:
            info["card_values"] = {
                "DATASET_URL": (f"https://huggingface.co/datasets/{args.dataset_repo}"
                                if args.dataset_repo else "не указан"),
            }

        template = template_path.read_text(encoding="utf-8")
        card, leftovers = render_template(template, model_card_values(args, info))
        if leftovers:
            warn("В шаблоне карточки остались неподставленные плейсхолдеры: "
                 + ", ".join(leftovers))
        if results_warning:
            warn(results_warning)

        log("=== План загрузки модели ===")
        log(f"  репозиторий:      {args.repo_id} (model)")
        log(f"  шаблон карточки:  {template_path.name} ({template_reason})")
        log(f"  чекпоинт:         {info.get('checkpoint')}")
        log(f"  веса:             {info.get('weights_source', 'model.safetensors')}")
        log(f"  config.json:      {info.get('config_source')}")
        log(f"  preprocessor:      {info.get('preprocessor_source')}")
        log(f"  character_list:   {info.get('character_list_source')}")
        log(f"  классов:          {info.get('num_classes', 'не выведено')}")
        log(f"  charset:          {info.get('charset') or 'не указан'}")
        log(f"  вход:             {info.get('image_height')}x{info.get('image_width')}, "
            f"mean={info.get('image_mean')}, std={info.get('image_std')}")
        for rel in info.get("extra_files", []):
            log(f"  дополнительно:    {rel}")
        total = sum(p.stat().st_size for _, p in files)
        log(f"  файлов к загрузке: {len(files) + 3}")
        log(f"  суммарный размер: {human_bytes(total)}")

        if args.dry_run:
            log("")
            log("--dry-run: ничего не отправлял, сеть не трогал.")
            token = resolve_token(args.token)
            if not token:
                log("")
                log("Токен не найден — для реальной загрузки понадобится:")
                log("  $env:HF_TOKEN = \"hf_...\"   или   .venv-gpu\\Scripts\\hf.exe auth login")
            return EXIT_OK

        uploaded = upload_model(args, meta, files, card)
        log(f"Готово: загружено {uploaded} файлов в {args.repo_id}.")
        return EXIT_OK
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    """Точка входа."""
    args = build_parser().parse_args(argv)
    if args.command == "dataset":
        return cmd_dataset(args)
    if args.command == "model":
        return cmd_model(args)
    if args.command == "check":
        return check_repo(args)
    return EXIT_ERROR


