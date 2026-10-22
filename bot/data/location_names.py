"""Английские названия и описания подземелий."""

from i18n import get_language, normalize_lang

SOLO_DUNGEONS_EN = {
    "forest": (
        "🌲 Mysterious Forest",
        "An ordinary forest full of goblins and slimes. (Great for beginners)",
    ),
    "crypt": (
        "💀 Forgotten Crypt",
        "Gloomy catacombs filled with undead and ancient riddles.",
    ),
    "temple": (
        "🏛️ Temple Ruins",
        "Ancient ruins with dangerous traps and guardians.",
    ),
}

WAR_REGIONS_EN = {
    1: ("🔥 Valley of Ash", "Scorched land ruled by fire demons."),
    2: ("🌲 Whispering Forest", "A corrupted ancient grove full of poison and rot."),
    3: ("❄️ Frozen Peaks", "Frostbound passes held by ice warriors."),
    4: ("🍄 Forgotten Swamps", "A deadly nesting ground of the giant spider queen."),
    5: ("🌑 Abyss Wastes", "A rift in the world whence the spawn of Darkness pour out."),
    6: ("⚡ Citadel of Storms", "A mountain bastion with storm golems."),
    7: ("👑 Bastion of Kings", "The heart of Camaria, seized by the Bone Dragon."),
}

DAILY_DUNGEONS_EN = {
    0: ("💀 Crypt of the Undead", "A crypt filled with ancient darkness."),
    1: ("🌋 Blazing Forge", "Rivers of lava and scorching anvil."),
    2: ("🍄 Mire of Oblivion", "Poisonous fumes and treacherous mud."),
    3: ("⏳ Temporal Ruins", "A place where seconds bend."),
    4: ("🩸 Dark Catacombs", "Whispers of cultists and bloodstained altars."),
    5: ("🏜 Golden Mirage", "The sands hide illusory riches."),
    6: ("⚔ Bloody Colosseum", "An arena for the mightiest warriors."),
}


def _localized(pair, fallback_name: str, fallback_desc: str, lang: str | None):
    if normalize_lang(lang or get_language()) == "en" and pair:
        return pair
    return fallback_name, fallback_desc


def solo_dungeon_display(dungeon_id: str, name: str, desc: str, lang: str | None = None):
    return _localized(SOLO_DUNGEONS_EN.get(dungeon_id), name, desc, lang)


def war_region_display(region_id: int, name: str, desc: str, lang: str | None = None):
    return _localized(WAR_REGIONS_EN.get(int(region_id)), name, desc, lang)


def daily_dungeon_display(day_index: int, name: str, desc: str, lang: str | None = None):
    return _localized(DAILY_DUNGEONS_EN.get(int(day_index)), name, desc, lang)
