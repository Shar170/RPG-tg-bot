# Формат: (location_id, item_id, chance, min_amount, max_amount)
LOOT_TABLES = [
    # --- БАЗОВЫЕ МАТЕРИАЛЫ И ИНГРЕДИЕНТЫ (Обычные подземелья) ---
    # Лес (forest)
    ("forest", "iron_ingot", 0.70, 1, 3),
    ("forest", "leather_scrap", 0.80, 2, 4), # Добавь в items.py, если еще нет
    ("forest", "cloth_scrap", 0.80, 2, 5),   # Добавь в items.py, если еще нет
    ("forest", "cave_mushroom", 0.50, 1, 2),
    ("forest", "red_berry", 0.60, 1, 3),
    ("forest", "goblin_ear", 0.40, 1, 2),
    
    # Склеп (crypt)
    ("crypt", "iron_ingot", 0.80, 2, 4),
    ("crypt", "leather_scrap", 0.50, 1, 3),
    ("crypt", "cloth_scrap", 0.70, 2, 4),
    ("crypt", "bone_marrow", 0.55, 1, 2),
    ("crypt", "grave_dust", 0.65, 1, 3),
    ("crypt", "spider_silk", 0.40, 1, 2),
    ("crypt", "demon_blood", 0.20, 1, 1),
    
    # Храм (temple)
    ("temple", "iron_ingot", 0.90, 3, 6),
    ("temple", "gold_petal", 0.25, 1, 1),
    ("temple", "sun_stone", 0.35, 1, 1),
    ("temple", "crystal_shard", 0.45, 1, 2),
    ("temple", "silver_leaf", 0.30, 1, 2),
    
    # --- СПЕЦИАЛЬНЫЕ ИВЕНТЫ И ЛОКАЦИИ ---
    # Ивент Колизей
    ("event_6", "iron_ingot", 1.0, 5, 10),
    ("event_6", "epic_token", 0.5, 1, 2),
    
    # --- РЕЛИКВИИ И АРТЕФАКТЫ (Боссы) ---
    ("solo", "art_cursed_blade", 0.05, 1, 1),
    ("solo", "art_frost_mourne", 0.03, 1, 1),
    ("solo", "art_thunder_fury", 0.02, 1, 1),
    ("solo", "art_blood_drinker", 0.01, 1, 1),
    ("event_6", "art_world_breaker", 0.01, 1, 1),
    
    # Дроп эксклюзивных артефактов
    ("solo", "art_dragon_heart", 0.04, 1, 1),
    ("solo", "art_shadow_cloak", 0.04, 1, 1),
    ("solo", "art_demonic_pact", 0.03, 1, 1),
    ("solo", "art_aegis_shard", 0.02, 1, 1),
    ("event_6", "art_blood_stone", 0.02, 1, 1)
]
