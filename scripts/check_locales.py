"""Проверка каталогов локализации.

Запуск: python scripts/check_locales.py
Код возврата 1, если есть расхождения ключей/плейсхолдеров или дубликаты.
"""

from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOT = os.path.join(ROOT, "bot")
LOCALES = os.path.join(BOT, "locales")
sys.path.insert(0, BOT)

PLACEHOLDER_RE = re.compile(r"(?<!\{)\{([a-zA-Z_][a-zA-Z0-9_]*)\}(?!\})")
LANGS = ("ru", "en")


def no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate key: {key}")
        result[key] = value
    return result


def load(lang: str) -> dict:
    path = os.path.join(LOCALES, f"{lang}.json")
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh, object_pairs_hook=no_duplicates)


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from strings(item)


def placeholders(value) -> set[str]:
    result = set()
    for text in strings(value):
        result.update(PLACEHOLDER_RE.findall(text))
    return result


def main() -> int:
    errors = []
    catalogs = {}

    for lang in LANGS:
        try:
            catalogs[lang] = load(lang)
        except Exception as exc:
            errors.append(f"{lang}.json: {exc}")
    if errors:
        print("\n".join(errors))
        return 1

    ru_keys = set(catalogs["ru"])
    en_keys = set(catalogs["en"])
    for key in sorted(ru_keys - en_keys):
        errors.append(f"key only in ru: {key}")
    for key in sorted(en_keys - ru_keys):
        errors.append(f"key only in en: {key}")

    for key in sorted(ru_keys & en_keys):
        ru_ph = placeholders(catalogs["ru"][key])
        en_ph = placeholders(catalogs["en"][key])
        if ru_ph != en_ph:
            errors.append(f"placeholders differ for {key}: ru={sorted(ru_ph)} en={sorted(en_ph)}")

    # Контентные ключи, которые обязаны существовать.
    from data.traits import TRAITS
    from utils.titles import ALL_TITLES, MEDAL_TIERS

    required = [f"trait.{tid}" for tid in TRAITS]
    required += [f"title.{tid}" for tid in ALL_TITLES]
    required += [f"medal.{tier}" for tier in MEDAL_TIERS]
    for key in required:
        for lang in LANGS:
            if key not in catalogs[lang]:
                errors.append(f"missing required key '{key}' in {lang}.json")

    if errors:
        print("Locale check failed:")
        print("\n".join(f"- {err}" for err in errors))
        return 1

    print(f"Locale check OK: {len(ru_keys)} keys, {len(LANGS)} languages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
