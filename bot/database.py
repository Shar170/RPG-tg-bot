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
        
        # Безопасное добавление колонок для защиты от чизинга и PvP
        try: cursor.execute("ALTER TABLE users ADD COLUMN last_msg_id INTEGER DEFAULT 0")
        except sqlite3.OperationalError: pass
        try: cursor.execute("ALTER TABLE pvp_matches ADD COLUMN match_state TEXT DEFAULT '{}'")
        except sqlite3.OperationalError: pass
        try: cursor.execute("ALTER TABLE pvp_matches ADD COLUMN last_action_time REAL DEFAULT 0")
        except sqlite3.OperationalError: pass
            
        cursor.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, username TEXT, state TEXT, hp INTEGER, max_hp INTEGER,
            gold INTEGER, inventory TEXT, home_data TEXT, combat_data TEXT, known_traits TEXT, dungeon_data TEXT,
            level INTEGER DEFAULT 1, xp INTEGER DEFAULT 0, clan_id INTEGER DEFAULT 0, gems INTEGER DEFAULT 0, 
            quests_data TEXT DEFAULT '{}', clan_role TEXT DEFAULT 'thrall', energy INTEGER DEFAULT 5, 
            last_energy_time INTEGER DEFAULT 0, last_msg_id INTEGER DEFAULT 0)''')
            
        cursor.execute('''CREATE TABLE IF NOT EXISTS daily_dungeons (
            day_index INTEGER PRIMARY KEY, name TEXT, desc TEXT, mobs TEXT, loot_id TEXT, loot_name TEXT, boss_id TEXT, mob_modifier REAL)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS bestiary (
            mob_id TEXT PRIMARY KEY, name TEXT, hp_min INTEGER, hp_max INTEGER, dmg_min INTEGER, dmg_max INTEGER, 
            row_pref TEXT, skills TEXT, gold_min INTEGER DEFAULT 5, gold_max INTEGER DEFAULT 15, xp_reward INTEGER DEFAULT 10)''')
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
            weekly_raids INTEGER DEFAULT 0, join_requests TEXT DEFAULT '[]', clan_vault TEXT DEFAULT '{"gold": 0, "gems": 0, "items": {}}')''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS war_regions (
            region_id INTEGER PRIMARY KEY, name TEXT, desc TEXT, target_clears INTEGER DEFAULT 100000, 
            current_clears INTEGER DEFAULT 0, is_liberated INTEGER DEFAULT 0, boss_id TEXT, mobs TEXT)''')
            
        # Таблицы Арены
        cursor.execute('''CREATE TABLE IF NOT EXISTS arena_queue (
            user_id INTEGER PRIMARY KEY, level INTEGER, clan_id INTEGER, joined_at REAL)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS pvp_matches (
            match_id INTEGER PRIMARY KEY AUTOINCREMENT, p1_id INTEGER, p2_id INTEGER, 
            p1_hp INTEGER, p2_hp INTEGER, p1_max INTEGER, p2_max INTEGER, 
            p1_ap INTEGER, p2_ap INTEGER, turn INTEGER, log TEXT, match_state TEXT DEFAULT '{}', last_action_time REAL DEFAULT 0)''')
        conn.commit()

def seed_all():
    with get_connection() as conn:
        cursor = conn.cursor()

        settings = [
            ("flee_loss_percent", "0.3"),
            ("base_unarmed_dmg", "5"),
            ("max_energy", "5"),
            ("energy_regen_seconds", "7200"),
            ("energy_cost_solo", "0"),
            ("energy_cost_event", "1"),
            ("energy_cost_war", "0"),
            ("energy_cost_minigame", "1"),
            ("armor_formula_k", "60"),
            ("max_damage_reduction", "0.75"),
            ("clan_create_min_level", "50"),
            ("clan_create_cost_gems", "100"),
            ("clan_create_cost_gold", "0")
        ]
        cursor.executemany("INSERT OR REPLACE INTO game_settings VALUES (?, ?)", settings)

        war_regions_seed = [
            (1, "🔥 Долина Пепла", "Выжженная земля под властью огненных демонов.", 100000, 0, 0, "fire_lord", json.dumps(["magma_slime", "cultist_fanatic"])),
            (2, "🌲 Шепчущий Лес", "Оскверненная древняя чаща, полная яда и гнили.", 100000, 0, 0, "decay_treant", json.dumps(["poison_slime", "decay_treant"])),
            (3, "❄️ Ледяные Пики", "Морозные перевалы, скованные ледяными воинами.", 100000, 0, 0, "arena_berserk", json.dumps(["skeleton_crossbow", "living_idol"])),
            (4, "🍄 Забытые Болота", "Гиблое место гнездования гигантской паучихи.", 100000, 0, 0, "spider_queen", json.dumps(["poison_slime", "goblin_thief"])),
            (5, "🌑 Пустоши Бездны", "Разлом мира, откуда вырываются порождения Тьмы.", 100000, 0, 0, "abyss_priest", json.dumps(["cultist_fanatic", "magic_anomaly"])),
            (6, "⚡ Цитадель Бурь", "Высокогорный бастион с грозовыми големами.", 100000, 0, 0, "golem_blacksmith", json.dumps(["temple_guard", "magic_anomaly"])),
            (7, "👑 Бастион Королей", "Сердце Камарии, захваченное Костяным Драконом.", 100000, 0, 0, "bone_dragon", json.dumps(["fallen_champion", "skeleton_crossbow"]))
        ]
        cursor.executemany("INSERT OR IGNORE INTO war_regions VALUES (?, ?, ?, ?, ?, ?, ?, ?)", war_regions_seed)

        mobs = [
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
        cursor.executemany("INSERT OR REPLACE INTO bestiary VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", mobs)

        daily_dungeons = [
            (0, "💀 Склеп Нежити", "Склеп, наполненный древней тьмой.", json.dumps(["skeleton_crossbow", "living_dead"]), "bone_marrow", "Костный мозг", "bone_dragon", 1.1),
            (1, "🌋 Пылающая Кузня", "Реки лавы и раскаленные наковальни.", json.dumps(["magma_slime", "golem_blacksmith"]), "fire_root", "Магматическое ядро", "fire_lord", 1.2),
            (2, "🍄 Топи Забвения", "Ядовитые испарения и топкая грязь.", json.dumps(["poison_slime", "decay_treant"]), "poison_gland", "Ядовитая железа", "spider_queen", 1.1),
            (3, "⏳ Временные Руины", "Место, где искривляются секунды.", json.dumps(["magic_anomaly", "time_mimic"]), "time_tear", "Слеза времени", "time_keeper", 1.0),
            (4, "🩸 Темные Катакомбы", "Шепот сектантов и кровавые алтари.", json.dumps(["cultist_fanatic", "living_dead"]), "demon_blood", "Кровь демона", "abyss_priest", 1.25),
            (5, "🏜 Золотой Мираж", "Пески скрывают иллюзорные богатства.", json.dumps(["goblin_thief", "golden_mimic"]), "gold_petal", "Золотой лепесток", "greed_spirit", 1.15),
            (6, "⚔️ Кровавый Колизей", "Арена для сильнейших воинов.", json.dumps(["fallen_champion", "arena_berserk"]), "epic_token", "Эпический жетон", "arena_champ", 1.35)
        ]
        cursor.executemany("INSERT OR REPLACE INTO daily_dungeons VALUES (?, ?, ?, ?, ?, ?, ?, ?)", daily_dungeons)
        cursor.executemany("INSERT OR REPLACE INTO alchemy_ingredients VALUES (?, ?, ?, ?)", INGREDIENTS)

        items = [
            ("ragout", "Сытное рагу", "consumable", 20, json.dumps({"heal_pct": 0.35})),
            ("health_potion", "Зелье: Хил", "consumable", 30, json.dumps({"heal_pct": 0.25})),
            ("repair_kit", "Рем-набор", "consumable", 50, json.dumps({"repair": 100})),
            ("khmer_amulet", "Амулет Жизни", "artifact", 1500, json.dumps({"max_hp_bonus": 50})),
            ("smoke_bomb", "Дымовая бомба", "artifact", 120, json.dumps({"escape": True})),
            ("iron_ingot", "Железный слиток", "material", 15, "{}"),
            ("epic_token", "Эпический жетон", "material", 200, "{}"),
            ("wood_sword", "Деревянный меч", "weapon", 25, json.dumps({"dmg": 12, "range": "melee", "req_lvl": 1})),
            ("iron_sword", "Стальной меч", "weapon", 250, json.dumps({"dmg": 26, "range": "melee", "req_lvl": 5})),
            ("steel_greatsword", "Стальной двуручник", "weapon", 1800, json.dumps({"dmg": 52, "range": "melee", "req_lvl": 12})),
            ("mithril_blade", "Мифриловый Клинок", "weapon", 8500, json.dumps({"dmg": 85, "range": "melee", "req_lvl": 22})),
            ("demon_scythe", "Коса Демона", "weapon", 25000, json.dumps({"dmg": 135, "range": "melee", "req_lvl": 35})),
            ("god_slayer", "Убийца Богов", "weapon", 65000, json.dumps({"dmg": 210, "range": "melee", "req_lvl": 50})),
            ("short_bow", "Охотничий лук", "weapon", 80, json.dumps({"dmg": 16, "range": "ranged", "req_lvl": 2})),
            ("longbow", "Длинный лук", "weapon", 950, json.dumps({"dmg": 38, "range": "ranged", "req_lvl": 8})),
            ("heavy_crossbow", "Тяжелый арбалет", "weapon", 3200, json.dumps({"dmg": 68, "range": "ranged", "req_lvl": 16})),
            ("elven_bow", "Эльфийский лук", "weapon", 12000, json.dumps({"dmg": 105, "range": "ranged", "req_lvl": 28})),
            ("dragon_breath_staff", "Посох Дыхания Дракона", "weapon", 38000, json.dumps({"dmg": 160, "range": "ranged", "req_lvl": 42})),
            ("leather_armor", "Кожаная броня", "armor", 25, json.dumps({"def": 8, "req_lvl": 1})),
            ("chainmail", "Кольчуга", "armor", 350, json.dumps({"def": 22, "req_lvl": 5})),
            ("steel_plate", "Стальные Латы", "armor", 3000, json.dumps({"def": 45, "req_lvl": 14})),
            ("mithril_plate", "Мифриловый Доспех", "armor", 14000, json.dumps({"def": 75, "req_lvl": 25})),
            ("dragonbone_armor", "Драконья Чешуя", "armor", 35000, json.dumps({"def": 115, "req_lvl": 38})),
            ("titan_fortress", "Титановая Крепость", "armor", 75000, json.dumps({"def": 170, "req_lvl": 50}))
        ]
        cursor.executemany("INSERT OR REPLACE INTO items VALUES (?, ?, ?, ?, ?)", items)

        recipes = [
            ("rec_iron_sword", "iron_sword", json.dumps({"iron_ingot": 6}), 120),
            ("rec_chainmail", "chainmail", json.dumps({"iron_ingot": 12}), 150),
            ("rec_steel_plate", "steel_plate", json.dumps({"iron_ingot": 18}), 1800),
            ("rec_steel_greatsword", "steel_greatsword", json.dumps({"iron_ingot": 16}), 1000),
            ("rec_repair_kit", "repair_kit", json.dumps({"iron_ingot": 1}), 15),
            ("rec_smoke_bomb", "smoke_bomb", json.dumps({"iron_ingot": 1, "cave_mushroom": 2}), 50)
        ]
        cursor.executemany("INSERT OR REPLACE INTO recipes VALUES (?, ?, ?, ?)", recipes)
        conn.commit()

def check_and_distribute_weekly_clan_rewards():
    today = datetime.date.today()
    current_year, current_week, _ = today.isocalendar()
    current_week_key = f"{current_year}_W{current_week}"
    
    last_reward_week = get_setting("last_clan_reward_week", "")
    if last_reward_week == current_week_key:
        return
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT clan_id, name, weekly_raids FROM clans ORDER BY weekly_raids DESC LIMIT 3")
        top_clans = cursor.fetchall()
        rewards = [10, 5, 1]
        for idx, clan in enumerate(top_clans):
            if clan[2] > 0:
                clan_id = clan[0]
                gems_reward = rewards[idx]
                cursor.execute("SELECT clan_vault FROM clans WHERE clan_id = ?", (clan_id,))
                vault_row = cursor.fetchone()
                vault = json.loads(vault_row[0]) if vault_row and vault_row[0] else {"gold": 0, "items": {}}
                vault["gems"] = vault.get("gems", 0) + gems_reward
                cursor.execute("UPDATE clans SET clan_vault = ? WHERE clan_id = ?", (json.dumps(vault, ensure_ascii=False), clan_id))
        
        cursor.execute("UPDATE clans SET weekly_raids = 0")
        cursor.execute("INSERT OR REPLACE INTO game_settings (key, value) VALUES ('last_clan_reward_week', ?)", (current_week_key,))
        conn.commit()

def get_player_max_energy(player_level: int = 1) -> int:
    base_max = int(get_setting("max_energy", "5"))
    lvl_bonus = max(0, player_level // 20)
    return base_max + lvl_bonus

def get_energy_settings(player_level: int = 1) -> dict:
    return {
        "max_energy": get_player_max_energy(player_level),
        "regen_seconds": int(get_setting("energy_regen_seconds", "7200")),
        "cost_solo": int(get_setting("energy_cost_solo", "0")),
        "cost_event": int(get_setting("energy_cost_event", "1")),
        "cost_war": int(get_setting("energy_cost_war", "0")),
        "cost_minigame": int(get_setting("energy_cost_minigame", "1"))
    }

def get_clan_creation_requirements() -> dict:
    return {
        "min_level": int(get_setting("clan_create_min_level", "50")),
        "cost_gems": int(get_setting("clan_create_cost_gems", "100")),
        "cost_gold": int(get_setting("clan_create_cost_gold", "0"))
    }

def calculate_damage_received(raw_dmg: int, def_val: int) -> int:
    k = float(get_setting("armor_formula_k", "60"))
    max_dr = float(get_setting("max_damage_reduction", "0.75"))
    if def_val <= 0: return max(1, raw_dmg)
    reduction = min(max_dr, def_val / (def_val + k))
    return max(1, int(raw_dmg * (1.0 - reduction)))

def get_scaled_mob(mob_id: str, player_lvl: int = 1) -> dict:
    mob = get_mob_by_name(mob_id).copy()
    if player_lvl > 3:
        scale = 1.0 + (player_lvl - 3) * 0.08
        mob['hp_min'] = int(mob['hp_min'] * scale)
        mob['hp_max'] = int(mob['hp_max'] * scale)
        mob['dmg_min'] = int(mob['dmg_min'] * scale)
        mob['dmg_max'] = int(mob['dmg_max'] * scale)
        mob['gold_min'] = int(mob.get('gold_min', 5) * scale)
        mob['gold_max'] = int(mob.get('gold_max', 15) * scale)
        mob['xp_reward'] = int(mob.get('xp_reward', 10) * scale)
    return mob

def track_stat(user_id: int, stat_name: str, amount: int = 1):
    user = get_user(user_id)
    if not user: return
    home = user.get('home_data', {})
    stats = home.setdefault('stats', {})
    stats[stat_name] = stats.get(stat_name, 0) + amount
    home['stats'] = stats
    update_user(user_id, home_data=home)

def get_unlocked_titles(home_data: dict) -> list[str]:
    stats = home_data.get('stats', {})
    titles = ["Новичок"]
    m_k = stats.get('mobs_killed', 0)
    b_k = stats.get('bosses_killed', 0)

    if m_k >= 10: titles.append("Истребитель Слизней")
    if m_k >= 200: titles.append("Мясник Камарии")
    if b_k >= 5: titles.append("Охотник на Боссов")
    if stats.get('pvp_wins', 0) >= 10: titles.append("Гладиатор")
    if stats.get('war_clears', 0) >= 20: titles.append("Герой Камарии")

    return sorted(list(set(titles)))

def get_all_war_regions():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT region_id, name, desc, target_clears, current_clears, is_liberated, boss_id, mobs FROM war_regions ORDER BY region_id ASC")
        rows = cursor.fetchall()
        return [{
            "id": r[0], "name": r[1], "desc": r[2], "target": r[3], "current": r[4],
            "is_liberated": bool(r[5]), "boss_id": r[6], "mobs": json.loads(r[7]),
            "pct": round(min(100.0, (r[4] / r[3]) * 100), 2)
        } for r in rows]

def progress_war_region(region_id: int, user_id: int, home_data: dict = None) -> tuple[dict, int]:
    user = get_user(user_id)
    if home_data is None: home_data = user.get('home_data', {})
    
    medals = home_data.setdefault('medals', [])
    stats = home_data.setdefault('stats', {})
    stats['war_clears'] = stats.get('war_clears', 0) + 1
    
    gems_gained = 0
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name, target_clears, current_clears, is_liberated FROM war_regions WHERE region_id = ?", (region_id,))
        row = cursor.fetchone()
        if row:
            r_name, target, current, is_lib = row
            p_medal = f"🎖️ Защитник: {r_name}"
            if p_medal not in medals: medals.append(p_medal)

            new_current = current + 1
            new_lib = 1 if new_current >= target else is_lib

            if new_lib == 1 and is_lib == 0:
                lib_medal = f"🏆 Освободитель: {r_name}"
                if lib_medal not in medals:
                    medals.append(lib_medal)
                    gems_gained += 25

            cursor.execute("UPDATE war_regions SET current_clears = ?, is_liberated = ? WHERE region_id = ?", (new_current, new_lib, region_id))
            conn.commit()

    home_data['medals'] = medals
    home_data['stats'] = stats
    return home_data, gems_gained

def get_user(user_id: int):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()
        if user:
            columns = [desc[0] for desc in cursor.description]
            u_dict = dict(zip(columns, user))
            for json_field in ['inventory', 'home_data', 'combat_data', 'known_traits', 'dungeon_data', 'quests_data']:
                if u_dict.get(json_field): 
                    try: u_dict[json_field] = json.loads(u_dict[json_field])
                    except: u_dict[json_field] = {}
                else: 
                    u_dict[json_field] = {}
                
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
    if amount <= 0: return True
    user = get_user(user_id)
    if user['energy'] >= amount:
        update_user(user_id, energy=user['energy'] - amount)
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
        if row: return {"clan_id": row[0], "name": row[1]}
    return None

def update_clan(clan_id: int, **kwargs):
    with get_connection() as conn:
        cursor = conn.cursor()
        for key, value in kwargs.items():
            if key in ['join_requests']: value = json.dumps(value, ensure_ascii=False)
            cursor.execute(f"UPDATE clans SET {key} = ? WHERE clan_id = ?", (value, clan_id))
        conn.commit()

def get_clan_members(clan_id: int):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, username, level, clan_role, state FROM users WHERE clan_id = ?", (clan_id,))
        return [{"user_id": r[0], "username": r[1], "level": r[2], "clan_role": r[3], "state": r[4]} for r in cursor.fetchall()]

def get_top_clans(limit=3):
    check_and_distribute_weekly_clan_rewards()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name, weekly_raids FROM clans ORDER BY weekly_raids DESC LIMIT ?", (limit,))
        return [{"name": row[0], "weekly_raids": row[1]} for row in cursor.fetchall()]

def get_all_clans_ranked():
    check_and_distribute_weekly_clan_rewards()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT clan_id, name, level, weekly_raids, join_requests FROM clans ORDER BY weekly_raids DESC, clan_id ASC")
        rows = cursor.fetchall()
        result = []
        for rank, row in enumerate(rows, start=1):
            clan_id, name, level, _, join_reqs_raw = row
            max_members = 5 + level * 5
            cursor.execute("SELECT COUNT(*), AVG(level) FROM users WHERE clan_id = ?", (clan_id,))
            count, avg_lvl = cursor.fetchone()
            result.append({
                "clan_id": clan_id, "rank": rank, "name": name, "level": level,
                "avg_level": round(avg_lvl or 1.0, 1), "members_count": count or 0,
                "max_members": max_members, "free_slots": max(0, max_members - (count or 0)),
                "join_requests": json.loads(join_reqs_raw) if join_reqs_raw else []
            })
        return result

def check_and_generate_quests(user_id):
    user = get_user(user_id)
    quests_data = user.get('quests_data', {})
    today = datetime.datetime.today().strftime('%Y-%m-%d')
    if quests_data.get("date") != today:
        categories = [
            [{"type": "kill_mobs", "desc": "Убить 5 монстров", "target": 5}],
            [{"type": "raid_success", "desc": "Зачистить 1 подземелье", "target": 1}]
        ]
        selected = [random.choice(cat) for cat in categories]
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
        row = conn.cursor().execute("SELECT * FROM bestiary WHERE mob_id = ? OR name = ?", (name, name)).fetchone()
        if row: return {"mob_id": row[0], "name": row[1], "hp_min": row[2], "hp_max": row[3], "dmg_min": row[4], "dmg_max": row[5], "row_pref": row[6], "skills": json.loads(row[7] if row[7] else "{}"), "gold_min": row[8], "gold_max": row[9], "xp_reward": row[10]}
    return {"mob_id": "temple_guard", "name": "Храмовый Страж", "hp_min": 55, "hp_max": 75, "dmg_min": 12, "dmg_max": 18, "row_pref": "front", "skills": {}, "gold_min": 6, "gold_max": 14, "xp_reward": 12}

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

# --- НОВЫЕ ХЕЛПЕРЫ АРЕНЫ ---
def get_pvp_match(match_id: int):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM pvp_matches WHERE match_id = ?", (match_id,))
        row = cursor.fetchone()
        if row:
            cols = [desc[0] for desc in cursor.description]
            return dict(zip(cols, row))
    return None

def update_pvp_match(match_id: int, **kwargs):
    with get_connection() as conn:
        cursor = conn.cursor()
        for key, value in kwargs.items():
            cursor.execute(f"UPDATE pvp_matches SET {key} = ? WHERE match_id = ?", (value, match_id))
        conn.commit()
        
def remove_from_queue(user_id: int):
    with get_connection() as conn:
        conn.cursor().execute("DELETE FROM arena_queue WHERE user_id = ?", (user_id,))
        conn.commit()

