import json

BESTIARY = [
    ("temple_guard", "Храмовый Страж", 55, 75, 12, 18, "front", json.dumps({"counter": 0.25, "weak": ["shock"]}), 6, 14, 12),
    ("living_idol", "Оживший Идол", 80, 110, 14, 22, "front", json.dumps({"heal": 0.15, "immune": ["bleed", "poison"], "resist": ["physical"], "weak": ["shock"]}), 8, 18, 16),
    ("khmer_priest", "Кхмерский Жрец", 45, 60, 18, 28, "back", json.dumps({"dodge": 0.2, "reposition": 0.6, "weak": ["dark"]}), 10, 22, 15),
    ("poison_slime", "Токсичный Слизень", 35, 50, 8, 14, "front", json.dumps({"poison": 0.35, "immune": ["poison", "bleed"], "weak": ["fire", "ice"]}), 4, 10, 10),
    ("skeleton_crossbow", "Скелет-арбалетчик", 40, 55, 16, 24, "back", json.dumps({"dodge": 0.15, "reposition": 0.7, "immune": ["poison", "bleed"], "weak": ["light", "fire"]}), 6, 15, 12),
    ("living_dead", "Оживший Мертвец", 60, 80, 10, 16, "front", json.dumps({"poison": 0.15, "immune": ["poison", "bleed"], "weak": ["light", "fire"]}), 5, 12, 11),
    ("magma_slime", "Магматический Слизень", 65, 85, 16, 24, "front", json.dumps({"burn": 0.3, "immune": ["fire", "poison", "bleed"], "weak": ["ice"]}), 8, 16, 15),
    ("golem_blacksmith", "Голем-кузнец", 110, 140, 20, 30, "front", json.dumps({"counter": 0.35, "immune": ["poison", "bleed"], "resist": ["physical", "fire"], "weak": ["shock"]}), 12, 25, 22),
    ("decay_treant", "Гнилой Энт", 95, 130, 15, 25, "front", json.dumps({"heal": 0.2, "poison": 0.2, "immune": ["poison"], "weak": ["fire"]}), 10, 20, 18),
    ("magic_anomaly", "Магическая Аномалия", 50, 70, 22, 35, "back", json.dumps({"dodge": 0.25, "immune": ["bleed"], "resist": ["dark", "shock"]}), 12, 24, 20),
    ("time_mimic", "Мимик-часовщик", 70, 95, 18, 26, "front", json.dumps({"counter": 0.2, "immune": ["bleed"], "weak": ["shock"]}), 15, 30, 25),
    ("cultist_fanatic", "Культист-фанатик", 60, 80, 20, 32, "back", json.dumps({"burn": 0.2, "resist": ["dark"], "weak": ["light"]}), 10, 20, 18),
    ("goblin_thief", "Гоблин-вор", 40, 55, 12, 20, "front", json.dumps({"dodge": 0.35, "reposition": 0.8, "weak": ["poison"]}), 18, 40, 15),
    ("golden_mimic", "Золотой Мимик", 120, 160, 22, 34, "front", json.dumps({"counter": 0.3, "immune": ["poison", "bleed"], "weak": ["shock"]}), 45, 90, 40),
    ("fallen_champion", "Падший Чемпион", 100, 130, 24, 38, "front", json.dumps({"counter": 0.3, "weak": ["light"]}), 15, 30, 30),
    ("arena_berserk", "Берсерк Арены", 85, 115, 28, 45, "front", json.dumps({"burn": 0.15, "weak": ["ice"]}), 14, 28, 28),
    ("time_keeper", "Хранитель Времени", 180, 220, 22, 34, "back", json.dumps({"dodge": 0.15, "reposition": 0.5, "resist": ["shock"], "weak": ["dark"]}), 45, 75, 80),
    ("spider_queen", "Королева Пауков", 220, 270, 24, 36, "back", json.dumps({"poison": 0.5, "dodge": 0.2, "immune": ["poison"], "weak": ["fire"]}), 50, 85, 95),
    ("fire_lord", "Лорд Огня", 280, 340, 30, 44, "front", json.dumps({"burn": 0.45, "counter": 0.2, "immune": ["fire"], "weak": ["ice"]}), 70, 110, 120),
    ("bone_dragon", "Костяной Дракон", 340, 420, 35, 52, "front", json.dumps({"counter": 0.25, "heal": 0.1, "immune": ["poison", "bleed"], "weak": ["light", "fire"]}), 90, 140, 160),
    ("abyss_priest", "Жрец Бездны", 240, 300, 28, 42, "back", json.dumps({"dodge": 0.2, "heal": 0.2, "immune": ["dark"], "weak": ["light"]}), 60, 95, 110),
    ("greed_spirit", "Дух Алчности", 260, 320, 26, 40, "front", json.dumps({"dodge": 0.25, "counter": 0.2, "immune": ["bleed"], "weak": ["dark", "light"]}), 100, 180, 130),
    ("arena_champ", "Чемпион Колизея", 320, 390, 34, 50, "front", json.dumps({"counter": 0.35, "resist": ["physical"], "weak": ["poison", "ice"]}), 80, 130, 150)
]
