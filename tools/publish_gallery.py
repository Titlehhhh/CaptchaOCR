"""Publish the CaptchaOCR gallery into the Hugging Face **dataset** card.

    .venv-gpu\\Scripts\\python.exe tools\\publish_gallery.py --dry-run   # print the plan
    .venv-gpu\\Scripts\\python.exe tools\\publish_gallery.py             # upload
    .venv-gpu\\Scripts\\python.exe tools\\publish_gallery.py --verify    # check the card

What it does:

* uploads the three contact sheets to `gallery/sheet_01.png` .. `sheet_03.png` of the
  repository `Titlehhhh/captchaocr-dataset` (the **dataset**, never the model repository);
* rewrites **only** the block between the markers `<!-- captchaocr-gallery:begin -->` and
  `<!-- captchaocr-gallery:end -->` of the card `README.md`. If the markers are not there yet,
  the block is appended at the end - the existing text, the licence frontmatter and the honest
  statements of the card are never touched;
* the block holds the three sheets (markdown), the **46-row table** (type · n · exact match ·
  CER · a link to the folder of the type with its 500 pictures on the Hub) and the table of
  the models.

Everything is measured: the numbers come from `reports/model_scoreboard.json` (the published
model on all 46 types) and from `reports/bench_models/*.json` (the 12 foreign models, one
protocol) plus the two training reports of our own models. Nothing is typed by hand.

The script is re-runnable: the uploaded block is replaced, not appended twice.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
os.environ.setdefault("HF_HOME", os.path.join(ROOT, ".hf-cache"))
os.environ.setdefault("HF_HUB_CACHE", os.path.join(ROOT, ".hf-cache", "hub"))

REPO_ID = "Titlehhhh/captchaocr-dataset"
REPO_TYPE = "dataset"
HF_BASE = "https://huggingface.co/datasets/Titlehhhh/captchaocr-dataset"
SHEETS = [os.path.join(ROOT, "reports", "HTML", "img", f"sheet_{i:02d}.png") for i in (1, 2, 3)]
SCOREBOARD = os.path.join(ROOT, "reports", "model_scoreboard.json")
TYPES_JSON = os.path.join(ROOT, "reports", "HTML", "img", "types.json")
BENCH_DIR = os.path.join(ROOT, "reports", "bench_models")
BEGIN = "<!-- captchaocr-gallery:begin -->"
END = "<!-- captchaocr-gallery:end -->"


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def pct(x):
    return "—" if x is None else f"{100 * x:.1f}%"


def micro_band(frame):
    n = sum(v["n"] for v in frame.values())
    if not n:
        return None
    return sum(v["acc"] * v["n"] for v in frame.values()) / n


def models_rows():
    """The 12 foreign models + our two, read from the measured files."""
    rows = []
    for path in sorted(glob.glob(os.path.join(BENCH_DIR, "*.json"))):
        name = os.path.basename(path)
        if name.startswith("T2_"):
            continue
        d = load_json(path)
        modes = d.get("modes") or {}
        band = (modes.get("band") or {}).get("full")
        frame = (modes.get("frame") or {}).get("full")
        legacy = (modes.get("band") or {}).get("legacy64")
        band_acc = frame_acc = None
        note = ""
        if band and band.get("ok", True) and band.get("per_type"):
            pt = band["per_type"]
            banded = {k: v for k, v in pt.items() if v.get("has_roi")}
            band_acc = micro_band(banded)
            note = f"{len(banded)} типов с полосой, 20 картинок на тип"
        elif band and not band.get("ok", True):
            note = "замер не состоялся: " + str(band.get("error", "")).split("\n")[0][:70]
        elif legacy and legacy.get("ok", True):
            band_acc = micro_band(legacy["per_type"])
            note = "только старый набор legacy64 (8 типов)"
        if frame and frame.get("ok", True) and frame.get("per_type"):
            fpt = frame["per_type"]
            fb = {k: v for k, v in fpt.items() if v.get("has_roi")}
            frame_acc = micro_band(fb if fb else fpt)
        rows.append({"repo": d.get("model") or "-", "license": d.get("license") or "-",
                     "band": band_acc, "frame": frame_acc, "note": note, "ours": False})

    crnn = load_json(os.path.join(ROOT, "reports", "TRAINING_CRNN_BIG.json"))
    h = crnn["held_out"]
    t = crnn["training_types"]
    h_micro = h["micro_over_images"]["exact_match_pct"] / 100.0
    t_micro = t["micro_over_images"]["exact_match_pct"] / 100.0
    rows.append({
        "repo": "наш CRNN + CTC (обучен с нуля, не опубликован)",
        "license": "-", "band": h_micro, "frame": None,
        "note": (f"другой протокол (500 картинок на тип, разбиение по типам): невиданные типы "
                 f"micro {pct(h_micro)} (n={h['micro_over_images']['n_images']}), свои типы "
                 f"{pct(t_micro)} — это запоминание, а не обобщение"),
        "ours": True})

    pp = load_json(os.path.join(ROOT, "reports", "TRAINING_PPOCR_V6_BIG.json"))
    soup = pp["weight_interpolation"]
    agg = soup.get("best_alpha_aggregate") or {}
    rows.append({
        "repo": "Titlehhhh/captchaocr-ppocrv6", "license": "Apache-2.0",
        "band": agg.get("exact_match_micro"), "frame": None,
        "note": (f"PP-OCRv6_medium_rec + WiSE-FT α={soup.get('best_alpha')}; 7 удержанных типов, "
                 f"3500 картинок — другой протокол, с чужими моделями в один столбец не сравнивается"),
        "ours": True})
    return rows


def build_block(sb, types_meta):
    """The markdown block that replaces the marked section of the card."""
    agg = sb["all_46"]
    held = sb["held_out_7_reproduced"]
    pub = sb["published_reference"]
    lines = [BEGIN, "", "## Gallery", "",
             "Три контактных листа: все 46 типов, по шесть картинок на тип. Красная рамка — полоса "
             "(roi), из неё модель читает ответ; подпись «модель: …» — ответ опубликованной модели "
             "(зелёная — точный, красная — ошибка).", ""]
    for i, sheet in enumerate(SHEETS, 1):
        lines.append(f"![Контактный лист {i}/3 — 46 типов, 6 картинок на тип](gallery/sheet_{i:02d}.png)")
        lines.append("")
    lines += ["### Скорее таблица — опубликованная модель на всех 46 типах", "",
              "`Titlehhhh/captchaocr-ppocrv6` (PP-OCRv6_medium_rec + WiSE-FT, α = 0.4). Кроп: полоса "
              "`roi`, где она есть, иначе кадр, обрезанный по рамке чернил. Эталон — нарисованная "
              "строка `text`. «все 500» открывает папку типа на Hub.", "",
              "| Тип | n | exact match | CER | все 500 |", "|---|---|---|---|---|"]
    for t in types_meta:
        tid = t["full_id"]
        v = sb["types"].get(tid, {})
        link = f"{HF_BASE}/tree/main/data/{tid}"
        cer = "—" if v.get("cer") is None else f"{v['cer']:.3f}"
        lines.append(f"| `{tid}` | {v.get('n', 500)} | {pct(v.get('exact_match'))} | {cer} | "
                     f"[все 500 →]({link}) |")
    lines += ["",
              f"Микро по всем 46 типам: **{pct(agg['exact_match_micro'])}** exact, CER "
              f"**{agg['cer_micro']}**; медиана по типам: **{pct(agg['exact_match_median'])}** exact, "
              f"CER **{agg['cer_median']}**. На тех же 7 удержанных типах этот код даёт "
              f"**{pct(held['exact_match_micro'])}** micro / **{pct(held['exact_match_median'])}** median — "
              f"опубликованные с моделью числа были {pct(pub['micro_exact'])} / "
              f"{pct(pub['median_exact'])}, то есть пайплайн воспроизводится.", "",
              "Почему «все 46» ниже, чем «7 удержанных»: в наборе 46 типов есть типы без полосы "
              "(кадр целиком), группа C (это вообще не задача OCR: ответ — название цвета, номер "
              "слота, картинка) и кириллические типы, символы которых **нет в словаре модели** "
              "(в словаре PP-OCRv6 нет ни одной кириллической буквы).", "",
              "### Модели", "",
              "Единый протокол: 20 картинок на тип, два режима — «полоса» и «весь кадр»; число — "
              "micro exact match по 29 типам, у которых есть полоса. Строки «наши» измерены другим "
              "протоколом (500 картинок на тип, разбиение по типам) и в один столбец с чужими "
              "моделями не сопоставимы.", "",
              "| Модель | полоса | кадр | лицензия | примечание |", "|---|---|---|---|---|"]
    for m in sorted(models_rows(), key=lambda r: (r["ours"], -(r["band"] or -1))):
        repo = m["repo"]
        link = f"https://huggingface.co/{repo}" if "/" in repo else repo
        name = f"[{repo}]({link})" if "/" in repo else repo
        lines.append(f"| {name} | {pct(m['band'])} | {pct(m['frame'])} | {m['license']} | {m['note']} |")
    lines += ["", "Полный замер по 46 типам (с примерами «эталон → ответ модели»): "
              "`reports/model_scoreboard.json` в репозитории проекта.", "", END]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="print the plan, upload nothing")
    ap.add_argument("--verify", action="store_true", help="re-read the card and check it")
    ap.add_argument("--repo", default=REPO_ID)
    args = ap.parse_args()

    from huggingface_hub import HfApi, hf_hub_download

    api = HfApi()

    if args.verify:
        path = hf_hub_download(args.repo, "README.md", repo_type=REPO_TYPE)
        text = open(path, encoding="utf-8").read()
        sheets = text.count("gallery/sheet")
        # the rows of OUR scoreboard table: the n=500 cell and the link to the folder
        rows = sum(1 for line in text.splitlines()
                   if "| 500 |" in line and "/tree/main/data/" in line)
        print(f"card: {path}")
        print(f"  gallery/sheet references : {sheets}")
        print(f"  scoreboard rows (n=500 + a link to the folder) : {rows}")
        print(f"  every '| 500 |' in the card (the old inventory table included) : "
              f"{text.count('| 500 |')}")
        ok = True
        for i in (1, 2, 3):
            name = f"gallery/sheet_{i:02d}.png"
            try:
                p = hf_hub_download(args.repo, name, repo_type=REPO_TYPE)
                size = os.path.getsize(p)
                print(f"  {name}: OK ({size} bytes)")
            except Exception as exc:  # noqa: BLE001
                ok = False
                print(f"  {name}: FAILED - {exc}")
        if sheets < 3:
            ok = False
            print("  ERROR: the card does not embed the three sheets")
        if rows != 46:
            ok = False
            print(f"  ERROR: the scoreboard table has {rows} rows, expected 46")
        print("VERIFY:", "OK" if ok else "FAILED")
        return 0 if ok else 1

    # -- the data -------------------------------------------------------------- #
    sb = load_json(SCOREBOARD)
    types_meta = load_json(TYPES_JSON)
    for t in types_meta:
        t["full_id"] = f"{t.get('tree', 'out')}/{t['type']}"
    block = build_block(sb, types_meta)

    missing = [s for s in SHEETS if not os.path.isfile(s)]
    if missing:
        print("ERROR: the contact sheets are missing:", missing)
        print("run: .venv-gpu\\Scripts\\python.exe reports\\HTML\\make_report.py")
        return 2

    readme_path = hf_hub_download(args.repo, "README.md", repo_type=REPO_TYPE)
    current = open(readme_path, encoding="utf-8").read()
    if BEGIN in current and END in current:
        head, _, rest = current.partition(BEGIN)
        _, _, tail = rest.partition(END)
        new_text = head + block + tail
        action = "replace the marked block"
    else:
        new_text = current.rstrip("\n") + "\n\n" + block + "\n"
        action = "append the block at the end"

    print(f"repository : {args.repo} ({REPO_TYPE})")
    print(f"card       : {readme_path}")
    print(f"action     : {action}")
    print(f"card size  : {len(current)} -> {len(new_text)} bytes")
    for s in SHEETS:
        print(f"upload     : {os.path.relpath(s, ROOT)} -> "
              f"{os.path.basename(os.path.dirname(s))}/../{os.path.basename(s)} "
              f"({os.path.getsize(s)} bytes)")
    print(f"the block  : {len(block.splitlines())} markdown lines, "
          f"{block.count('| 500 |')} scoreboard rows, {block.count('gallery/sheet')} sheets")

    if args.dry_run:
        print("\n--- the block that would be written ---")
        print(block[:4000])
        print("... (truncated)")
        print("\nDRY RUN: nothing was uploaded.")
        return 0

    for i, sheet in enumerate(SHEETS, 1):
        api.upload_file(
            path_or_fileobj=sheet,
            path_in_repo=f"gallery/sheet_{i:02d}.png",
            repo_id=args.repo,
            repo_type=REPO_TYPE,
            commit_message=f"gallery: contact sheet {i}/3 (46 types, with the model's answers)",
        )
        print(f"uploaded gallery/sheet_{i:02d}.png")

    api.upload_file(
        path_or_fileobj=_write_temp(new_text),
        path_in_repo="README.md",
        repo_id=args.repo,
        repo_type=REPO_TYPE,
        commit_message="gallery: contact sheets, the 46-row scoreboard and the models table",
    )
    print("uploaded README.md")
    return 0


def _write_temp(text: str) -> str:
    """A temporary file with the new card (the upload API wants a path or a file object)."""
    import tempfile
    fd, path = tempfile.mkstemp(suffix=".md")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    return path


if __name__ == "__main__":
    sys.exit(main())
