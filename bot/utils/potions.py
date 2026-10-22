"""Идентификаторы и эффекты алхимических зелий.

Кастомное зелье — это не русская строка, а стабильный ID вида
``potion_custom:armor+heal``. Благодаря этому его можно хранить в инвентаре,
передавать в callback_data, сравнивать в квестах и переводить название без
потери данных.
"""

from data.traits import POSITIVE_TRAITS, normalize_trait, normalize_traits
from i18n import t

CUSTOM_POTION_PREFIX = "potion_custom:"

# Базовые эффекты свойств. scale — прибавка за уровень игрока в PvE.
DAMAGE_TRAITS = {
    "fire_damage": {"element": "fire", "base": 30, "scale": 5, "dot": "dot_burn", "dot_turns": 3},
    "poison_damage": {"element": "poison", "base": 20, "scale": 4, "dot": "dot_poison", "dot_turns": 4},
    "ice_damage": {"element": "ice", "base": 25, "scale": 4, "distance": "far"},
    "shock_damage": {"element": "shock", "base": 35, "scale": 6},
    "dark_power": {"element": "dark", "base": 35, "scale": 6},
    "light": {"element": "light", "base": 40, "scale": 5, "cleanse": True},
}


def make_custom_potion_id(trait_ids) -> str:
    """Собирает канонический ID зелья из набора свойств."""
    traits = sorted(set(normalize_traits(trait_ids)))
    return CUSTOM_POTION_PREFIX + "+".join(traits)


def is_custom_potion(value: str) -> bool:
    if not isinstance(value, str):
        return False
    lowered = value.strip().lower()
    return (
        lowered.startswith(CUSTOM_POTION_PREFIX)
        or lowered.startswith("зелье:")
        or lowered.startswith("potion:")
    )


def parse_custom_potion_traits(value: str) -> list[str]:
    """Возвращает ID свойств из нового или старого названия зелья."""
    if not isinstance(value, str):
        return []

    raw = value.strip()
    lowered = raw.lower()
    if lowered.startswith(CUSTOM_POTION_PREFIX):
        raw = raw[len(CUSTOM_POTION_PREFIX):]
        parts = raw.split("+")
    elif lowered.startswith("зелье:") or lowered.startswith("potion:"):
        raw = raw.split(":", 1)[1]
        parts = raw.split(",")
    else:
        return []

    result = []
    for part in parts:
        trait_id = normalize_trait(part)
        if trait_id and trait_id not in result:
            result.append(trait_id)
    return result


def trait_display(trait_id: str, lang: str | None = None) -> str:
    normalized = normalize_trait(trait_id) or trait_id
    return t(f"trait.{normalized}", lang=lang)


def custom_potion_display_name(trait_ids, lang: str | None = None) -> str:
    names = ", ".join(trait_display(tid, lang=lang) for tid in trait_ids)
    return t("potion.custom", lang=lang, traits=names)


def get_potion_display_name(value: str, lang: str | None = None) -> str:
    """Название зелья для интерфейса: кастомное или обычный предмет из БД."""
    if is_custom_potion(value):
        return custom_potion_display_name(parse_custom_potion_traits(value), lang=lang)

    try:
        from database import get_item

        item = get_item(value)
        if item:
            return item["name"]
    except Exception:
        pass
    return value


def analyze_traits(trait_ids) -> dict:
    """Считает эффекты зелья по ID свойств.

    Возвращает нейтральную структуру, которую PvE и PvP применяют к своим
    полям боя. Один и тот же набор свойств больше не зависит от языка.
    """
    traits = set(normalize_traits(trait_ids))
    is_thrown = not bool(traits & POSITIVE_TRAITS)

    effects = {
        "trait_ids": sorted(traits),
        "is_thrown": is_thrown,
        "heal_pct": 0.25 * (int("heal" in traits) + int("hp_regen" in traits)),
        "ap_bonus": 2 if traits & {"ap_regen", "haste", "vigor"} else 0,
        "armor_bonus": 15 if traits & {"armor", "resistance", "heaviness"} else 0,
        "armor_turns": 3,
        "str_bonus": 20 if ("strength" in traits and "dark_power" not in traits) else 0,
        "str_turns": 2,
        "dodge_bonus": 0.35 if traits & {"dodge", "agility", "flight"} else 0.0,
        "dodge_turns": 2,
        "cleanse": bool(traits & {"cleanse", "mana"}),
        "gold_range": (30, 80) if traits & {"wealth", "luck"} else None,
        "self_damage": 0,
        "enemy_flat_damage": 0,
        "damage_events": [],
        "enemy_dots": {},
        "enemy_stun": 1 if traits & {"paralysis", "sleep", "fear"} else 0,
        "self_debuffs": {},
        "enemy_debuffs": {},
        "vampirism": 0,
        "distance": None,
    }

    # Урон и отбрасывание.
    for trait_id, spec in DAMAGE_TRAITS.items():
        if trait_id == "light":
            if not ({"light", "dark_protection"} & traits):
                continue
        elif trait_id == "ice_damage":
            if not ({"ice_damage", "slow"} & traits):
                continue
        elif trait_id not in traits:
            continue

        event = {
            "element": spec["element"],
            "base": spec["base"],
            "scale": spec.get("scale", 0),
        }
        if spec.get("dot"):
            event["dot"] = spec["dot"]
            event["dot_turns"] = spec.get("dot_turns", 1)
            effects["enemy_dots"][spec["dot"]] = spec.get("dot_turns", 1)
        if spec.get("distance"):
            effects["distance"] = spec["distance"]
        if spec.get("cleanse"):
            effects["cleanse"] = True
        effects["damage_events"].append(event)

    if "bleed" in traits:
        effects["enemy_dots"]["dot_bleed"] = 3
    if "vampirism" in traits:
        effects["vampirism"] = 20

    # Негативные свойства: при броске — врагу, при питье — себе.
    if traits & {"weakness", "burn", "disease", "suffocation"}:
        if is_thrown:
            effects["enemy_flat_damage"] += 15
        else:
            effects["self_damage"] += 15

    if "fragility" in traits:
        if is_thrown:
            effects["enemy_debuffs"]["debuff_vuln"] = 3
        else:
            effects["self_debuffs"]["debuff_fragile"] = 3

    if "vulnerability" in traits:
        if is_thrown:
            effects["enemy_debuffs"]["debuff_vuln"] = 3
        else:
            effects["self_debuffs"]["debuff_vuln"] = 3

    if "blind" in traits:
        key = "enemy_debuffs" if is_thrown else "self_debuffs"
        effects[key]["debuff_blind"] = 2

    return effects
