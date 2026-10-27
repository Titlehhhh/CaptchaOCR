
import os

from .constants import EXIT_NO_AUTH
from .utils import log

AUTH_INSTRUCTIONS = """\
=== Нужен токен Hugging Face =========================================

Скрипту нужен токен с правом WRITE. Сделайте это (один раз):

  1. Зарегистрируйтесь на https://huggingface.co/join
     (аккаунт привязан к почте, подтверждение по ссылке из письма).

  2. Откройте https://huggingface.co/settings/tokens
     -> "Write token" (или "Read & Write") -> задайте имя, например "captha".
     Токен — это строка вида hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx.

  3. Сохраните токен в переменную окружения (PowerShell, текущая сессия):

       $env:HF_TOKEN = "hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

     Или один раз на машину:

       [Environment]::SetEnvironmentVariable("HF_TOKEN", "hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx", "User")

  4. Либо авторизуйтесь через CLI (он тоже кладёт токен в ~/.cache/huggingface/token):

       .venv-gpu\\Scripts\\hf.exe auth login
       .venv-gpu\\Scripts\\hf.exe auth whoami

Проверить, что токен виден:

  $env:HF_TOKEN | Measure-Object -Character
  .venv-gpu\\Scripts\\hf.exe auth whoami

После этого запустите ту же команду снова.
====================================================================="""


def resolve_token(explicit: str | None) -> str | None:
    if explicit:
        return explicit
    for name in ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "HUGGINGFACE_TOKEN"):
        value = os.environ.get(name)
        if value and value.strip():
            return value.strip()
    try:
        from huggingface_hub import get_token

        stored = get_token()
        if stored:
            return stored
    except Exception:  # noqa: BLE001 - токена просто нет, это не ошибка
        return None
    return None


def require_token(explicit: str | None) -> str:
    token = resolve_token(explicit)
    if token:
        return token
    log(AUTH_INSTRUCTIONS)
    log("Токен не найден: ни HF_TOKEN, ни сохранённый токен CLI. Выход с кодом 2.")
    raise SystemExit(EXIT_NO_AUTH)


def api_for(token: str):
    from huggingface_hub import HfApi

    return HfApi(token=token)


def whoami_name(api) -> str:
    try:
        info = api.whoami()
    except Exception:  # noqa: BLE001 - токен может быть без прав на профиль
        return ""
    if isinstance(info, dict):
        return str(info.get("name") or info.get("fullname") or "")
    return ""
