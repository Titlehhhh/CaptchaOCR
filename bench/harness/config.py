
import os

from paths import OUT, OUT_RU, REPORTS  # noqa: F401  (re-exported for the harness)

RESULTS_DIR = os.path.join(REPORTS, "bench_models")





OLD_HUB = os.environ.get("HF_HUB_CACHE") or os.path.join(
    os.path.expanduser("~"), ".cache", "huggingface", "hub")


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
