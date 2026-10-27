import os
import sys

import torch

from .templates_card import MODEL_CARD_TEMPLATE


PLUGINS = {
    "LagBug/XProtect": ("LagBug/XProtect", "MIT", "faithful"),
    "jonesdevelopment/sonar": ("jonesdevelopment/sonar", "GPL-3.0", "clean-room"),
    "Archy-X/Krypton": ("Archy-X/Krypton", "no licence (all rights reserved)", "clean-room"),
    "FeelingAlive0/AdvancedCaptcha": ("FeelingAlive0/AdvancedCaptcha", "MIT", "faithful"),
    "jSdCool/minecaptcha": ("jSdCool/minecaptcha", "CC0-1.0", "faithful"),
    "Z4OLLIEZ4/reCaptcha": ("Z4OLLIEZ4/reCaptcha", "MIT", "faithful"),
    "Joey61021/captcha": ("Joey61021/captcha", "MIT", "faithful"),
    "laforetbrut/are-you-sure": ("laforetbrut/are-you-sure", "MIT", "faithful"),
    "Mrbysco/Captcha": ("Mrbysco/Captcha", "MIT", "faithful"),
    "Yukun99/Captchas": ("Yukun99/Captchas", "no licence (all rights reserved)", "clean-room"),
    "China2B2T/Captcha": ("China2B2T/Captcha", "GPL-3.0", "clean-room"),
    "InstantlyMoist/Captcha": ("InstantlyMoist/Captcha", "MIT", "faithful"),
    "JSH32/Minecaptcha": ("JSH32/Minecaptcha", "MIT", "faithful"),
    "haq/mapcha": ("haq/mapcha", "MIT", "faithful"),
    "just-captcha/ProstoCaptcha": ("just-captcha/ProstoCaptcha", "MIT", "faithful"),
    "irootdev/AnBot": ("irootdev/AnBot", "GPL-3.0", "clean-room"),
    "ringoame196-s-mcPlugin/ReproductionCAPTCHA": (
        "ringoame196-s-mcPlugin/ReproductionCAPTCHA",
        "no licence file (all rights reserved)", "clean-room"),
    "n1zamu/NCaptcha": ("n1zamu/NCaptcha", "MIT", "faithful"),
    "Elytrium/LimboFilter": ("Elytrium/LimboFilter", "AGPL-3.0", "clean-room"),
    "Leymooo/BungeeCord": ("Leymooo/BungeeCord (BotFilter)",
                           "BSD-2-Clause + no-commercial-hosting clause", "clean-room"),
    "Mateitaa1/CaptchaVerifyZ": ("Mateitaa1/CaptchaVerifyZ",
                                 "all rights reserved (Modrinth)", "clean-room"),
    "Supl1n/CaptchaGUI": ("Supl1n/CaptchaGUI", "no licence file (all rights reserved)",
                           "clean-room"),
    "GalleryCaptcha": ("GalleryCaptcha catalogue", "proprietary (no licence)", "reconstructed"),
}

PLUGIN_TYPES = {
    "LagBug/XProtect": ["code", "color", "different", "drop", "equation", "gui", "jump",
                        "map", "picture", "reverse", "slot", "sneak"],
    "jonesdevelopment/sonar": ["standard", "complex", "legacy"],
    "Archy-X/Krypton": ["map", "menu"],
    "FeelingAlive0/AdvancedCaptcha": ["button", "math"],
    "jSdCool/minecaptcha": ["text", "image"],
    "Z4OLLIEZ4/reCaptcha": ["captchasx"],
    "Joey61021/captcha": ["colorgui"],
    "laforetbrut/are-you-sure": ["code"],
    "Mrbysco/Captcha": ["math"],
    "Yukun99/Captchas": ["itemslot"],
    "China2B2T/Captcha": ["wool"],
    "InstantlyMoist/Captcha": ["textcaptcha"],
    "JSH32/Minecaptcha": ["map"],
    "haq/mapcha": ["map"],
    "just-captcha/ProstoCaptcha": ["map"],
    "irootdev/AnBot": ["captcha"],
    "ringoame196-s-mcPlugin/ReproductionCAPTCHA": ["map"],
    "n1zamu/NCaptcha": ["anvil"],
    "Elytrium/LimboFilter": ["map", "symbols", "framed3x3", "framed2x2"],
    "Leymooo/BungeeCord": ["map"],
    "Mateitaa1/CaptchaVerifyZ": ["map"],
    "Supl1n/CaptchaGUI": ["clickblock"],
    "GalleryCaptcha": ["ru-numberword", "ru-numberword-caption", "ru-symbols", "ru-web",
                       "ru-object-swatch"],
}

TYPE_IDS = (
    [f"{p}/{t}" for p, ts in PLUGIN_TYPES.items() for t in ts
     if p not in ("Elytrium/LimboFilter", "Leymooo/BungeeCord", "Mateitaa1/CaptchaVerifyZ",
                   "Supl1n/CaptchaGUI", "GalleryCaptcha")]
    + ["LimboFilter/map", "LimboFilter/symbols", "LimboFilter/framed3x3", "LimboFilter/framed2x2",
       "BotFilter/map", "CaptchaVerifyZ/map", "CaptchaGUI/clickblock",
       "GalleryCaptcha/ru-numberword", "GalleryCaptcha/ru-numberword-caption",
       "GalleryCaptcha/ru-symbols", "GalleryCaptcha/ru-web",
       "GalleryCaptcha/ru-object-swatch"]
)

NOT_OCR_TYPES = {
    "LagBug/XProtect/drop", "LagBug/XProtect/jump", "LagBug/XProtect/sneak",
    "LagBug/XProtect/different", "LagBug/XProtect/slot", "LagBug/XProtect/color",
    "LagBug/XProtect/gui", "LagBug/XProtect/picture",
    "China2B2T/Captcha/wool", "jSdCool/minecaptcha/image", "GalleryCaptcha/ru-object-swatch",
    "CaptchaGUI/clickblock", "FeelingAlive0/AdvancedCaptcha/button",
    "LimboFilter/map", "LimboFilter/framed3x3", "LimboFilter/framed2x2",
    "GalleryCaptcha/ru-numberword", "GalleryCaptcha/ru-numberword-caption",
    "Yukun99/Captchas/itemslot", "Joey61021/captcha/colorgui",
    "Archy-X/Krypton/menu", "LagBug/XProtect/equation",
    "FeelingAlive0/AdvancedCaptcha/math", "Mrbysco/Captcha/math",
    "jonesdevelopment/sonar/standard", "jonesdevelopment/sonar/complex",
    "jonesdevelopment/sonar/legacy", "Z4OLLIEZ4/reCaptcha/captchasx",
}


def plugin_of(type_id: str) -> str:
    if type_id.startswith("GalleryCaptcha/"):
        return "GalleryCaptcha"
    if type_id.startswith("LimboFilter/"):
        return "Elytrium/LimboFilter"
    if type_id.startswith("BotFilter/"):
        return "Leymooo/BungeeCord"
    if type_id.startswith("CaptchaVerifyZ/"):
        return "Mateitaa1/CaptchaVerifyZ"
    if type_id.startswith("CaptchaGUI/"):
        return "Supl1n/CaptchaGUI"
    parts = type_id.split("/")
    if len(parts) >= 2:
        return "/".join(parts[:2])
    return type_id


def training_data_section() -> str:
    lines = [
        "Every image was rendered by this project's own generators, which re-implement the",
        "captchas that open-source Minecraft anti-bot plugins draw. The dataset is **46 types",
        "x 100 images** (3400 in `dataset/out/`, 1200 in `dataset/out_ru/`), and it is published",
        "**one repository per licence family**, because the upstream plugins do not share one",
        "licence. Every row of every published dataset carries its `mode` and its upstream",
        "licence.",
        "",
        "`mode` is:",
        "",
        "* **faithful** - a line-by-line re-implementation from the upstream source, which the",
        "  upstream licence permits;",
        "* **clean-room** - the algorithm and the resulting picture were read from upstream and",
        "  rewritten independently: no code, comments, identifiers or copyright headers are",
        "  carried over. Used wherever the licence forbids copying, or where no licence exists;",
        "* **reconstructed** - no upstream source was found; the generator is driven by the",
        "  reference screenshots of the gallery catalogue and says so in its javadoc.",
        "",
        "| type | upstream | upstream licence | mode | a recogniser target? |",
        "|---|---|---|---|---|",
    ]
    for type_id in TYPE_IDS:
        plugin = plugin_of(type_id)
        upstream, licence, mode = PLUGINS.get(plugin, (plugin, "unknown", "unknown"))
        target = "no" if type_id in NOT_OCR_TYPES else "yes"
        lines.append(f"| `{type_id}` | {upstream} | {licence} | {mode} | {target} |")
    lines += [
        "",
        "Two of the renders are **approximations**, not reproductions, and the dataset card",
        "says so: the `jonesdevelopment/sonar` dot-matrix fonts could not be redistributed",
        "(`dotness.ttf` is personal-use only, `DotMatrix.ttf` has no licence at all), so Lucida",
        "Console and Courier New stand in; and `Archy-X/Krypton`'s swatch colours are invented,",
        "because the upstream derives them from the running server's material registry.",
        "",
        "The **weights** are MIT. The **dataset** is not: a user of the dataset has to comply",
        "with the licence of the plugin each row came from, and the three plugins with no",
        "licence at all (`Archy-X/Krypton`, `Yukun99/Captchas`,",
        "`ringoame196-s-mcPlugin/ReproductionCAPTCHA`, plus `Supl1n/CaptchaGUI` and the",
        "all-rights-reserved `Mateitaa1/CaptchaVerifyZ`) are published in a family of their",
        "own, because there the default is *all rights reserved*.",
    ]
    return "\n".join(lines)


def evaluation_section(val_report: dict | None, cfg: dict, n_params: int) -> str:
    lines = [
        f"The model has **{n_params:,} parameters** and **{cfg['num_classes']} classes**"
        f" ({cfg['num_classes'] - 1} characters plus the blank).",
        "",
    ]
    if not val_report:
        lines += [
            "**No evaluation report was supplied with this export.** The numbers of the",
            "training run are in the run's own `val_report.json`; re-export with",
            "`--val-report <path>` and they will be written into this section.",
        ]
        return "\n".join(lines)

    overall = val_report.get("overall", {})
    lines += [
        "| metric | value |",
        "|---|---|",
        f"| exact match | {overall.get('accuracy', 0):.4f} |",
        f"| mean CER | {overall.get('cer', 0):.4f} |",
        f"| samples | {overall.get('n', 0)} |",
        "",
        "The validation split is **by captcha type, never by image**: the unit of",
        "generalisation that matters is a plugin, and a random image split leaks because",
        "several types have only a handful of distinct answers (under a random split, about a",
        "third of all test samples have their exact gold answer string in the training half).",
        "",
        "Per type:",
        "",
        "| type | exact match | CER | n |",
        "|---|---|---|---|",
    ]
    for type_id, d in sorted(val_report.get("per_type", {}).items()):
        lines.append(f"| `{type_id}` | {d.get('accuracy', 0):.4f} | {d.get('cer', 0):.4f} "
                     f"| {d.get('n', 0)} |")
    return "\n".join(lines)


def write_model_card(out_dir: str, cfg: dict, charset: str, n_params: int,
                     val_report: dict | None, repo_id: str, checkpoint: str,
                     step: int, epoch: int, onnx_exporter: str) -> None:
    import transformers

    try:
        import onnxruntime

        onnx_version = onnxruntime.__version__
    except ImportError:  # noqa: BLE001
        onnx_version = "not installed"

    card = MODEL_CARD_TEMPLATE.format(
        title=repo_id,
        intro=(
            f"A CRNN + CTC captcha recogniser, trained from scratch by the **CaptchaOCR**\n"
            f"project on pixel-faithful re-implementations of Minecraft anti-bot-plugin\n"
            f"captchas.\n\n"
            f"* weights: `model.safetensors` (safetensors, {n_params:,} parameters)\n"
            f"* exported from the training checkpoint `{os.path.basename(checkpoint)}` "
            f"(step {step}, epoch {epoch})\n"
            f"* ONNX: `onnx/model.onnx` (exported with `torch.onnx.export`, "
            f"{onnx_exporter} exporter)"
        ),
        glyph_height=cfg["glyph_height"],
        num_classes=cfg["num_classes"],
        num_chars=len(charset),
        charset=charset,
        repo_id=repo_id,
        training_data=training_data_section(),
        evaluation=evaluation_section(val_report, cfg, n_params),
        python_version=".".join(str(v) for v in sys.version_info[:3]),
        torch_version=torch.__version__,
        transformers_version=transformers.__version__,
        onnxruntime_version=onnx_version,
    )
    with open(os.path.join(out_dir, "README.md"), "w", encoding="utf-8") as f:
        f.write(card)
