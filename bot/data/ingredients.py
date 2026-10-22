import json

# Формат: (item_id, name, traits_json, base_price)
INGREDIENTS = [
    # --- Базовые лечебные (Чистый хил) ---
    ("cave_mushroom", "Пещерный гриб", json.dumps(["heal", "weakness", "dark_protection", "slow"], ensure_ascii=False), 10),
    ("light_flower", "Светлый цветок", json.dumps(["heal", "light", "cleanse", "luck"], ensure_ascii=False), 12),
    ("red_berry", "Кровавая ягода", json.dumps(["heal", "vampirism", "burn", "strength"], ensure_ascii=False), 15),
    ("mountain_moss", "Горный мох", json.dumps(["armor", "heal", "ap_regen", "fire_vulnerability"], ensure_ascii=False), 10),
    ("water_lily", "Водяная лилия", json.dumps(["heal", "mana", "haste", "fragility"], ensure_ascii=False), 14),
    
    # --- Боевые (Урон, Огонь, Яд, Вампиризм) ---
    ("fire_root", "Магматическое ядро", json.dumps(["fire_damage", "fire_protection", "strength", "burn"], ensure_ascii=False), 15),
    ("poison_gland", "Ядовитая железа", json.dumps(["poison_damage", "weakening", "blind", "vulnerability"], ensure_ascii=False), 12),
    ("demon_blood", "Кровь демона", json.dumps(["vampirism", "dark_power", "madness", "hp_regen"], ensure_ascii=False), 25),
    ("ash_spores", "Пепельные споры", json.dumps(["fire_damage", "blind", "suffocation", "weakness"], ensure_ascii=False), 13),
    ("swamp_rot", "Болотная гниль", json.dumps(["poison_damage", "disease", "slow", "weakening"], ensure_ascii=False), 11),
    ("vampire_bat_wing", "Крыло вампира", json.dumps(["vampirism", "agility", "blind", "speed"], ensure_ascii=False), 18),
    
    # --- Баффы (Ускорение, Броня, ОД) ---
    ("time_tear", "Слеза времени", json.dumps(["ap_regen", "haste", "dodge", "fragility"], ensure_ascii=False), 20),
    ("iron_bark", "Железная кора", json.dumps(["armor", "heaviness", "resistance", "slow"], ensure_ascii=False), 16),
    ("wind_feather", "Перо ветра", json.dumps(["haste", "dodge", "lightness", "fragility"], ensure_ascii=False), 14),
    ("coffee_bean", "Кофейное зерно", json.dumps(["ap_regen", "vigor", "madness", "speed"], ensure_ascii=False), 22),
    
    # --- Экономика и Магия (Удача, Богатство) ---
    ("gold_petal", "Золотой лепесток", json.dumps(["wealth", "illusion", "light", "luck"], ensure_ascii=False), 50),
    ("leprechaun_clover", "Клевер удачи", json.dumps(["luck", "wealth", "agility", "ap_regen"], ensure_ascii=False), 45),
    ("crystal_shard", "Кристальный осколок", json.dumps(["mana", "light", "cleanse", "fragility"], ensure_ascii=False), 30),
    
    # --- Расширенный список миксов (32 дополнительных) ---
    ("ice_thistle", "Ледяной чертополох", json.dumps(["ice_damage", "slow", "fragility", "armor"], ensure_ascii=False), 15),
    ("frost_gland", "Морозная железа", json.dumps(["ice_damage", "blind", "paralysis", "ice_protection"], ensure_ascii=False), 18),
    ("sun_stone", "Солнечный камень", json.dumps(["fire_damage", "light", "cleanse", "blind"], ensure_ascii=False), 20),
    ("moon_dust", "Лунная пыль", json.dumps(["illusion", "sleep", "mana", "dodge"], ensure_ascii=False), 25),
    ("shadow_essence", "Сущность тени", json.dumps(["dark_power", "blind", "vampirism", "dodge"], ensure_ascii=False), 28),
    ("troll_fat", "Жир тролля", json.dumps(["hp_regen", "weakening", "slow", "armor"], ensure_ascii=False), 12),
    ("goblin_ear", "Ухо гоблина", json.dumps(["agility", "luck", "disease", "haste"], ensure_ascii=False), 8),
    ("dragon_scale", "Чешуйка дракона", json.dumps(["armor", "resistance", "fire_damage", "strength"], ensure_ascii=False), 60),
    ("harpy_claw", "Коготь гарпии", json.dumps(["strength", "bleed", "agility", "haste"], ensure_ascii=False), 17),
    ("siren_vocal_cord", "Связка сирены", json.dumps(["illusion", "madness", "sleep", "vulnerability"], ensure_ascii=False), 22),
    ("giant_toe", "Палец великана", json.dumps(["strength", "heaviness", "heal", "slow"], ensure_ascii=False), 35),
    ("pixie_dust", "Пыльца феи", json.dumps(["flight", "mana", "illusion", "lightness"], ensure_ascii=False), 40),
    ("bone_marrow", "Костный мозг", json.dumps(["dark_power", "hp_regen", "disease", "weakening"], ensure_ascii=False), 14),
    ("ecto_plasm", "Эктоплазма", json.dumps(["illusion", "dark_protection", "fear", "mana"], ensure_ascii=False), 19),
    ("basilisk_eye", "Глаз василиска", json.dumps(["paralysis", "slow", "blind", "poison_damage"], ensure_ascii=False), 32),
    ("phoenix_ash", "Пепел феникса", json.dumps(["hp_regen", "heal", "fire_damage", "light"], ensure_ascii=False), 75),
    ("mandrake_root", "Корень мандрагоры", json.dumps(["sleep", "fear", "madness", "heal"], ensure_ascii=False), 26),
    ("silver_leaf", "Серебряный лист", json.dumps(["cleanse", "light", "dark_protection", "armor"], ensure_ascii=False), 21),
    ("blood_rose", "Кровавая роза", json.dumps(["vampirism", "bleed", "charm", "heal"], ensure_ascii=False), 24),
    ("grave_dust", "Могильная пыль", json.dumps(["dark_power", "fear", "suffocation", "disease"], ensure_ascii=False), 9),
    ("abyssal_pearl", "Жемчужина бездны", json.dumps(["dark_power", "mana", "paralysis", "blind"], ensure_ascii=False), 55),
    ("stardust", "Звездная пыль", json.dumps(["luck", "mana", "light", "haste"], ensure_ascii=False), 65),
    ("coral_fragment", "Фрагмент коралла", json.dumps(["ice_protection", "heal", "heaviness", "armor"], ensure_ascii=False), 15),
    ("desert_mirage", "Цветок миража", json.dumps(["illusion", "sleep", "thirst", "dodge"], ensure_ascii=False), 18),
    ("obsidian_shard", "Осколок обсидиана", json.dumps(["armor", "fire_damage", "fragility", "heaviness"], ensure_ascii=False), 23),
    ("spider_silk", "Паутина", json.dumps(["slow", "paralysis", "agility", "dodge"], ensure_ascii=False), 11),
    ("snake_venom", "Яд кобры", json.dumps(["poison_damage", "bleed", "weakness", "blind"], ensure_ascii=False), 27),
    ("toad_wart", "Бородавка жабы", json.dumps(["disease", "poison_damage", "jumping", "heal"], ensure_ascii=False), 7),
    ("electric_eel_skin", "Кожа угря", json.dumps(["shock_damage", "haste", "paralysis", "agility"], ensure_ascii=False), 29),
    ("storm_cloud", "Грозовое облако", json.dumps(["shock_damage", "flight", "lightness", "blind"], ensure_ascii=False), 34),
    ("living_water", "Живая вода", json.dumps(["heal", "cleanse", "hp_regen", "light"], ensure_ascii=False), 80),
    ("dead_water", "Мертвая вода", json.dumps(["dark_power", "poison_damage", "disease", "weakness"], ensure_ascii=False), 50)
]
