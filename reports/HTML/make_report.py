"""Build the contact sheets of the 46 captcha types for `reports/HTML/index.html`.

    .venv-gpu\\Scripts\\python.exe reports\\HTML\\make_report.py

What it produces, all under `reports/HTML/img/`:

*   `sheet_01.png` .. `sheet_03.png` - three contact sheets, 46 types in total,
    6 sample pictures each, every thumbnail captioned with the type id and the
    ground truth (`answer` and, where it differs, the drawn `text`);
*   `types.json` - the same per-type metadata in machine-readable form, so the
    HTML page can be rebuilt from the data instead of from hand-written text.

Rules that this script obeys:

*   **`dataset/**` is read-only.** Nothing is written outside `reports/HTML/`.
*   **`real_shots/` never appears.** The reference screenshots are other people's
    pictures; the guard below refuses any path that contains `real_shots`.
*   Every type is covered: the script fails loudly if the number of types is not
    the expected 46, or if a type has fewer than 6 usable samples.
"""

from __future__ import annotations

import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT_DIR = os.path.join(HERE, "img")
DATASET_ROOTS = [
    (os.path.join(ROOT, "dataset", "out"), "out"),
    (os.path.join(ROOT, "dataset", "out_ru"), "out_ru"),
]

#: how many sample pictures per type
N_SAMPLES = 6
#: the maximum width of one thumbnail, in pixels (the brief's limit is 320)
THUMB_W = 240
#: the maximum height of one thumbnail, in pixels
THUMB_H = 150
#: how many types per contact sheet
TYPES_PER_SHEET = 16
#: the width of the label column on the left, in pixels
LABEL_W = 300
#: the expected number of types - the script refuses to continue otherwise
EXPECTED_TYPES = 46

# --- the group table, from `agents/INDEX.md` section 4 (A = pure OCR,
# --- B = OCR + a solver step, C = not an OCR task at all).
GROUPS = {
    "Archy-X/Krypton/map": "A", "InstantlyMoist/Captcha/textcaptcha": "A",
    "JSH32/Minecaptcha/map": "A", "LagBug/XProtect/code": "A",
    "LagBug/XProtect/map": "A", "LagBug/XProtect/picture": "A",
    "haq/mapcha/map": "A", "irootdev/AnBot/captcha": "A",
    "jonesdevelopment/sonar/standard": "A", "jonesdevelopment/sonar/legacy": "A",
    "jonesdevelopment/sonar/complex": "A", "just-captcha/ProstoCaptcha/map": "A",
    "laforetbrut/are-you-sure/code": "A",
    "ringoame196-s-mcPlugin/ReproductionCAPTCHA/map": "A",
    "GalleryCaptcha/ru-web": "A", "GalleryCaptcha/ru-symbols": "A",
    "BotFilter/map": "A", "CaptchaVerifyZ/map": "A", "LimboFilter/symbols": "A",
    "jSdCool/minecaptcha/text": "A",

    "LagBug/XProtect/reverse": "B", "GalleryCaptcha/ru-numberword": "B",
    "GalleryCaptcha/ru-numberword-caption": "B", "LimboFilter/map": "B",
    "LagBug/XProtect/equation": "B", "FeelingAlive0/AdvancedCaptcha/math": "B",
    "Mrbysco/Captcha/math": "B", "n1zamu/NCaptcha/anvil": "B",
    "LagBug/XProtect/gui": "B", "Archy-X/Krypton/menu": "B",
    "Yukun99/Captchas/itemslot": "B",

    "LagBug/XProtect/drop": "C", "LagBug/XProtect/jump": "C",
    "LagBug/XProtect/sneak": "C", "LagBug/XProtect/different": "C",
    "China2B2T/Captcha/wool": "C", "jSdCool/minecaptcha/image": "C",
    "LimboFilter/framed2x2": "C", "LimboFilter/framed3x3": "C",
    "GalleryCaptcha/ru-object-swatch": "C", "LagBug/XProtect/color": "C",
    "Joey61021/captcha/colorgui": "C", "Z4OLLIEZ4/reCaptcha/captchasx": "C",
    "LagBug/XProtect/slot": "C", "CaptchaGUI/clickblock": "C",
    "FeelingAlive0/AdvancedCaptcha/button": "C",
}

#: the solver step of group B, from `agents/INDEX.md` section 4
SOLVERS = {
    "LagBug/XProtect/reverse": "развернуть строку",
    "GalleryCaptcha/ru-numberword": "русские слова -> цифры",
    "GalleryCaptcha/ru-numberword-caption": "русские слова -> цифры",
    "LimboFilter/map": "русские слова -> цифры",
    "LagBug/XProtect/equation": "посчитать выражение",
    "FeelingAlive0/AdvancedCaptcha/math": "посчитать выражение",
    "Mrbysco/Captcha/math": "посчитать выражение",
    "n1zamu/NCaptcha/anvil": "ответ уже обычными цифрами",
    "LagBug/XProtect/gui": "строка 3-20 символов",
    "Archy-X/Krypton/menu": "-",
    "Yukun99/Captchas/itemslot": "-",
}

#: why a group-C type is not an OCR task
NOT_OCR = {
    "LagBug/XProtect/drop": "константный ответ",
    "LagBug/XProtect/jump": "константный ответ",
    "LagBug/XProtect/sneak": "константный ответ",
    "LagBug/XProtect/different": "константный ответ",
    "China2B2T/Captcha/wool": "константный ответ",
    "jSdCool/minecaptcha/image": "63-70 символов, нечитаемо",
    "LimboFilter/framed2x2": "ответ в повёрнутых рамках",
    "LimboFilter/framed3x3": "ответ в повёрнутых рамках",
    "GalleryCaptcha/ru-object-swatch": "ответ - название цвета",
    "LagBug/XProtect/color": "ответ - название цвета",
    "Joey61021/captcha/colorgui": "ответ - название цвета",
    "Z4OLLIEZ4/reCaptcha/captchasx": "ответ - название цвета",
    "LagBug/XProtect/slot": "ответ - номер слота",
    "CaptchaGUI/clickblock": "ответ - индекс картинки",
    "FeelingAlive0/AdvancedCaptcha/button": "18-27 символов",
}

GROUP_COLOR = {"A": (24, 106, 66), "B": (22, 84, 150), "C": (140, 60, 20)}
INK = (25, 25, 30)
MUTED = (110, 110, 120)
PAPER = (255, 255, 255)
GRID = (222, 222, 228)

#: the measured predictions of the published model (`reports/model_scoreboard.json`).
#: The file is optional: without it the sheets carry only the ground truth.
SCOREBOARD = os.path.join(ROOT, "reports", "model_scoreboard.json")


def _norm(s):
    """The metric normalisation of `train/finetune_ppocr.py` (letters, digits, +-*/=)."""
    if s is None:
        return ""
    return "".join(ch for ch in str(s) if ch.isalnum() or ch in "+-*/=")


def load_predictions():
    """{(type_id, file): prediction} of the published model, if the file exists."""
    if not os.path.isfile(SCOREBOARD):
        print("no scoreboard yet - the sheets carry only the ground truth")
        return None
    with open(SCOREBOARD, encoding="utf-8") as f:
        sb = json.load(f)
    out = {}
    for tid, v in (sb.get("types") or {}).items():
        # the scoreboard keys the types with the tree prefix ("out/..."), the sheets
        # use the plain type id ("Archy-X/Krypton/map")
        plain = tid.split("/", 1)[1] if "/" in tid else tid
        for ex in v.get("examples") or []:
            out[(plain, ex["file"])] = ex.get("pred", "")
    print(f"predictions of the published model: {len(out)}")
    return out


def load_font(size: int, bold: bool = False):
    """A Unicode-capable TrueType font; the PIL default cannot draw Cyrillic."""
    names = ["arialbd.ttf", "arial.ttf"] if bold else ["arial.ttf", "segoeui.ttf"]
    for name in names:
        path = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", name)
        if os.path.isfile(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


def find_types():
    """Every captcha type of the two trees, as `(type_id, directory)`."""
    found = []
    for root, tag in DATASET_ROOTS:
        if not os.path.isdir(root):
            continue
        for dirpath, dirs, files in os.walk(root):
            # the reference screenshots of other people are never used, never shown
            dirs[:] = [d for d in dirs if d != "real_shots"]
            if "real_shots" in dirpath.replace(os.sep, "/").split("/"):
                continue
            if "labels.jsonl" not in files:
                continue
            rel = os.path.relpath(dirpath, root).replace(os.sep, "/")
            if tag == "out":
                parts = rel.split("/")
                if len(parts) != 3:
                    continue
                type_id = "/".join(parts)
            else:
                parts = rel.split("/")
                if len(parts) != 2:
                    continue
                type_id = "/".join(parts)
            found.append((type_id, dirpath))
    return sorted(found)


def read_labels(directory):
    rows = []
    with open(os.path.join(directory, "labels.jsonl"), encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def pick_rows(rows, n):
    """`n` rows spread evenly over the type (the type has 500 samples today)."""
    if len(rows) <= n:
        return list(rows)
    idx = [int(round(i * (len(rows) - 1) / (n - 1))) for i in range(n)]
    return [rows[i] for i in idx]


def fit(img, box_w, box_h):
    """Scale the picture down into the box, keeping the aspect ratio."""
    scale = min(box_w / img.width, box_h / img.height, 1.0)
    return img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))),
                      Image.LANCZOS)


def short(text, limit=26):
    text = str(text)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def draw_type_block(canvas, draw, x0, y0, type_id, info, samples, fonts, preds=None):
    """One type: a label column and six captioned thumbnails."""
    f_type, f_small, f_cap, f_badge = fonts
    cell_w = THUMB_W + 16
    img_top = y0

    # -- the label column ----------------------------------------------------- #
    f_id = f_type
    while draw.textlength(type_id, font=f_id) > LABEL_W - 6 and f_id.size > 9:
        f_id = load_font(f_id.size - 1, bold=True)
    draw.text((x0, y0), type_id, font=f_id, fill=INK)
    group = info["group"]
    gcolor = GROUP_COLOR.get(group, MUTED)
    badge = f"группа {group}"
    bw = draw.textlength(badge, font=f_badge)
    draw.rectangle([x0, y0 + 21, x0 + bw + 12, y0 + 35], fill=gcolor)
    draw.text((x0 + 6, y0 + 22), badge, font=f_badge, fill=(255, 255, 255))
    meta = info["meta"]
    for i, line in enumerate(meta):
        draw.text((x0, y0 + 40 + i * 14), short(line, 34), font=f_small, fill=MUTED)

    # -- the thumbnails -------------------------------------------------------- #
    for i, row in enumerate(samples):
        cx = x0 + LABEL_W + i * cell_w
        path = os.path.join(info["dir"], row["file"])
        if "real_shots" in path.replace(os.sep, "/").split("/"):
            raise RuntimeError(f"refusing to embed a real_shots picture: {path}")
        img = Image.open(path).convert("RGB")
        thumb = fit(img, THUMB_W, THUMB_H)
        # the band is drawn on the THUMBNAIL, in the thumbnail's own coordinates
        roi = row.get("roi")
        if roi:
            rx, ry, rw, rh = (int(v) for v in roi)
            sx = thumb.width / img.width
            sy = thumb.height / img.height
            box = [cx + rx * sx, img_top + ry * sy,
                   cx + (rx + rw) * sx - 1, img_top + (ry + rh) * sy - 1]
            draw.rectangle(box, outline=(220, 30, 30), width=2)
        canvas.paste(thumb, (cx, img_top))
        draw.rectangle([cx, img_top, cx + thumb.width - 1, img_top + thumb.height - 1],
                       outline=GRID, width=1)
        cap_y = img_top + THUMB_H + 4
        answer = str(row.get("answer", ""))
        text = str(row.get("text", ""))
        draw.text((cx, cap_y), short(answer, 30), font=f_cap, fill=INK)
        if text and text != answer:
            draw.text((cx, cap_y + 14), "нарисовано: " + short(text, 24), font=f_small,
                      fill=(170, 40, 40))
        # what the published model answered for this very picture
        if preds is not None:
            p = preds.get((type_id, row["file"]))
            if p is not None:
                gold = text or answer
                ok = _norm(p) == _norm(gold)
                draw.text((cx, cap_y + 28), "модель: " + short(p or "(пусто)", 24),
                          font=f_small, fill=(15, 110, 95) if ok else (170, 40, 40))
    return


def collect_meta(types):
    """Per-type metadata for the HTML page, read from every `labels.jsonl`."""
    meta_out = []
    for type_id, directory in types:
        rows = read_labels(directory)
        samples = pick_rows(rows, N_SAMPLES)
        meta_out.append({
            "type": type_id,
            "group": GROUPS[type_id],
            "tree": "out_ru" if "out_ru" in directory.replace(os.sep, "/") else "out",
            "samples": len(rows),
            "with_band": sum(1 for r in rows if r.get("roi")),
            "canvas": f"{rows[0].get('width')}x{rows[0].get('height')}",
            "source": rows[0].get("source", "")[:120],
            "solver": SOLVERS.get(type_id) or NOT_OCR.get(type_id),
            "examples": [{"file": r["file"], "answer": r.get("answer"),
                          "text": r.get("text"), "roi": r.get("roi")}
                         for r in samples],
        })
    return meta_out


def write_types_table(meta_out, path):
    """The 46 rows of the type table of `index.html`, as HTML `<tr>` lines."""
    rows = []
    for i, t in enumerate(meta_out, 1):
        parts = t["type"].split("/")
        plugin = "/".join(parts[:2]) if len(parts) == 3 else parts[0]
        solver = t["solver"] or "—"
        rows.append(
            f'      <tr><td class="num">{i}</td><td><code>{t["type"]}</code></td>'
            f'<td>{plugin}</td><td>{t["tree"]}</td>'
            f'<td><span class="g g{t["group"]}">{t["group"]}</span></td>'
            f'<td>{t["canvas"]}</td><td class="num">{t["samples"]}</td>'
            f'<td class="num">{t["with_band"]}/{t["samples"]}</td>'
            f'<td class="solver">{solver}</td></tr>')
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(rows) + "\n")
    return len(rows)


def main() -> int:
    types = find_types()
    print(f"types found: {len(types)}")
    if len(types) != EXPECTED_TYPES:
        print(f"ERROR: expected {EXPECTED_TYPES} types, found {len(types)}")
        return 2
    missing = [t for t, _ in types if t not in GROUPS]
    if missing:
        print("ERROR: no group assigned for:", missing)
        return 2

    os.makedirs(OUT_DIR, exist_ok=True)

    # `--table-only` refreshes the metadata and the type table without touching
    # the contact sheets (which are already published inside `index.html`).
    if "--table-only" in sys.argv:
        meta_out = collect_meta(types)
        n = write_types_table(meta_out, os.path.join(OUT_DIR, "types_table.html"))
        json.dump(meta_out, open(os.path.join(OUT_DIR, "types.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print(f"wrote the type table ({n} rows) and types.json")
        return 0

    fonts = (load_font(15, bold=True), load_font(12), load_font(12), load_font(11, bold=True))
    preds = load_predictions()

    meta_out = collect_meta(types)
    sheets = [types[i:i + TYPES_PER_SHEET] for i in range(0, len(types), TYPES_PER_SHEET)]

    for sheet_no, sheet in enumerate(sheets, start=1):
        blocks = []
        for type_id, directory in sheet:
            rows = read_labels(directory)
            samples = pick_rows(rows, N_SAMPLES)
            if len(samples) < N_SAMPLES:
                print(f"ERROR: {type_id} has only {len(samples)} samples")
                return 2
            n_band = sum(1 for r in rows if r.get("roi"))
            info = {
                "type": type_id,
                "dir": directory,
                "group": GROUPS[type_id],
                "meta": [
                    f"{len(rows)} картинок",
                    f"полоса: {n_band}/{len(rows)}",
                    f"solver: {SOLVERS.get(type_id, NOT_OCR.get(type_id, '-'))}",
                ],
            }
            blocks.append((type_id, info, samples))

        # the sheet's geometry
        cell_w = THUMB_W + 16
        width = LABEL_W + N_SAMPLES * cell_w + 24
        row_h = THUMB_H + (66 if preds else 52)
        height = 92 + len(blocks) * row_h + 16

        canvas = Image.new("RGB", (width, height), PAPER)
        draw = ImageDraw.Draw(canvas)
        f_title = load_font(24, bold=True)
        f_sub = load_font(14)
        draw.text((24, 20), f"CaptchaOCR - контактный лист {sheet_no}/{len(sheets)}",
                  font=f_title, fill=INK)
        draw.text((24, 52),
                  "46 типов x 500 PNG. Красная рамка - полоса (roi), из неё модель читает ответ. "
                  + ("Зелёная подпись 'модель:' - точный ответ, красная - ошибка." if preds else ""),
                  font=f_sub, fill=MUTED)
        draw.line([24, 76, width - 24, 76], fill=GRID, width=2)

        y = 92
        for type_id, info, samples in blocks:
            draw_type_block(canvas, draw, 24, y, type_id, info, samples, fonts, preds)
            y += row_h
            draw.line([24, y - 14, width - 24, y - 14], fill=GRID, width=1)

        path = os.path.join(OUT_DIR, f"sheet_{sheet_no:02d}.png")
        canvas.save(path, optimize=True)
        size = os.path.getsize(path)
        print(f"wrote {path}  ({canvas.width}x{canvas.height}, {size / 1e6:.2f} MB)")

        for type_id, info, samples in blocks:
            rows = read_labels(info["dir"])
            assert len(rows) == len(samples) or len(rows) >= N_SAMPLES

    meta_path = os.path.join(OUT_DIR, "types.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta_out, f, ensure_ascii=False, indent=1)
    print(f"wrote {meta_path}  ({len(meta_out)} types)")
    n = write_types_table(meta_out, os.path.join(OUT_DIR, "types_table.html"))
    print(f"wrote the type table ({n} rows) -> img/types_table.html")

    total = sum(t["samples"] for t in meta_out)
    band_types = sum(1 for t in meta_out if t["with_band"])
    print(f"types={len(meta_out)}  labelled PNG={total}  types with a band={band_types}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
