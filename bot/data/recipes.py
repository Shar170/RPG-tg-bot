import json

RECIPES = [
    ("rec_iron_sword", "iron_sword", json.dumps({"iron_ingot": 6}), 120),
    ("rec_chainmail", "chainmail", json.dumps({"iron_ingot": 12}), 150),
    ("rec_steel_plate", "steel_plate", json.dumps({"iron_ingot": 18}), 1800),
    ("rec_steel_greatsword", "steel_greatsword", json.dumps({"iron_ingot": 16}), 1000),
    ("rec_smoke_bomb", "smoke_bomb", json.dumps({"iron_ingot": 1, "poison_gland": 1}), 50),
    ("rec_shrapnel_bomb", "shrapnel_bomb", json.dumps({"iron_ingot": 2, "fire_root": 1}), 80),
    ("rec_scroll_weakness", "scroll_weakness", json.dumps({"bone_marrow": 1, "demon_blood": 1}), 120),
    ("rec_time_hourglass", "time_hourglass", json.dumps({"time_tear": 2, "gold_petal": 1}), 350)
]
