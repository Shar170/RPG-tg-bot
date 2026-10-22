"""Английские названия алхимических ингредиентов."""

from i18n import get_language, normalize_lang

INGREDIENT_NAMES_EN = {
    "cave_mushroom": "Cave Mushroom",
    "light_flower": "Radiant Flower",
    "red_berry": "Bloodberry",
    "mountain_moss": "Mountain Moss",
    "water_lily": "Water Lily",
    "fire_root": "Magma Core",
    "poison_gland": "Poison Gland",
    "demon_blood": "Demon Blood",
    "ash_spores": "Ash Spores",
    "swamp_rot": "Swamp Rot",
    "vampire_bat_wing": "Vampire Bat Wing",
    "time_tear": "Time Tear",
    "iron_bark": "Ironbark",
    "wind_feather": "Wind Feather",
    "coffee_bean": "Coffee Bean",
    "gold_petal": "Golden Petal",
    "leprechaun_clover": "Lucky Clover",
    "crystal_shard": "Crystal Shard",
    "ice_thistle": "Frost Thistle",
    "frost_gland": "Frost Gland",
    "sun_stone": "Sunstone",
    "moon_dust": "Moon Dust",
    "shadow_essence": "Shadow Essence",
    "troll_fat": "Troll Fat",
    "goblin_ear": "Goblin Ear",
    "dragon_scale": "Dragon Scale",
    "harpy_claw": "Harpy Claw",
    "siren_vocal_cord": "Siren Vocal Cord",
    "giant_toe": "Giant's Toe",
    "pixie_dust": "Pixie Dust",
    "bone_marrow": "Bone Marrow",
    "ecto_plasm": "Ectoplasm",
    "basilisk_eye": "Basilisk Eye",
    "phoenix_ash": "Phoenix Ash",
    "mandrake_root": "Mandrake Root",
    "silver_leaf": "Silver Leaf",
    "blood_rose": "Blood Rose",
    "grave_dust": "Grave Dust",
    "abyssal_pearl": "Abyssal Pearl",
    "stardust": "Stardust",
    "coral_fragment": "Coral Fragment",
    "desert_mirage": "Mirage Flower",
    "obsidian_shard": "Obsidian Shard",
    "spider_silk": "Spider Silk",
    "snake_venom": "Cobra Venom",
    "toad_wart": "Toad Wart",
    "electric_eel_skin": "Electric Eel Skin",
    "storm_cloud": "Storm Cloud",
    "living_water": "Living Water",
    "dead_water": "Dead Water",
}


def ingredient_display_name(ingredient_id: str, fallback: str, lang: str | None = None) -> str:
    if normalize_lang(lang or get_language()) == "en":
        return INGREDIENT_NAMES_EN.get(ingredient_id, fallback)
    return fallback
