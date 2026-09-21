import json

# Формат: (item_id, name, traits_json, base_price)
INGREDIENTS = [
    # --- Базовые лечебные (Чистый хил) ---
    ("cave_mushroom", "Пещерный гриб", json.dumps(["Хил", "Слабость", "Защита от тьмы", "Замедление"], ensure_ascii=False), 10),
    ("light_flower", "Светлый цветок", json.dumps(["Хил", "Свет", "Очищение", "Удача"], ensure_ascii=False), 12),
    ("red_berry", "Кровавая ягода", json.dumps(["Хил", "Вампиризм", "Ожог", "Сила"], ensure_ascii=False), 15),
    ("mountain_moss", "Горный мох", json.dumps(["Броня", "Хил", "Реген ОД", "Уязвимость к огню"], ensure_ascii=False), 10),
    ("water_lily", "Водяная лилия", json.dumps(["Хил", "Мана", "Ускорение", "Хрупкость"], ensure_ascii=False), 14),
    
    # --- Боевые (Урон, Огонь, Яд, Вампиризм) ---
    ("fire_root", "Магматическое ядро", json.dumps(["Урон огнем", "Защита от огня", "Сила", "Ожог"], ensure_ascii=False), 15),
    ("poison_gland", "Ядовитая железа", json.dumps(["Урон ядом", "Ослабление", "Слепота", "Уязвимость"], ensure_ascii=False), 12),
    ("demon_blood", "Кровь демона", json.dumps(["Вампиризм", "Сила тьмы", "Безумие", "Реген ХП"], ensure_ascii=False), 25),
    ("ash_spores", "Пепельные споры", json.dumps(["Урон огнем", "Слепота", "Удушье", "Слабость"], ensure_ascii=False), 13),
    ("swamp_rot", "Болотная гниль", json.dumps(["Урон ядом", "Болезнь", "Замедление", "Ослабление"], ensure_ascii=False), 11),
    ("vampire_bat_wing", "Крыло вампира", json.dumps(["Вампиризм", "Ловкость", "Слепота", "Скорость"], ensure_ascii=False), 18),
    
    # --- Баффы (Ускорение, Броня, ОД) ---
    ("time_tear", "Слеза времени", json.dumps(["Реген ОД", "Ускорение", "Уклонение", "Хрупкость"], ensure_ascii=False), 20),
    ("iron_bark", "Железная кора", json.dumps(["Броня", "Тяжесть", "Сопротивление", "Замедление"], ensure_ascii=False), 16),
    ("wind_feather", "Перо ветра", json.dumps(["Ускорение", "Уклонение", "Легкость", "Хрупкость"], ensure_ascii=False), 14),
    ("coffee_bean", "Кофейное зерно", json.dumps(["Реген ОД", "Бодрость", "Безумие", "Скорость"], ensure_ascii=False), 22),
    
    # --- Экономика и Магия (Удача, Богатство) ---
    ("gold_petal", "Золотой лепесток", json.dumps(["Богатство", "Иллюзия", "Свет", "Удача"], ensure_ascii=False), 50),
    ("leprechaun_clover", "Клевер удачи", json.dumps(["Удача", "Богатство", "Ловкость", "Реген ОД"], ensure_ascii=False), 45),
    ("crystal_shard", "Кристальный осколок", json.dumps(["Мана", "Свет", "Очищение", "Хрупкость"], ensure_ascii=False), 30),
    
    # --- Расширенный список миксов (32 дополнительных) ---
    ("ice_thistle", "Ледяной чертополох", json.dumps(["Урон льдом", "Замедление", "Хрупкость", "Броня"], ensure_ascii=False), 15),
    ("frost_gland", "Морозная железа", json.dumps(["Урон льдом", "Слепота", "Оцепенение", "Защита от льда"], ensure_ascii=False), 18),
    ("sun_stone", "Солнечный камень", json.dumps(["Урон огнем", "Свет", "Очищение", "Слепота"], ensure_ascii=False), 20),
    ("moon_dust", "Лунная пыль", json.dumps(["Иллюзия", "Сон", "Мана", "Уклонение"], ensure_ascii=False), 25),
    ("shadow_essence", "Сущность тени", json.dumps(["Сила тьмы", "Слепота", "Вампиризм", "Уклонение"], ensure_ascii=False), 28),
    ("troll_fat", "Жир тролля", json.dumps(["Реген ХП", "Ослабление", "Замедление", "Броня"], ensure_ascii=False), 12),
    ("goblin_ear", "Ухо гоблина", json.dumps(["Ловкость", "Удача", "Болезнь", "Ускорение"], ensure_ascii=False), 8),
    ("dragon_scale", "Чешуйка дракона", json.dumps(["Броня", "Сопротивление", "Урон огнем", "Сила"], ensure_ascii=False), 60),
    ("harpy_claw", "Коготь гарпии", json.dumps(["Сила", "Кровотечение", "Ловкость", "Ускорение"], ensure_ascii=False), 17),
    ("siren_vocal_cord", "Связка сирены", json.dumps(["Иллюзия", "Безумие", "Сон", "Уязвимость"], ensure_ascii=False), 22),
    ("giant_toe", "Палец великана", json.dumps(["Сила", "Тяжесть", "Хил", "Замедление"], ensure_ascii=False), 35),
    ("pixie_dust", "Пыльца феи", json.dumps(["Полет", "Мана", "Иллюзия", "Легкость"], ensure_ascii=False), 40),
    ("bone_marrow", "Костный мозг", json.dumps(["Сила тьмы", "Реген ХП", "Болезнь", "Ослабление"], ensure_ascii=False), 14),
    ("ecto_plasm", "Эктоплазма", json.dumps(["Иллюзия", "Защита от тьмы", "Страх", "Мана"], ensure_ascii=False), 19),
    ("basilisk_eye", "Глаз василиска", json.dumps(["Оцепенение", "Замедление", "Слепота", "Урон ядом"], ensure_ascii=False), 32),
    ("phoenix_ash", "Пепел феникса", json.dumps(["Реген ХП", "Хил", "Урон огнем", "Свет"], ensure_ascii=False), 75),
    ("mandrake_root", "Корень мандрагоры", json.dumps(["Сон", "Страх", "Безумие", "Хил"], ensure_ascii=False), 26),
    ("silver_leaf", "Серебряный лист", json.dumps(["Очищение", "Свет", "Защита от тьмы", "Броня"], ensure_ascii=False), 21),
    ("blood_rose", "Кровавая роза", json.dumps(["Вампиризм", "Кровотечение", "Соблазн", "Хил"], ensure_ascii=False), 24),
    ("grave_dust", "Могильная пыль", json.dumps(["Сила тьмы", "Страх", "Удушье", "Болезнь"], ensure_ascii=False), 9),
    ("abyssal_pearl", "Жемчужина бездны", json.dumps(["Сила тьмы", "Мана", "Оцепенение", "Слепота"], ensure_ascii=False), 55),
    ("stardust", "Звездная пыль", json.dumps(["Удача", "Мана", "Свет", "Ускорение"], ensure_ascii=False), 65),
    ("coral_fragment", "Фрагмент коралла", json.dumps(["Защита от льда", "Хил", "Тяжесть", "Броня"], ensure_ascii=False), 15),
    ("desert_mirage", "Цветок миража", json.dumps(["Иллюзия", "Сон", "Жажда", "Уклонение"], ensure_ascii=False), 18),
    ("obsidian_shard", "Осколок обсидиана", json.dumps(["Броня", "Урон огнем", "Хрупкость", "Тяжесть"], ensure_ascii=False), 23),
    ("spider_silk", "Паутина", json.dumps(["Замедление", "Оцепенение", "Ловкость", "Уклонение"], ensure_ascii=False), 11),
    ("snake_venom", "Яд кобры", json.dumps(["Урон ядом", "Кровотечение", "Слабость", "Слепота"], ensure_ascii=False), 27),
    ("toad_wart", "Бородавка жабы", json.dumps(["Болезнь", "Урон ядом", "Прыгучесть", "Хил"], ensure_ascii=False), 7),
    ("electric_eel_skin", "Кожа угря", json.dumps(["Урон током", "Ускорение", "Оцепенение", "Ловкость"], ensure_ascii=False), 29),
    ("storm_cloud", "Грозовое облако", json.dumps(["Урон током", "Полет", "Легкость", "Слепота"], ensure_ascii=False), 34),
    ("living_water", "Живая вода", json.dumps(["Хил", "Очищение", "Реген ХП", "Свет"], ensure_ascii=False), 80),
    ("dead_water", "Мертвая вода", json.dumps(["Сила тьмы", "Урон ядом", "Болезнь", "Слабость"], ensure_ascii=False), 50)
]
