"""Английские названия монстров."""

from i18n import get_language, normalize_lang

MOB_NAMES_EN = {
    "temple_guard": "Temple Guardian",
    "living_idol": "Living Idol",
    "khmer_priest": "Khmer Priest",
    "poison_slime": "Poison Slime",
    "skeleton_crossbow": "Skeleton Crossbowman",
    "living_dead": "Living Dead",
    "magma_slime": "Magma Slime",
    "golem_blacksmith": "Golem Blacksmith",
    "decay_treant": "Decaying Treant",
    "magic_anomaly": "Magic Anomaly",
    "time_mimic": "Time Mimic",
    "cultist_fanatic": "Cultist Fanatic",
    "goblin_thief": "Goblin Thief",
    "golden_mimic": "Golden Mimic",
    "fallen_champion": "Fallen Champion",
    "arena_berserk": "Arena Berserker",
    "time_keeper": "Time Keeper",
    "spider_queen": "Spider Queen",
    "fire_lord": "Fire Lord",
    "bone_dragon": "Bone Dragon",
    "abyss_priest": "Abyss Priest",
    "greed_spirit": "Greed Spirit",
    "arena_champ": "Arena Champion",
}


def mob_display_name(mob_id: str, fallback: str, lang: str | None = None) -> str:
    if normalize_lang(lang or get_language()) == "en":
        return MOB_NAMES_EN.get(mob_id, fallback)
    return fallback
