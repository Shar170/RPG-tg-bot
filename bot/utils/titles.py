"""Титулы как стабильные ID + отображаемые названия из локалей."""

from i18n import t

TITLE_NOVICE = "novice"
TITLE_SLIME_SLAYER = "slime_slayer"
TITLE_BUTCHER = "butcher"
TITLE_BOSS_HUNTER = "boss_hunter"
TITLE_GLADIATOR = "gladiator"
TITLE_ARENA_CHAMPION = "arena_champion"
TITLE_WAR_HERO = "war_hero"
TITLE_THINKER = "thinker"
TITLE_EMPTY_HEAD = "empty_head"
TITLE_FIREFIGHTER = "firefighter"
TITLE_GOBLIN_BANE = "goblin_bane"
TITLE_IDOL_BREAKER = "idol_breaker"
TITLE_KEEPER_BURIER = "keeper_burier"
TITLE_POTION_MASTER = "potion_master"
TITLE_SMITH = "smith"
TITLE_LUCKY = "lucky"

ALL_TITLES = [
    TITLE_NOVICE,
    TITLE_SLIME_SLAYER,
    TITLE_BUTCHER,
    TITLE_BOSS_HUNTER,
    TITLE_GLADIATOR,
    TITLE_ARENA_CHAMPION,
    TITLE_WAR_HERO,
    TITLE_THINKER,
    TITLE_EMPTY_HEAD,
    TITLE_FIREFIGHTER,
    TITLE_GOBLIN_BANE,
    TITLE_IDOL_BREAKER,
    TITLE_KEEPER_BURIER,
    TITLE_POTION_MASTER,
    TITLE_SMITH,
    TITLE_LUCKY,
]

LEGACY_TITLE_NAMES = {
    "Новичок": TITLE_NOVICE,
    "Истребитель Слизней": TITLE_SLIME_SLAYER,
    "Мясник Камарии": TITLE_BUTCHER,
    "Охотник на Боссов": TITLE_BOSS_HUNTER,
    "Гладиатор": TITLE_GLADIATOR,
    "Чемпион Арены": TITLE_ARENA_CHAMPION,
    "Герой Камарии": TITLE_WAR_HERO,
    "Мыслитель": TITLE_THINKER,
    "Пустоголовый": TITLE_EMPTY_HEAD,
    "Пожарный": TITLE_FIREFIGHTER,
    "Гроза гоблинов": TITLE_GOBLIN_BANE,
    "Разрушитель идолов": TITLE_IDOL_BREAKER,
    "Похоронитель хранителей": TITLE_KEEPER_BURIER,
    "Мастер зелий": TITLE_POTION_MASTER,
    "Кузнец": TITLE_SMITH,
    "Счастливчик": TITLE_LUCKY,
}


def normalize_title(title_id: str | None) -> str:
    if not title_id:
        return TITLE_NOVICE
    if title_id in ALL_TITLES:
        return title_id
    return LEGACY_TITLE_NAMES.get(title_id, TITLE_NOVICE)


def get_title_display(title_id: str | None, lang: str | None = None) -> str:
    return t(f"title.{normalize_title(title_id)}", lang=lang)


# --- Медали ---
MEDAL_TIERS = ("defender", "veteran", "hero", "liberator")


def make_medal_id(tier: str, region_id: int) -> str:
    return f"war_{tier}_{region_id}"


def parse_medal_id(medal_id: str) -> tuple[str, int] | None:
    if not isinstance(medal_id, str):
        return None
    parts = medal_id.split("_")
    if len(parts) != 3 or parts[0] != "war" or parts[1] not in MEDAL_TIERS:
        return None
    try:
        return parts[1], int(parts[2])
    except ValueError:
        return None


def get_medal_display(medal_id: str, region_name: str, lang: str | None = None) -> str:
    parsed = parse_medal_id(medal_id)
    if not parsed:
        return medal_id
    tier, _region_id = parsed
    return t(f"medal.{tier}", lang=lang, region=region_name)
