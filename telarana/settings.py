"""Ajustes de usuario de SpiderFinance, guardados en data/ajustes.json."""
import json

from .database import DATA_DIR

PATH = DATA_DIR / "ajustes.json"

DEFAULTS = {
    "currency": "$",          # símbolo de moneda
    "alert_threshold": 90,    # % de ingresos comprometidos que dispara la alerta
    "animations": True,       # animaciones del anillo y de las barras
    "sidebar_expanded": False,  # barra lateral abierta al iniciar
}

CURRENCIES = ["$", "COP", "US$", "€", "S/", "Bs"]

_cache = None


def _load():
    global _cache
    if _cache is None:
        _cache = dict(DEFAULTS)
        try:
            stored = json.loads(PATH.read_text(encoding="utf-8"))
            for key in DEFAULTS:
                if key in stored and type(stored[key]) is type(DEFAULTS[key]):
                    _cache[key] = stored[key]
        except (OSError, ValueError):
            pass
    return _cache


def get(key):
    return _load()[key]


def _save():
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        PATH.write_text(json.dumps(_load(), ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def set(key, value):  # noqa: A001
    if key in DEFAULTS:
        _load()[key] = value
        _save()


def reset():
    global _cache
    _cache = dict(DEFAULTS)
    _save()
