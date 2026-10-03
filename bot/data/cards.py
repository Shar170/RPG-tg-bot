import json

CARD_SETS = [
    ("set_veg", "Овощи", "Дары природы", "common", "box_common_mats", "forest"),
    ("set_fruit", "Фрукты", "Сладкий урожай", "common", "box_common_mats", "forest"),
    ("set_tools", "Инструменты", "Ремесленный набор", "common", "box_common_mats", "forge"),
    ("set_food", "Еда", "Сытный пир", "uncommon", "box_uncommon_cards", "tavern"),
    ("set_alch", "Алхимия", "Тайные знания", "uncommon", "box_uncommon_cards", "crypt"),
    ("set_beasts", "Звери", "Дикая природа", "uncommon", "box_uncommon_cards", "forest"),
    ("set_weap", "Оружие", "Арсенал героя", "rare", "box_rare_weapon", "forge"),
    ("set_stars", "Светила", "Небесный свод", "rare", "box_rare_armor", "temple"),
    ("set_dark", "Тьма", "Порождения бездны", "rare", "box_rare_weapon", "crypt"),
    ("set_myth", "Мифические", "Легенды Камарии", "epic", "box_epic_mix", "temple"),
    ("set_royal", "Королевские", "Символы власти", "epic", "box_epic_mix", "castle"),
    ("set_anom", "Аномалии", "Искажения ткани мира", "legendary", "box_leg_mix", "abyss")
]

CARDS = [
    ("c_carrot", "Морковь", "🥕", "set_veg", "common"), ("c_tomato", "Томат", "🍅", "set_veg", "common"), ("c_broccoli", "Брокколи", "🥦", "set_veg", "common"), ("c_corn", "Кукуруза", "🌽", "set_veg", "common"), ("c_cucumber", "Огурец", "🥒", "set_veg", "common"), ("c_onion", "Лук", "🧅", "set_veg", "common"),
    ("c_apple", "Яблоко", "🍎", "set_fruit", "common"), ("c_banana", "Банан", "🍌", "set_fruit", "common"), ("c_grape", "Виноград", "🍇", "set_fruit", "common"), ("c_strawb", "Клубника", "🍓", "set_fruit", "common"), ("c_peach", "Персик", "🍑", "set_fruit", "common"), ("c_cherry", "Вишня", "🍒", "set_fruit", "common"),
    ("c_hammer", "Молоток", "🔨", "set_tools", "common"), ("c_axe_tool", "Топор", "🪓", "set_tools", "common"), ("c_wrench", "Ключ", "🔧", "set_tools", "common"), ("c_saw", "Пила", "🪚", "set_tools", "common"), ("c_toolbox", "Ящик", "🧰", "set_tools", "common"), ("c_pickaxe", "Кирка", "⛏", "set_tools", "common"),
    ("c_meat", "Мясо на кости", "🍖", "set_food", "uncommon"), ("c_chicken", "Окорочок", "🍗", "set_food", "uncommon"), ("c_steak", "Стейк", "🥩", "set_food", "uncommon"), ("c_burger", "Бургер", "🍔", "set_food", "uncommon"), ("c_pizza", "Пицца", "🍕", "set_food", "uncommon"), ("c_sandw", "Сэндвич", "🥪", "set_food", "uncommon"),
    ("c_alembic", "Перегонный куб", "⚗️", "set_alch", "uncommon"), ("c_flask", "Колба", "🧪", "set_alch", "uncommon"), ("c_crystal", "Шар", "🔮", "set_alch", "uncommon"), ("c_scroll", "Свиток", "📜", "set_alch", "uncommon"), ("c_candle", "Свеча", "🕯", "set_alch", "uncommon"), ("c_amulet", "Амулет", "🧿", "set_alch", "uncommon"),
    ("c_wolf", "Волк", "🐺", "set_beasts", "uncommon"), ("c_fox", "Лиса", "🦊", "set_beasts", "uncommon"), ("c_bear", "Медведь", "🐻", "set_beasts", "uncommon"), ("c_boar", "Кабан", "🐗", "set_beasts", "uncommon"), ("c_deer", "Олень", "🦌", "set_beasts", "uncommon"), ("c_snake", "Змея", "🐍", "set_beasts", "uncommon"),
    ("c_swords", "Скрещенные мечи", "⚔️", "set_weap", "rare"), ("c_dagger", "Кинжал", "🗡", "set_weap", "rare"), ("c_shield", "Щит", "🛡", "set_weap", "rare"), ("c_bow", "Лук", "🏹", "set_weap", "rare"), ("c_axe_weap", "Боевой топор", "🪓", "set_weap", "rare"), ("c_trident", "Трезубец", "🔱", "set_weap", "rare"),
    ("c_sun", "Солнце", "☀️", "set_stars", "rare"), ("c_moon", "Месяц", "🌙", "set_stars", "rare"), ("c_star1", "Звезда", "⭐", "set_stars", "rare"), ("c_star2", "Сияние", "🌟", "set_stars", "rare"), ("c_star3", "Искры", "✨", "set_stars", "rare"), ("c_star4", "Метеорит", "💫", "set_stars", "rare"),
    ("c_skull", "Череп", "💀", "set_dark", "rare"), ("c_ghost", "Призрак", "👻", "set_dark", "rare"), ("c_bat", "Летучая мышь", "🦇", "set_dark", "rare"), ("c_spider", "Паук", "🕷", "set_dark", "rare"), ("c_web", "Паутина", "🕸", "set_dark", "rare"), ("c_newmoon", "Новолуние", "🌑", "set_dark", "rare"),
    ("c_dragon", "Дракон", "🐉", "set_myth", "epic"), ("c_unicorn", "Единорог", "🦄", "set_myth", "epic"), ("c_dragonhead", "Голова дракона", "🐲", "set_myth", "epic"), ("c_eagle", "Орел", "🦅", "set_myth", "epic"), ("c_fire", "Огонь", "🔥", "set_myth", "epic"), ("c_ice", "Лед", "❄", "set_myth", "epic"),
    ("c_crown", "Корона", "👑", "set_royal", "epic"), ("c_gem", "Драгоценность", "💎", "set_royal", "epic"), ("c_trophy", "Кубок", "🏆", "set_royal", "epic"), ("c_medal", "Орден", "🎖", "set_royal", "epic"), ("c_gold_medal", "Медаль", "🥇", "set_royal", "epic"), ("c_fleur", "Лилия", "⚜", "set_royal", "epic"),
    ("c_vortex", "Вихрь", "🌀", "set_anom", "legendary"), ("c_galaxy", "Галактика", "🌌", "set_anom", "legendary"), ("c_hole", "Дыра", "🕳", "set_anom", "legendary"), ("c_zap", "Разряд", "⚡", "set_anom", "legendary"), ("c_orb", "Сфера", "🔮", "set_anom", "legendary"), ("c_eye", "Око", "👁", "set_anom", "legendary")
]

LOOT_BOXES = [
    ("box_common_mats", "📦 Коробка Ингредиентов", "mats", "common", json.dumps({"count": 5, "gold": 300, "potions": 1}), 1, 100),
    ("box_uncommon_cards", "🎴 Сундук Карточек", "cards", "uncommon", json.dumps({"count": 3}), 1, 100),
    ("box_rare_weapon", "⚔ Оружейный Ящик", "weapon", "rare", json.dumps({"count": 1, "gold": 1000}), 1, 100),
    ("box_rare_armor", "🛡 Ящик Брони", "armor", "rare", json.dumps({"count": 1, "gold": 1000}), 1, 100),
    ("box_epic_mix", "👑 Эпический Дар", "epic_mix", "epic", json.dumps({"equip_count": 2, "gold": 3000}), 1, 100),
    ("box_leg_mix", "🌀 Аномальный Куб", "leg_mix", "legendary", json.dumps({"equip_count": 1, "gold": 7000, "gems": 10}), 1, 100)
]
