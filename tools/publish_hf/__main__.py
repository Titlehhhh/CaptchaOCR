from .cli import main
from .constants import EXIT_ERROR
from .utils import log

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except KeyboardInterrupt:  # pragma: no cover
        log("Прервано пользователем.")
        raise SystemExit(EXIT_ERROR)
    except Exception as exc:  # noqa: BLE001
        log(f"ОШИБКА: {type(exc).__name__}: {exc}")
        raise SystemExit(EXIT_ERROR)
