"""The fixed knobs of the unified benchmark harness."""

import os

from paths import OUT, OUT_RU, REPORTS  # noqa: F401  (re-exported for the harness)

RESULTS_DIR = os.path.join(REPORTS, "bench_models")

# The user's pre-existing Hugging Face cache: read-only, but readable. An explicit
# HF_HUB_CACHE wins; otherwise the default location of the platform is used.
# It is deliberately NOT the HF_HOME set in ``harness/__init__.py`` - that one points
# into the workspace.
OLD_HUB = os.environ.get("HF_HUB_CACHE") or os.path.join(
    os.path.expanduser("~"), ".cache", "huggingface", "hub")

# The 13 types of the old benchmark (bench/bench_hf.py: TEXT_TYPES).
LEGACY_TYPES = [
    "Archy-X/Krypton/map",
    "InstantlyMoist/Captcha/textcaptcha",
    "JSH32/Minecaptcha/map",
    "haq/mapcha/map",
    "LagBug/XProtect/code",
    "LagBug/XProtect/map",
    "irootdev/AnBot/captcha",
    "jonesdevelopment/sonar/standard",
    "jSdCool/minecaptcha/text",
    "just-captcha/ProstoCaptcha/map",
    "laforetbrut/are-you-sure/code",
    "ringoame196-s-mcPlugin/ReproductionCAPTCHA/map",
    "n1zamu/NCaptcha/anvil",
]
