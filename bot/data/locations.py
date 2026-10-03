import json

SOLO_DUNGEONS = [
    ("forest", "🌲 Загадочный Лес", "Обычный лес с гоблинами и слизнями. (Отлично для новичков)", json.dumps(["poison_slime", "goblin_thief", "decay_treant"]), "decay_treant", 3, 5, json.dumps({"combat": 40, "puzzle": 30, "treasure": 20, "empty": 10})),
    ("crypt", "💀 Забытый Склеп", "Мрачные катакомбы, полные нежити и древних загадок.", json.dumps(["skeleton_crossbow", "living_dead", "fallen_champion"]), "bone_dragon", 4, 6, json.dumps({"combat": 60, "puzzle": 10, "treasure": 20, "empty": 10})),
    ("temple", "🏛️ Руины Храма", "Древние развалины с опасными ловушками и стражами.", json.dumps(["temple_guard", "living_idol", "khmer_priest"]), "golem_blacksmith", 5, 8, json.dumps({"combat": 50, "puzzle": 25, "treasure": 15, "empty": 10}))
]

WAR_REGIONS = [
    (1, "🔥 Долина Пепла", "Выжженная земля под властью огненных демонов.", 100000, 0, 0, "fire_lord", json.dumps(["magma_slime", "cultist_fanatic"])),
    (2, "🌲 Шепчущий Лес", "Оскверненная древняя чаща, полная яда и гнили.", 100000, 0, 0, "decay_treant", json.dumps(["poison_slime", "decay_treant"])),
    (3, "❄️ Ледяные Пики", "Морозные перевалы, скованные ледяными воинами.", 100000, 0, 0, "arena_berserk", json.dumps(["skeleton_crossbow", "living_idol"])),
    (4, "🍄 Забытые Болота", "Гиблое место гнездования гигантской паучихи.", 100000, 0, 0, "spider_queen", json.dumps(["poison_slime", "goblin_thief"])),
    (5, "🌑 Пустоши Бездны", "Разлом мира, откуда вырываются порождения Тьмы.", 100000, 0, 0, "abyss_priest", json.dumps(["cultist_fanatic", "magic_anomaly"])),
    (6, "⚡ Цитадель Бурь", "Высокогорный бастион с грозовыми големами.", 100000, 0, 0, "golem_blacksmith", json.dumps(["temple_guard", "magic_anomaly"])),
    (7, "👑 Бастион Королей", "Сердце Камарии, захваченное Костяным Драконом.", 100000, 0, 0, "bone_dragon", json.dumps(["fallen_champion", "skeleton_crossbow"]))
]

DAILY_DUNGEONS = [
    (0, "💀 Склеп Нежити", "Склеп, наполненный древней тьмой.", json.dumps(["skeleton_crossbow", "living_dead"]), "bone_marrow", "Костный мозг", "bone_dragon", 1.1),
    (1, "🌋 Пылающая Кузня", "Реки лавы и раскаленные наковальни.", json.dumps(["magma_slime", "golem_blacksmith"]), "fire_root", "Магматическое ядро", "fire_lord", 1.2),
    (2, "🍄 Топи Забвения", "Ядовитые испарения и топкая грязь.", json.dumps(["poison_slime", "decay_treant"]), "poison_gland", "Ядовитая железа", "spider_queen", 1.1),
    (3, "⏳ Временные Руины", "Место, где искривляются секунды.", json.dumps(["magic_anomaly", "time_mimic"]), "time_tear", "Слеза времени", "time_keeper", 1.0),
    (4, "🩸 Темные Катакомбы", "Шепот сектантов и кровавые алтари.", json.dumps(["cultist_fanatic", "living_dead"]), "demon_blood", "Кровь демона", "abyss_priest", 1.25),
    (5, "🏜 Золотой Мираж", "Пески скрывают иллюзорные богатства.", json.dumps(["goblin_thief", "golden_mimic"]), "gold_petal", "Золотой лепесток", "greed_spirit", 1.15),
    (6, "⚔ Кровавый Колизей", "Арена для сильнейших воинов.", json.dumps(["fallen_champion", "arena_berserk"]), "epic_token", "Эпический жетон", "arena_champ", 1.35)
]
