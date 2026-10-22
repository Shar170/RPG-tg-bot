"""Минимальный каркас локализации.

Ключи плоские (``town.btn.inventory``), каталоги — JSON в ``bot/locales``.
Текущий язык хранится в contextvar и ставится middleware на каждый update.
"""

from __future__ import annotations

import json
import os
import sys
from contextlib import contextmanager
from contextvars import ContextVar, Token

DEFAULT_LANG = "ru"
SUPPORTED_LANGS = ("ru", "en")
LOCALES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "locales")

_current_lang: ContextVar[str] = ContextVar("current_lang", default=DEFAULT_LANG)
_catalogs: dict[str, dict] = {}
_warned_missing: set[tuple[str, str]] = set()


def normalize_lang(code: str | None) -> str:
    """``en-US`` -> ``en``, ``ru-RU`` -> ``ru``, всё остальное -> ru."""
    if not code:
        return DEFAULT_LANG
    code = str(code).strip().lower().replace("_", "-")
    if code.startswith("en"):
        return "en"
    if code.startswith("ru"):
        return "ru"
    return DEFAULT_LANG


def load_catalogs() -> dict[str, dict]:
    global _catalogs
    if _catalogs:
        return _catalogs

    loaded: dict[str, dict] = {}
    for lang in SUPPORTED_LANGS:
        path = os.path.join(LOCALES_DIR, f"{lang}.json")
        try:
            with open(path, "r", encoding="utf-8") as fh:
                loaded[lang] = json.load(fh)
        except FileNotFoundError:
            loaded[lang] = {}
            print(f"[i18n] locale file not found: {path}", file=sys.stderr)
        except json.JSONDecodeError as exc:
            loaded[lang] = {}
            print(f"[i18n] invalid JSON in {path}: {exc}", file=sys.stderr)
    _catalogs = loaded
    return _catalogs


def reload_catalogs() -> None:
    global _catalogs
    _catalogs = {}
    _warned_missing.clear()
    load_catalogs()


def get_language() -> str:
    return _current_lang.get()


def set_language(lang: str | None) -> Token:
    return _current_lang.set(normalize_lang(lang))


def reset_language(token: Token) -> None:
    _current_lang.reset(token)


@contextmanager
def language_context(lang: str | None):
    token = set_language(lang)
    try:
        yield
    finally:
        reset_language(token)


class _SafeDict(dict):
    def __missing__(self, key):
        return "{" + key + "}"


def _format(value: str, params: dict) -> str:
    if not params:
        return value
    try:
        return value.format_map(_SafeDict(params))
    except (ValueError, IndexError):
        return value


def _lookup(key: str, lang: str):
    catalogs = load_catalogs()
    catalog = catalogs.get(lang, {})
    if key in catalog:
        return catalog[key]

    # Fallback на язык по умолчанию.
    fallback = catalogs.get(DEFAULT_LANG, {})
    if key in fallback:
        return fallback[key]

    marker = (lang, key)
    if marker not in _warned_missing:
        _warned_missing.add(marker)
        print(f"[i18n] missing key '{key}' for '{lang}'", file=sys.stderr)
    return None


def t(key: str, lang: str | None = None, **params) -> str:
    """Переводит ключ. Неизвестные параметры остаются как ``{name}``."""
    lang = normalize_lang(lang or get_language())
    value = _lookup(key, lang)
    if value is None:
        return key
    if isinstance(value, dict):
        value = value.get("other") or value.get("many") or next(iter(value.values()), key)
    return _format(str(value), params)


def plural_form(lang: str, n: int) -> str:
    lang = normalize_lang(lang)
    n = abs(int(n))
    if lang == "ru":
        if n % 10 == 1 and n % 100 != 11:
            return "one"
        if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
            return "few"
        return "many"
    return "one" if n == 1 else "other"


def t_plural(key: str, n: int, lang: str | None = None, **params) -> str:
    """Плюрализованная строка. В каталоге значение — объект форм."""
    lang = normalize_lang(lang or get_language())
    value = _lookup(key, lang)
    if value is None:
        return key
    if not isinstance(value, dict):
        return _format(str(value), params)

    form = plural_form(lang, n)
    text = value.get(form) or value.get("other") or next(iter(value.values()))
    params = {**params, "n": n}
    return _format(str(text), params)
