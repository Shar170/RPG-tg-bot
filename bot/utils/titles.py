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
# Порядок важен для отображения и проверки локалей.
MEDAL_TIERS = ("participant", "defender", "veteran", "hero", "liberator")

# Пороги «боевых» медалей за каждый регион. Освободитель выдаётся отдельно —
# всем, кто завершил рейд во время финальной зачистки региона.
WAR_MEDAL_THRESHOLDS = {
    "participant": 1,
    "defender": 10,
    "veteran": 50,
    "hero": 100,
}
WAR_LIBERATOR_TIER = "liberator"

# (id медали, ключ статистики, порог)
STAT_MEDALS = (
    ("mobs_100", "mobs_killed", 100),
    ("mobs_1000", "mobs_killed", 1000),
    ("mobs_5000", "mobs_killed", 5000),
    ("bosses_10", "bosses_killed", 10),
    ("bosses_100", "bosses_killed", 100),
    ("bosses_500", "bosses_killed", 500),
    ("event_bosses_10", "event_bosses_killed", 10),
    ("event_bosses_50", "event_bosses_killed", 50),
    ("pvp_wins_25", "pvp_wins", 25),
    ("pvp_wins_100", "pvp_wins", 100),
    ("pvp_wins_500", "pvp_wins", 500),
    ("pvp_easy_25", "pvp_wins_easy", 25),
    ("pvp_even_50", "pvp_wins_even", 50),
    ("pvp_hard_25", "pvp_wins_hard", 25),
    ("pvp_legend_5", "pvp_wins_legend", 5),
    ("war_clears_100", "war_clears", 100),
    ("war_clears_1000", "war_clears", 1000),
    ("craft_10", "items_crafted", 10),
    ("craft_100", "items_crafted", 100),
    ("alchemy_20", "potions_crafted", 20),
    ("alchemy_100", "potions_crafted", 100),
    ("minigames_10", "minigames_won", 10),
    ("minigames_100", "minigames_won", 100),
    ("riddles_25", "riddles_solved", 25),
    ("riddles_250", "riddles_solved", 250),
    ("story_count_5", "stories_completed", 5),
    ("story_count_10", "stories_completed", 10),
)

# (id медали, минимальный уровень)
LEVEL_MEDALS = (
    ("level_10", 10),
    ("level_25", 25),
    ("level_50", 50),
    ("level_75", 75),
    ("level_100", 100),
)

# (id медали, минимальная серия дней подряд)
STREAK_MEDALS = (
    ("streak_3", 3),
    ("streak_7", 7),
    ("streak_14", 14),
    ("streak_30", 30),
    ("streak_60", 60),
    ("streak_100", 100),
    ("streak_365", 365),
)

# (id медали, минимальное число разных карт в коллекции)
CARD_MEDALS = (
    ("cards_25", 25),
    ("cards_100", 100),
    ("cards_300", 300),
)

STATIC_MEDAL_IDS = tuple(
    [medal_id for medal_id, _stat, _threshold in STAT_MEDALS]
    + [medal_id for medal_id, _threshold in LEVEL_MEDALS]
    + [medal_id for medal_id, _threshold in STREAK_MEDALS]
    + [medal_id for medal_id, _threshold in CARD_MEDALS]
)


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


def collect_medal_ids(
    stats: dict,
    level: int = 1,
    visit_streak: int = 0,
    best_visit_streak: int = 0,
    cards_count: int = 0,
) -> list[str]:
    """Возвращает все медали, которые игрок заслужил по текущим счётчикам."""
    earned: list[str] = []

    for medal_id, stat_key, threshold in STAT_MEDALS:
        if int(stats.get(stat_key, 0) or 0) >= threshold:
            earned.append(medal_id)

    for medal_id, required_level in LEVEL_MEDALS:
        if int(level or 1) >= required_level:
            earned.append(medal_id)

    streak = max(int(visit_streak or 0), int(best_visit_streak or 0))
    for medal_id, required_streak in STREAK_MEDALS:
        if streak >= required_streak:
            earned.append(medal_id)

    for medal_id, required_cards in CARD_MEDALS:
        if int(cards_count or 0) >= required_cards:
            earned.append(medal_id)

    return earned


def get_medal_category(medal_id: str) -> str:
    """Категория для сортировки/группировки медалей в профиле."""
    if medal_id.startswith("war_"):
        return "war"
    if medal_id.startswith("pvp_"):
        return "pvp"
    if medal_id.startswith("story_"):
        return "story"
    if medal_id.startswith("level_"):
        return "progress"
    if medal_id.startswith("streak_"):
        return "streak"
    if medal_id.startswith(("mobs_", "bosses_")) or medal_id.startswith("event_bosses_"):
        return "combat"
    if medal_id.startswith(("craft_", "alchemy_")):
        return "craft"
    if medal_id.startswith(("minigames_", "riddles_", "cards_")):
        return "misc"
    return "other"
