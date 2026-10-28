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
    from data.items import ITEMS
    from data.item_names import ITEM_NAMES_EN
    from data.ingredients import INGREDIENTS
    from data.ingredient_names import INGREDIENT_NAMES_EN
    from data.locations import SOLO_DUNGEONS, WAR_REGIONS, DAILY_DUNGEONS
    from data.location_names import (
        SOLO_DUNGEONS_EN,
        WAR_REGIONS_EN,
        DAILY_DUNGEONS_EN,
    )
    from data.mobs import BESTIARY
    from data.mob_names import MOB_NAMES_EN
    from utils.titles import ALL_TITLES, MEDAL_TIERS, STATIC_MEDAL_IDS

    required = [f"trait.{tid}" for tid in TRAITS]
    required += [f"title.{tid}" for tid in ALL_TITLES]
    required += [f"medal.{tier}" for tier in MEDAL_TIERS]
    required += [f"medal.{medal_id}" for medal_id in STATIC_MEDAL_IDS]
    for key in required:
        for lang in LANGS:
            if key not in catalogs[lang]:
                errors.append(f"missing required key '{key}' in {lang}.json")

    item_ids = {item_id for item_id, *_rest in ITEMS}
    for item_id in sorted(item_ids - set(ITEM_NAMES_EN)):
        errors.append(f"missing English name for item '{item_id}'")
    for item_id in sorted(set(ITEM_NAMES_EN) - item_ids):
        errors.append(f"English name for unknown item '{item_id}'")

    ingredient_ids = {ingredient_id for ingredient_id, *_rest in INGREDIENTS}
    for ingredient_id in sorted(ingredient_ids - set(INGREDIENT_NAMES_EN)):
        errors.append(f"missing English name for ingredient '{ingredient_id}'")
    for ingredient_id in sorted(set(INGREDIENT_NAMES_EN) - ingredient_ids):
        errors.append(f"English name for unknown ingredient '{ingredient_id}'")

    solo_ids = {dungeon_id for dungeon_id, *_rest in SOLO_DUNGEONS}
    for dungeon_id in sorted(solo_ids - set(SOLO_DUNGEONS_EN)):
        errors.append(f"missing English location for solo dungeon '{dungeon_id}'")
    war_ids = {region_id for region_id, *_rest in WAR_REGIONS}
    for region_id in sorted(war_ids - set(WAR_REGIONS_EN)):
        errors.append(f"missing English location for war region '{region_id}'")
    daily_ids = {day_index for day_index, *_rest in DAILY_DUNGEONS}
    for day_index in sorted(daily_ids - set(DAILY_DUNGEONS_EN)):
        errors.append(f"missing English location for daily dungeon '{day_index}'")

    mob_ids = {mob_id for mob_id, *_rest in BESTIARY}
    for mob_id in sorted(mob_ids - set(MOB_NAMES_EN)):
        errors.append(f"missing English name for mob '{mob_id}'")
    for mob_id in sorted(set(MOB_NAMES_EN) - mob_ids):
        errors.append(f"English name for unknown mob '{mob_id}'")

    if errors:
        print("Locale check failed:")
        print("\n".join(f"- {err}" for err in errors))
        return 1

    print(f"Locale check OK: {len(ru_keys)} keys, {len(LANGS)} languages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
