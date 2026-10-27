
from .constants import DATASET_LICENSE_TEMPLATE
from .utils import human_bytes


def render_template(template: str, values: dict[str, str]) -> tuple[str, list[str]]:
    out = template
    for key, value in values.items():
        out = out.replace("{" + key + "}", str(value))
    leftovers: list[str] = []
    rest = out
    while "{" in rest and "}" in rest:
        start = rest.index("{")
        end = rest.index("}", start)
        token = rest[start:end + 1]
        if token not in leftovers:
            leftovers.append(token)
        rest = rest[end + 1:]
    return out, leftovers


def type_table(inventory: dict) -> str:
    lines = ["| тип | дерево | PNG | с полосой | алфавит | длина text (мин/мед/макс) "
             "| уник. ответов | лицензия |",
             "|---|---|---|---|---|---|---|---|"]
    for t in inventory["types"]:
        tl = t["text_length"]
        lines.append(
            f"| `{t['type_id']}` | {t['tree']} | {t['png_files']} | "
            f"{t['rows_with_roi']}/{t['samples']} | {t['alphabet_kind']} "
            f"({t['alphabet_size']}) | {tl['min']}/{tl['median']:.0f}/{tl['max']} | "
            f"{t['unique_answers']} | {t['licence']} |")
    return "\n".join(lines)


def plugin_table(inventory: dict) -> str:
    lines = ["| плагин | типов | PNG | лицензия | режим |", "|---|---|---|---|---|"]
    for p in inventory["plugins"]:
        lines.append(f"| `{p['plugin']}` | {len(p['types'])} | {p['png_files']} | "
                     f"{p['licence']} | {p['mode']} |")
    return "\n".join(lines)


def tree_table(inventory: dict) -> str:
    lines = ["| дерево | типов | PNG | байт |", "|---|---|---|---|"]
    for t in inventory["trees"]:
        lines.append(f"| `{t['tree']}` | {t['types']} | {t['png_files']} | "
                     f"{human_bytes(t['bytes'])} |")
    return "\n".join(lines)


def alphabet_block(inventory: dict) -> str:
    lines = []
    for t in inventory["types"]:
        alphabet = t["alphabet"] or "(пусто)"
        lines.append(f"* `{t['type_id']}` — алфавит ({t['alphabet_size']} символов): "
                     f"`{alphabet}`")
    return "\n".join(lines)


def reconstructed_block(inventory: dict) -> str:
    lines = []
    for t in inventory["types"]:
        if t["mode"] == "faithful":
            continue
        lines.append(f"* `{t['type_id']}` — режим **{t['mode']}**, плагин `{t['plugin']}`; "
                     f"происхождение: {t['source']}")
    if not lines:
        return "_Все типы — faithful-порты апстримных алгоритмов._"
    return "\n".join(lines)


def dataset_card_values(inventory: dict, repo_id: str) -> dict[str, str]:
    totals = inventory["totals"]
    return {
        "REPO_ID": repo_id,
        "N_TYPES": str(totals["types"]),
        "N_SAMPLES": str(totals["samples"]),
        "N_PNG_FILES": str(totals["png_files"]),
        "N_PLUGINS": str(totals["plugins"]),
        "N_TREES": str(totals["trees"]),
        "N_TYPES_WITH_ROI": str(totals["types_with_roi"]),
        "N_ROWS_WITH_ROI": str(totals["rows_with_roi"]),
        "N_ROWS_WITHOUT_ROI": str(totals["rows_without_roi"]),
        "N_TYPES_TEXT_NE_ANSWER": str(totals["types_text_ne_answer"]),
        "N_FAITHFUL_TYPES": str(totals["types_faithful"]),
        "N_CLEAN_ROOM_TYPES": str(totals["types_clean_room"]),
        "N_RECONSTRUCTED_TYPES": str(totals["types_reconstructed"]),
        "ALPHABET_SIZE": str(totals["alphabet_size"]),
        "TOTAL_BYTES": str(totals["bytes"]),
        "TOTAL_BYTES_HUMAN": human_bytes(totals["bytes"]),
        "DATA_DIR": inventory["data_dir"],
        "LAYOUT": inventory["layout"],
        "TREE_TABLE": tree_table(inventory),
        "TYPE_TABLE": type_table(inventory),
        "PLUGIN_TABLE": plugin_table(inventory),
        "ALPHABET_LIST": alphabet_block(inventory),
        "RECONSTRUCTED_LIST": reconstructed_block(inventory),
    }


def licence_summary_block(inventory: dict) -> str:
    groups: dict[str, dict] = {}
    for p in inventory["plugins"]:
        entry = groups.setdefault(p["licence"], {"types": 0, "png": 0,
                                                  "plugins": []})
        entry["types"] += len(p["types"])
        entry["png"] += p["png_files"]
        entry["plugins"].append(p["plugin"])
    lines = ["| licence | upstream plugins | captcha types | PNG |",
             "|---|---|---|---|"]
    for licence in sorted(groups):
        entry = groups[licence]
        names = ", ".join(f"`{name}`" for name in sorted(entry["plugins"]))
        lines.append(f"| {licence} | {names} | {entry['types']} | {entry['png']} |")
    return "\n".join(lines)


def no_licence_note(inventory: dict) -> str:
    without = [p["plugin"] for p in inventory["plugins"]
               if "no licence" in p["licence"].lower()
               or "all rights reserved" in p["licence"].lower()
               or "не установлена" in p["licence"].lower()]
    if not without:
        return ("All upstream plugins in this dataset ship a licence, so no row is "
                "published without permission.")
    names = ", ".join(f"`{name}`" for name in sorted(without))
    return (f"Those rows ({names}) are published for research use; the upstream author "
            f"granted nothing, so no permission can be derived from this repository — "
            f"ask the upstream author before any other use.")


def agpl_note(inventory: dict) -> str:
    agpl = [p["plugin"] for p in inventory["plugins"]
            if "agpl" in p["licence"].lower()]
    if not agpl:
        return ("No upstream plugin in this dataset is licensed under AGPL, so the "
                "network-use obligation of the AGPL does not reach this dataset.")
    names = ", ".join(f"`{name}`" for name in sorted(agpl))
    return (f"**{names}**: the renders of these types reproduce the upstream algorithm, so "
            f"the AGPL-3.0 terms of the upstream plugin apply to those rows — including the "
            f"requirement to offer the corresponding source to users of a network service. "
            f"The upstream notice must be kept.")


def dataset_license_values(inventory: dict, repo_id: str) -> dict[str, str]:
    values = dataset_card_values(inventory, repo_id)
    values.update({
        "LICENCE_SUMMARY": licence_summary_block(inventory),
        "NO_LICENCE_NOTE": no_licence_note(inventory),
        "AGPL_NOTE": agpl_note(inventory),
    })
    return values


def render_dataset_license(inventory: dict, repo_id: str) -> tuple[str, list[str]]:
    template = DATASET_LICENSE_TEMPLATE.read_text(encoding="utf-8")
    return render_template(template, dataset_license_values(inventory, repo_id))
