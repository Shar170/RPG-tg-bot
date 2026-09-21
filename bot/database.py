import sqlite3
import json
import datetime
import random
import time
from config import DB_PATH
from data.ingredients import INGREDIENTS

def get_connection():
    return sqlite3.connect(DB_PATH)

def init_db():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, username TEXT, state TEXT, hp INTEGER, max_hp INTEGER,
            gold INTEGER, inventory TEXT, home_data TEXT, combat_data TEXT, known_traits TEXT, dungeon_data TEXT,
            level INTEGER DEFAULT 1, xp INTEGER DEFAULT 0, clan_id INTEGER DEFAULT 0, gems INTEGER DEFAULT 0, quests_data TEXT DEFAULT '{}', clan_role TEXT DEFAULT 'thrall',
            energy INTEGER DEFAULT 5, last_energy_time INTEGER DEFAULT 0)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS daily_dungeons (
            day_index INTEGER PRIMARY KEY, name TEXT, desc TEXT, mobs TEXT, loot_id TEXT, loot_name TEXT, boss_id TEXT, mob_modifier REAL)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS bestiary (
            mob_id TEXT PRIMARY KEY, name TEXT, hp_min INTEGER, hp_max INTEGER, dmg_min INTEGER, dmg_max INTEGER, row_pref TEXT, skills TEXT, gold_min INTEGER DEFAULT 5, gold_max INTEGER DEFAULT 15, xp_reward INTEGER DEFAULT 10)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS alchemy_ingredients (
            item_id TEXT PRIMARY KEY, name TEXT, traits TEXT, base_price INTEGER DEFAULT 10)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS items (
            item_id TEXT PRIMARY KEY, name TEXT, type TEXT, base_price INTEGER, stats TEXT)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS recipes (
            recipe_id TEXT PRIMARY KEY, result_item_id TEXT, materials_needed TEXT, gold_cost INTEGER)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS loot_tables (
            id INTEGER PRIMARY KEY AUTOINCREMENT, location_id TEXT, item_id TEXT, chance REAL, min_amount INTEGER, max_amount INTEGER)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS game_settings (
            key TEXT PRIMARY KEY, value TEXT)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS clans (
            clan_id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, leader_id INTEGER, treasury INTEGER DEFAULT 0, level INTEGER DEFAULT 1, 
            weekly_raids INTEGER DEFAULT 0, join_requests TEXT DEFAULT '[]', clan_vault TEXT DEFAULT '{"gold": 0, "items": {}}')''')
            
        try: cursor.execute("ALTER TABLE users ADD COLUMN level INTEGER DEFAULT 1")
        except: pass
        try: cursor.execute("ALTER TABLE users ADD COLUMN xp INTEGER DEFAULT 0")
        except: pass
        try: cursor.execute("ALTER TABLE users ADD COLUMN clan_id INTEGER DEFAULT 0")
        except: pass
        try: cursor.execute("ALTER TABLE users ADD COLUMN gems INTEGER DEFAULT 0")
        except: pass
        try: cursor.execute("ALTER TABLE users ADD COLUMN quests_data TEXT DEFAULT '{}'")
        except: pass
        try: cursor.execute("ALTER TABLE users ADD COLUMN clan_role TEXT DEFAULT 'thrall'")
        except: pass
        try: cursor.execute("ALTER TABLE users ADD COLUMN energy INTEGER DEFAULT 5")
        except: pass
        try: cursor.execute("ALTER TABLE users ADD COLUMN last_energy_time INTEGER DEFAULT 0")
        except: pass
        try: cursor.execute("ALTER TABLE daily_dungeons ADD COLUMN boss_id TEXT DEFAULT 'time_keeper'")
        except: pass
        try: cursor.execute("ALTER TABLE daily_dungeons ADD COLUMN mob_modifier REAL DEFAULT 1.0")
        except: pass
        try: cursor.execute("ALTER TABLE bestiary ADD COLUMN skills TEXT DEFAULT '{}'")
        except: pass
        try: cursor.execute("ALTER TABLE bestiary ADD COLUMN gold_min INTEGER DEFAULT 5")
        except: pass
        try: cursor.execute("ALTER TABLE bestiary ADD COLUMN gold_max INTEGER DEFAULT 15")
        except: pass
        try: cursor.execute("ALTER TABLE bestiary ADD COLUMN xp_reward INTEGER DEFAULT 10")
        except: pass
        try: cursor.execute("ALTER TABLE alchemy_ingredients ADD COLUMN base_price INTEGER DEFAULT 10")
        except: pass
        try: cursor.execute("ALTER TABLE clans ADD COLUMN weekly_raids INTEGER DEFAULT 0")
        except: pass
        try: cursor.execute("ALTER TABLE clans ADD COLUMN join_requests TEXT DEFAULT '[]'")
        except: pass
        try: cursor.execute("ALTER TABLE clans ADD COLUMN clan_vault TEXT DEFAULT '{\"gold\": 0, \"items\": {}}'")
        except: pass
        conn.commit()

def seed_all():
    with get_connection() as conn:
        cursor = conn.cursor()
        default_dungeons = [
            (0, "💀 Склеп", "Во тьме.", json.dumps(["skeleton_crossbow", "Оживший Мертвец"]), "cave_mushroom", "Костяная пыль", "bone_dragon", 1.2),
            (1, "🌋 Кузня", "Магма.", json.dumps(["Магматический Слизень", "Голем-кузнец"]), "fire_root", "Магматическое ядро", "fire_lord", 1.3),
            (2, "🍄 Топи", "Кислота.", json.dumps(["poison_slime", "Гнилой Энт"]), "poison_gland", "Ядовитая железа", "spider_queen", 1.1),
            (3, "⏳ Руины", "Камни.", json.dumps(["Магическая Аномалия", "Мимик-часовщик"]), "time_tear", "Слеза времени", "time_keeper", 1.0),
            (4, "🩸 Катакомбы", "Руны.", json.dumps(["Культист-фанатик", "Жрец Бездны"]), "demon_blood", "Кровь демона", "abyss_priest", 1.4),
            (5, "🏜 Мираж", "Иллюзии.", json.dumps(["Гоблин-вор", "Золотой Мимик"]), "gold_petal", "Золотой лепесток", "greed_spirit", 1.0),
            (6, "⚔️ Колизей", "Арена.", json.dumps(["Падший Чемпион", "Берсерк Арены"]), "epic_token", "Эпический жетон", "arena_champ", 1.5)
        ]
        cursor.executemany("INSERT OR IGNORE INTO daily_dungeons VALUES (?, ?, ?, ?, ?, ?, ?, ?)", default_dungeons)

        mobs = [
            ("temple_guard", "Храмовый Страж", 50, 70, 10, 18, "front", json.dumps({"counter": 0.3}), 8, 20, 15),
            ("living_idol", "Оживший Идол", 80, 110, 15, 25, "front", json.dumps({"heal": 0.2}), 15, 30, 25),
            ("khmer_priest", "Кхмерский Жрец", 40, 55, 20, 35, "back", json.dumps({"dodge": 0.2, "reposition": 0.8}), 10, 25, 20),
            ("poison_slime", "Токсичный Слизень", 30, 45, 8, 12, "front", json.dumps({"poison": 0.4}), 2, 10, 10),
            ("skeleton_crossbow", "Скелет-арбалетчик", 35, 50, 15, 20, "back", json.dumps({"dodge": 0.1, "reposition": 0.9}), 5, 15, 12),
            ("time_keeper", "Хранитель Времени", 200, 250, 25, 40, "back", json.dumps({"dodge": 0.15, "counter": 0.15, "reposition": 0.5}), 50, 100, 150),
            ("fire_lord", "Лорд Огня", 300, 350, 35, 50, "front", json.dumps({"burn": 0.5, "counter": 0.2}), 60, 120, 200),
            ("spider_queen", "Королева Пауков", 250, 300, 20, 30, "back", json.dumps({"poison": 0.6, "dodge": 0.3, "reposition": 0.8}), 45, 90, 180),
            ("bone_dragon", "Костяной Дракон", 350, 400, 40, 60, "front", json.dumps({"counter": 0.25, "heal": 0.1}), 100, 200, 300)
        ]
        cursor.executemany("INSERT OR IGNORE INTO bestiary (mob_id, name, hp_min, hp_max, dmg_min, dmg_max, row_pref, skills, gold_min, gold_max, xp_reward) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", mobs)

        cursor.executemany("INSERT OR IGNORE INTO alchemy_ingredients VALUES (?, ?, ?, ?)", INGREDIENTS)

        items = [
            ("ragout", "Сытное рагу", "consumable", 20, "{}"), ("health_potion", "Зелье: Хил", "consumable", 30, "{}"),
            ("repair_kit", "Рем-набор", "consumable", 50, "{}"), ("khmer_amulet", "Амулет Жизни", "artifact", 1500, "{}"),
            ("smoke_bomb", "Дымовая бомба", "artifact", 120, "{}"), ("iron_ingot", "Железный слиток", "material", 15, "{}"),
            ("epic_token", "Эпический жетон", "material", 200, "{}"),
            ("wood_sword", "Деревянный меч", "weapon", 25, json.dumps({"dmg": 12, "range": "melee"})),
            ("iron_sword", "Стальной меч", "weapon", 250, json.dumps({"dmg": 28, "range": "melee"})),
            ("steel_greatsword", "Стальной двуручник", "weapon", 2500, json.dumps({"dmg": 55, "range": "melee"})),
            ("mithril_blade", "Мифриловый Клинок", "weapon", 12000, json.dumps({"dmg": 90, "range": "melee"})),
            ("demon_scythe", "Коса Демона", "weapon", 35000, json.dumps({"dmg": 150, "range": "melee"})),
            ("god_slayer", "Убийца Богов", "weapon", 85000, json.dumps({"dmg": 250, "range": "melee"})),
            ("short_bow", "Охотничий лук", "weapon", 80, json.dumps({"dmg": 18, "range": "ranged"})),
            ("longbow", "Длинный лук", "weapon", 800, json.dumps({"dmg": 40, "range": "ranged"})),
            ("heavy_crossbow", "Тяжелый арбалет", "weapon", 4000, json.dumps({"dmg": 75, "range": "ranged"})),
            ("elven_bow", "Эльфийский лук", "weapon", 18000, json.dumps({"dmg": 120, "range": "ranged"})),
            ("dragon_breath_staff", "Посох Дыхания Дракона", "weapon", 50000, json.dumps({"dmg": 180, "range": "ranged"})),
            ("leather_armor", "Кожаная броня", "armor", 20, json.dumps({"def": 5})),
            ("chainmail", "Кольчуга", "armor", 400, json.dumps({"def": 15})),
            ("steel_plate", "Стальные Латы", "armor", 3000, json.dumps({"def": 40})),
            ("mithril_plate", "Мифриловый Доспех", "armor", 15000, json.dumps({"def": 80})),
            ("dragonbone_armor", "Драконья Чешуя", "armor", 40000, json.dumps({"def": 130})),
            ("titan_fortress", "Титановая Крепость", "armor", 90000, json.dumps({"def": 220}))
        ]
        cursor.executemany("INSERT OR IGNORE INTO items VALUES (?, ?, ?, ?, ?)", items)
        
        # ДОБАВИЛ БОЛЬШЕ РЕЦЕПТОВ ДЛЯ ЖЕЛЕЗНОЙ РУДЫ (iron_ingot)
        recipes = [
            ("rec_iron_sword", "iron_sword", json.dumps({"iron_ingot": 5}), 100), 
            ("rec_chainmail", "chainmail", json.dumps({"iron_ingot": 12}), 200),
            ("rec_steel_plate", "steel_plate", json.dumps({"iron_ingot": 25}), 800),
            ("rec_repair_kit", "repair_kit", json.dumps({"iron_ingot": 3}), 50),
            ("rec_smoke_bomb", "smoke_bomb", json.dumps({"iron_ingot": 1, "cave_mushroom": 2}), 70)
        ]
        cursor.executemany("INSERT OR IGNORE INTO recipes VALUES (?, ?, ?, ?)", recipes)
        
        # УМНОЕ ОБНОВЛЕНИЕ ЛУТА (чтобы новые ингредиенты начали падать)
        cursor.execute("SELECT DISTINCT item_id FROM loot_tables")
        existing_loot = set(row[0] for row in cursor.fetchall())
        
        locations = ["solo", "event_0", "event_1", "event_2", "event_3", "event_4", "event_5", "event_6"]
        missing_loot = []
        
        # Добавляем базовые предметы, если их нет
        if "iron_ingot" not in existing_loot:
            missing_loot.append(("solo", "iron_ingot", 0.45, 1, 2))
        if "wood_sword" not in existing_loot:
            missing_loot.append(("solo", "wood_sword", 0.05, 1, 1))
        if "epic_token" not in existing_loot:
            missing_loot.append(("event_6", "epic_token", 0.5, 1, 1))
            
        # Добавляем все пропущенные ингредиенты алхимии
        for ing in INGREDIENTS:
            if ing[0] not in existing_loot:
                loc = random.choice(locations)
                missing_loot.append((loc, ing[0], random.uniform(0.3, 0.7), 1, 3))
                
        if missing_loot:
            cursor.executemany("INSERT INTO loot_tables (location_id, item_id, chance, min_amount, max_amount) VALUES (?, ?, ?, ?, ?)", missing_loot)
        
        settings = [("flee_loss_percent", "0.3"), ("base_unarmed_dmg", "5")]
        cursor.executemany("INSERT OR IGNORE INTO game_settings VALUES (?, ?)", settings)
        conn.commit()

def get_user(user_id: int):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()
        if user:
            columns = [desc[0] for desc in cursor.description]
            u_dict = dict(zip(columns, user))
            for json_field in ['inventory', 'home_data', 'combat_data', 'known_traits', 'dungeon_data', 'quests_data']:
                if u_dict.get(json_field): u_dict[json_field] = json.loads(u_dict[json_field])
                else: u_dict[json_field] = {}
                
            now = int(time.time())
            energy = u_dict.get('energy', 5)
            last_time = u_dict.get('last_energy_time', now)
            if energy is None: energy = 5
            if last_time is None or last_time == 0: last_time = now

            if energy < 5:
                elapsed = now - last_time
                gained = elapsed // 7200
                if gained > 0:
                    energy = min(5, energy + gained)
                    last_time += gained * 7200
                    if energy == 5: last_time = now
                    cursor.execute("UPDATE users SET energy=?, last_energy_time=? WHERE user_id=?", (energy, last_time, user_id))
                    conn.commit()

            u_dict['energy'] = energy
            u_dict['last_energy_time'] = last_time
            u_dict['next_energy_in'] = 7200 - (now - last_time) if energy < 5 else 0
            
            return u_dict
    return None

def update_user(user_id: int, **kwargs):
    with get_connection() as conn:
        cursor = conn.cursor()
        for key, value in kwargs.items():
            if key in ['inventory', 'home_data', 'combat_data', 'known_traits', 'dungeon_data', 'quests_data']: 
                value = json.dumps(value, ensure_ascii=False)
            cursor.execute(f"UPDATE users SET {key} = ? WHERE user_id = ?", (value, user_id))
        conn.commit()

def consume_energy(user_id: int, amount: int = 1) -> bool:
    user = get_user(user_id)
    if user['energy'] >= amount:
        new_energy = user['energy'] - amount
        new_time = int(time.time()) if user['energy'] == 5 else user['last_energy_time']
        update_user(user_id, energy=new_energy, last_energy_time=new_time)
        return True
    return False

def get_clan(clan_id: int):
    with get_connection() as conn:
        row = conn.cursor().execute("SELECT * FROM clans WHERE clan_id = ?", (clan_id,)).fetchone()
        if row: return {"clan_id": row[0], "name": row[1], "leader_id": row[2], "treasury": row[3], "level": row[4], "weekly_raids": row[5], "join_requests": json.loads(row[6]), "clan_vault": row[7]}
    return None

def get_clan_by_name(name: str):
    with get_connection() as conn:
        row = conn.cursor().execute("SELECT * FROM clans WHERE name = ?", (name,)).fetchone()
        if row: return {"clan_id": row[0], "name": row[1], "leader_id": row[2], "treasury": row[3], "level": row[4], "weekly_raids": row[5], "join_requests": json.loads(row[6]), "clan_vault": row[7]}
    return None

def update_clan(clan_id: int, **kwargs):
    with get_connection() as conn:
        cursor = conn.cursor()
        for key, value in kwargs.items():
            if key in ['join_requests']: value = json.dumps(value, ensure_ascii=False)
            cursor.execute(f"UPDATE clans SET {key} = ? WHERE clan_id = ?", (value, clan_id))
        conn.commit()

def get_top_clans(limit=3):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name, weekly_raids FROM clans ORDER BY weekly_raids DESC LIMIT ?", (limit,))
        return [{"name": row[0], "weekly_raids": row[1]} for row in cursor.fetchall()]

def get_clan_members(clan_id: int):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, username, level, clan_role, state FROM users WHERE clan_id = ?", (clan_id,))
        return [{"user_id": r[0], "username": r[1], "level": r[2], "clan_role": r[3], "state": r[4]} for r in cursor.fetchall()]

def check_and_generate_quests(user_id):
    user = get_user(user_id)
    quests_data = user.get('quests_data', {})
    today = datetime.datetime.today().strftime('%Y-%m-%d')
    types_present = [q.get("type") for q in quests_data.get("quests", [])]
    has_duplicates = len(types_present) != len(set(types_present))
    if quests_data.get("date") != today or has_duplicates:
        categories = [[{"type": "kill_mobs", "desc": "Убить 5 монстров", "target": 5}, {"type": "kill_mobs", "desc": "Убить 15 монстров", "target": 15}], [{"type": "raid_success", "desc": "Зачистить 1 подземелье", "target": 1}, {"type": "raid_success", "desc": "Зачистить 3 подземелья", "target": 3}], [{"type": "craft_items", "desc": "Скрафтить 1 предмет", "target": 1}, {"type": "craft_items", "desc": "Скрафтить 3 предмета", "target": 3}]]
        selected = [random.choice(cat) for cat in categories]
        random.shuffle(selected)
        for q in selected: q["progress"] = 0; q["completed"] = False
        quests_data = {"date": today, "quests": selected, "claimed": False}
        update_user(user_id, quests_data=quests_data)
    return quests_data

def add_quest_progress(user_id: int, q_type: str, amount: int = 1):
    user = get_user(user_id)
    if not user: return
    quests_data = check_and_generate_quests(user_id)
    changed = False
    for q in quests_data.get("quests", []):
        if q["type"] == q_type and not q["completed"]:
            q["progress"] += amount
            if q["progress"] >= q["target"]: q["progress"] = q["target"]; q["completed"] = True
            changed = True
    if changed: update_user(user_id, quests_data=quests_data)

def get_setting(key: str, default: str) -> str:
    with get_connection() as conn:
        res = conn.cursor().execute("SELECT value FROM game_settings WHERE key = ?", (key,)).fetchone()
        return res[0] if res else default

def get_today_dungeon():
    day_index = datetime.datetime.today().weekday()
    with get_connection() as conn:
        row = conn.cursor().execute("SELECT * FROM daily_dungeons WHERE day_index = ?", (day_index,)).fetchone()
        if row: return {"name": row[1], "desc": row[2], "mobs": json.loads(row[3]), "loot": row[4], "loot_name": row[5], "boss_id": row[6], "mob_modifier": row[7]}
    return None

def get_mob_by_name(name: str):
    with get_connection() as conn:
        row = conn.cursor().execute("SELECT * FROM bestiary WHERE name = ? OR mob_id = ?", (name, name)).fetchone()
        if row: return {"mob_id": row[0], "name": row[1], "hp_min": row[2], "hp_max": row[3], "dmg_min": row[4], "dmg_max": row[5], "row_pref": row[6], "skills": json.loads(row[7] if row[7] else "{}"), "gold_min": row[8] if len(row)>8 and row[8] else 5, "gold_max": row[9] if len(row)>9 and row[9] else 15, "xp_reward": row[10] if len(row)>10 and row[10] else 10}
    return {"mob_id": "unknown", "name": name, "hp_min": 40, "hp_max": 50, "dmg_min": 10, "dmg_max": 15, "row_pref": "front", "skills": {}, "gold_min": 5, "gold_max": 15, "xp_reward": 10}

def get_all_ingredients():
    with get_connection() as conn: return {row[0]: {"name": row[1], "traits": json.loads(row[2])} for row in conn.cursor().execute("SELECT * FROM alchemy_ingredients").fetchall()}

def get_item(item_id: str):
    with get_connection() as conn:
        row = conn.cursor().execute("SELECT * FROM items WHERE item_id = ?", (item_id,)).fetchone()
        if row: return {"item_id": row[0], "name": row[1], "type": row[2], "base_price": row[3], "stats": json.loads(row[4])}
    return None

def get_all_recipes():
    with get_connection() as conn: return [{"recipe_id": r[0], "result_item_id": r[1], "materials": json.loads(r[2]), "gold": r[3]} for r in conn.cursor().execute("SELECT * FROM recipes").fetchall()]

def get_loot_table(location_id: str):
    with get_connection() as conn: return [{"item_id": r[0], "chance": r[1], "min": r[2], "max": r[3]} for r in conn.cursor().execute("SELECT item_id, chance, min_amount, max_amount FROM loot_tables WHERE location_id = ?", (location_id,)).fetchall()]

def get_item_name(item_id: str) -> str:
    with get_connection() as conn:
        cursor = conn.cursor()
        res = cursor.execute("SELECT name FROM items WHERE item_id = ?", (item_id,)).fetchone()
        if res: return res[0]
        res = cursor.execute("SELECT name FROM alchemy_ingredients WHERE item_id = ?", (item_id,)).fetchone()
        if res: return res[0]
    return str(item_id).replace("_", " ").title()

def get_item_price(item_id: str) -> int:
    with get_connection() as conn:
        cursor = conn.cursor()
        res = cursor.execute("SELECT base_price FROM items WHERE item_id = ?", (item_id,)).fetchone()
        if res: return res[0]
        res = cursor.execute("SELECT base_price FROM alchemy_ingredients WHERE item_id = ?", (item_id,)).fetchone()
        if res and res[0] is not None: return res[0]
    return 10 

def apply_flee_penalty(user_id: int, dungeon_data: dict):
    user = get_user(user_id)
    penalty_pct = float(get_setting("flee_loss_percent", "0.3"))
    lost_gold = int(dungeon_data.get("gathered_gold", 0) * penalty_pct)
    user['gold'] = max(0, user['gold'] - lost_gold)
    inv = user['inventory']
    materials = inv.get("materials", {})
    gathered_mats = dungeon_data.get("gathered_materials", {})
    lost_mats_names = []
    for m_id, count in gathered_mats.items():
        loss = int(count * penalty_pct)
        if loss > 0:
            materials[m_id] = max(0, materials.get(m_id, 0) - loss)
            if materials[m_id] == 0: del materials[m_id]
            lost_mats_names.append(f"{get_item_name(m_id)} (x{loss})")
    inv["materials"] = materials
    update_user(user_id, gold=user['gold'], inventory=inv)
    return lost_gold, lost_mats_names

def apply_death_penalty(user_id: int, dungeon_data: dict):
    user = get_user(user_id)
    inv = user['inventory']
    lost_gold = dungeon_data.get("gathered_gold", 0)
    user['gold'] = max(0, user['gold'] - lost_gold)
    for m_id, count in dungeon_data.get("gathered_materials", {}).items():
        inv.setdefault("materials", {})[m_id] = max(0, inv.get("materials", {}).get(m_id, 0) - count)
        if inv["materials"].get(m_id) == 0: del inv["materials"][m_id]
    for e_id in dungeon_data.get("gathered_equipment", []):
        if e_id in inv.get("backpack", []): inv["backpack"].remove(e_id)
        elif e_id in inv.get("artifacts", []): inv["artifacts"].remove(e_id)
    update_user(user_id, gold=user['gold'], hp=max(1, int(user['max_hp'] * 0.5)), inventory=inv)
