"""Реестр свойств алхимии.

Свойства хранятся и сравниваются только по ASCII-идентификаторам.
Отображаемые названия живут в локалях (``trait.<id>``), поэтому один и
тот же ингредиент работает для любого языка без миграций данных.
"""

# id -> положительное свойство (зелье можно пить) / отрицательное
TRAITS = {
    "heal": True,
    "hp_regen": True,
    "ap_regen": True,
    "haste": True,
    "vigor": True,
    "armor": True,
    "resistance": True,
    "heaviness": True,
    "strength": True,
    "dodge": True,
    "agility": True,
    "flight": True,
    "cleanse": True,
    "mana": True,
    "light": True,
    "dark_protection": True,
    "fire_protection": True,
    "ice_protection": True,
    "luck": True,
    "wealth": True,
    "weakness": False,
    "slow": False,
    "vampirism": False,
    "burn": False,
    "fire_vulnerability": False,
    "fragility": False,
    "fire_damage": False,
    "poison_damage": False,
    "weakening": False,
    "blind": False,
    "vulnerability": False,
    "dark_power": False,
    "madness": False,
    "suffocation": False,
    "disease": False,
    "speed": True,
    "lightness": True,
    "illusion": False,
    "paralysis": False,
    "sleep": False,
    "fear": False,
    "charm": False,
    "thirst": False,
    "jumping": True,
    "shock_damage": False,
    "bleed": False,
    "ice_damage": False,
}

POSITIVE_TRAITS = {trait_id for trait_id, is_positive in TRAITS.items() if is_positive}

# Старые русские названия. Нужны только для чтения данных, созданных до
# перехода на ID (например, если сервер ещё не вайпнули).
LEGACY_TRAIT_NAMES = {
    "Хил": "heal",
    "Слабость": "weakness",
    "Защита от тьмы": "dark_protection",
    "Замедление": "slow",
    "Свет": "light",
    "Очищение": "cleanse",
    "Удача": "luck",
    "Вампиризм": "vampirism",
    "Ожог": "burn",
    "Сила": "strength",
    "Броня": "armor",
    "Реген ОД": "ap_regen",
    "Уязвимость к огню": "fire_vulnerability",
    "Мана": "mana",
    "Ускорение": "haste",
    "Хрупкость": "fragility",
    "Урон огнем": "fire_damage",
    "Урон ядом": "poison_damage",
    "Защита от огня": "fire_protection",
    "Ослабление": "weakening",
    "Слепота": "blind",
    "Уязвимость": "vulnerability",
    "Сила тьмы": "dark_power",
    "Безумие": "madness",
    "Реген ХП": "hp_regen",
    "Удушье": "suffocation",
    "Болезнь": "disease",
    "Скорость": "speed",
    "Ловкость": "agility",
    "Уклонение": "dodge",
    "Тяжесть": "heaviness",
    "Сопротивление": "resistance",
    "Легкость": "lightness",
    "Бодрость": "vigor",
    "Богатство": "wealth",
    "Иллюзия": "illusion",
    "Защита от льда": "ice_protection",
    "Оцепенение": "paralysis",
    "Сон": "sleep",
    "Полет": "flight",
    "Страх": "fear",
    "Соблазн": "charm",
    "Жажда": "thirst",
    "Прыгучесть": "jumping",
    "Урон током": "shock_damage",
    "Кровотечение": "bleed",
    "Урон льдом": "ice_damage",
}


def normalize_trait(value: str) -> str | None:
    """Приводит ID или старое русское название к ID свойства."""
    if not isinstance(value, str):
        return None
    value = value.strip()
    if value in TRAITS:
        return value
    return LEGACY_TRAIT_NAMES.get(value)


def normalize_traits(values) -> list[str]:
    result = []
    for value in values or []:
        trait_id = normalize_trait(value)
        if trait_id and trait_id not in result:
            result.append(trait_id)
    return result
