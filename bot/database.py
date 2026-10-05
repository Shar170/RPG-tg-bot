import sqlite3
import json
import datetime
import random
import time
from config import DB_PATH

# Импорты из модуля data/
from data.ingredients import INGREDIENTS
from data.items import ITEMS
from data.loot import LOOT_TABLES
from data.cards import CARD_SETS, CARDS, LOOT_BOXES
from data.skins import HOME_SKINS
from data.locations import SOLO_DUNGEONS, WAR_REGIONS, DAILY_DUNGEONS
from data.mobs import BESTIARY
from data.recipes import RECIPES

def get_connection():
    return sqlite3.connect(DB_PATH, timeout=10.0)

def init_db():
    with get_connection() as conn:
        cursor = conn.cursor()
        
        try: cursor.execute("ALTER TABLE users ADD COLUMN last_msg_id INTEGER DEFAULT 0")
        except sqlite3.OperationalError: pass
        try: cursor.execute("ALTER TABLE users ADD COLUMN is_bot INTEGER DEFAULT 0")
        except sqlite3.OperationalError: pass
        try: cursor.execute("ALTER TABLE pvp_matches ADD COLUMN match_state TEXT DEFAULT '{}'")
        except sqlite3.OperationalError: pass
        try: cursor.execute("ALTER TABLE pvp_matches ADD COLUMN last_action_time REAL DEFAULT 0")
        except sqlite3.OperationalError: pass
        try: cursor.execute("ALTER TABLE clans ADD COLUMN total_raids INTEGER DEFAULT 0")
        except sqlite3.OperationalError: pass
        
        try: cursor.execute("ALTER TABLE clans ADD COLUMN banner TEXT DEFAULT ''")
        except sqlite3.OperationalError: pass
        try: cursor.execute("ALTER TABLE clans ADD COLUMN merchant_data TEXT DEFAULT '{}'")
        except sqlite3.OperationalError: pass
        try: cursor.execute("ALTER TABLE clans ADD COLUMN chat_history TEXT DEFAULT '[]'")
        except sqlite3.OperationalError: pass
        
        try: cursor.execute("ALTER TABLE users ADD COLUMN dust INTEGER DEFAULT 0")
        except sqlite3.OperationalError: pass
        try: cursor.execute("ALTER TABLE users ADD COLUMN pity_counter INTEGER DEFAULT 0")
        except sqlite3.OperationalError: pass
        try: cursor.execute("ALTER TABLE users ADD COLUMN last_hp_time INTEGER DEFAULT 0")
        except sqlite3.OperationalError: pass
        
        try: cursor.execute("ALTER TABLE users ADD COLUMN notified_hp INTEGER DEFAULT 0")
        except sqlite3.OperationalError: pass
        try: cursor.execute("ALTER TABLE users ADD COLUMN notified_energy INTEGER DEFAULT 0")
        except sqlite3.OperationalError: pass
        
        try: cursor.execute("ALTER TABLE users ADD COLUMN last_active_time REAL DEFAULT 0")
        except sqlite3.OperationalError: pass
        try: cursor.execute("ALTER TABLE users ADD COLUMN reengagement_stage INTEGER DEFAULT 0")
        except sqlite3.OperationalError: pass
        
        try: cursor.execute("ALTER TABLE users ADD COLUMN story_progress TEXT DEFAULT '{\"story_id\": \"\", \"chapter_id\": \"\", \"current_node_id\": \"\", \"flags\": {}}'")
        except sqlite3.OperationalError: pass
            
        cursor.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, username TEXT, state TEXT, hp INTEGER, max_hp INTEGER,
            gold INTEGER, inventory TEXT, home_data TEXT, combat_data TEXT, known_traits TEXT, dungeon_data TEXT,
            level INTEGER DEFAULT 1, xp INTEGER DEFAULT 0, clan_id INTEGER DEFAULT 0, gems INTEGER DEFAULT 0, 
            quests_data TEXT DEFAULT '{}', clan_role TEXT DEFAULT 'thrall', energy INTEGER DEFAULT 5, 
            last_energy_time INTEGER DEFAULT 0, last_msg_id INTEGER DEFAULT 0, is_bot INTEGER DEFAULT 0, 
            dust INTEGER DEFAULT 0, pity_counter INTEGER DEFAULT 0, last_hp_time INTEGER DEFAULT 0,
            notified_hp INTEGER DEFAULT 0, notified_energy INTEGER DEFAULT 0,
            last_active_time REAL DEFAULT 0, reengagement_stage INTEGER DEFAULT 0)''')
            
        cursor.execute('''CREATE TABLE IF NOT EXISTS global_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT, text TEXT, timestamp REAL)''')
            
        cursor.execute('''CREATE TABLE IF NOT EXISTS daily_dungeons (
            day_index INTEGER PRIMARY KEY, name TEXT, desc TEXT, mobs TEXT, loot_id TEXT, loot_name TEXT, boss_id TEXT, mob_modifier REAL,
            min_rooms INTEGER DEFAULT 3, max_rooms INTEGER DEFAULT 4, room_weights TEXT DEFAULT '{"combat": 50, "puzzle": 20, "treasure": 15, "empty": 15}')''')
        
        cursor.execute('''CREATE TABLE IF NOT EXISTS war_regions (
            region_id INTEGER PRIMARY KEY, name TEXT, desc TEXT, target_clears INTEGER DEFAULT 100000, 
            current_clears INTEGER DEFAULT 0, is_liberated INTEGER DEFAULT 0, boss_id TEXT, mobs TEXT,
            min_rooms INTEGER DEFAULT 4, max_rooms INTEGER DEFAULT 6, room_weights TEXT DEFAULT '{"combat": 60, "puzzle": 15, "treasure": 15, "empty": 10}')''')

        cursor.execute('''CREATE TABLE IF NOT EXISTS solo_dungeons (
            id TEXT PRIMARY KEY, name TEXT, desc TEXT, mobs TEXT, boss_id TEXT, 
            min_rooms INTEGER DEFAULT 3, max_rooms INTEGER DEFAULT 5, 
            room_weights TEXT DEFAULT '{"combat": 40, "puzzle": 30, "treasure": 20, "empty": 10}')''')

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
            weekly_raids INTEGER DEFAULT 0, total_raids INTEGER DEFAULT 0, join_requests TEXT DEFAULT '[]', clan_vault TEXT DEFAULT '{"gold": 0, "gems": 0, "items": {}}',
            banner TEXT DEFAULT '', merchant_data TEXT DEFAULT '{}', chat_history TEXT DEFAULT '[]')''')
            
        cursor.execute('''CREATE TABLE IF NOT EXISTS arena_queue (
            user_id INTEGER PRIMARY KEY, level INTEGER, clan_id INTEGER, joined_at REAL)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS pvp_matches (
            match_id INTEGER PRIMARY KEY AUTOINCREMENT, p1_id INTEGER, p2_id INTEGER, 
            p1_hp INTEGER, p2_hp INTEGER, p1_max INTEGER, p2_max INTEGER, 
            p1_ap INTEGER, p2_ap INTEGER, turn INTEGER, log TEXT, match_state TEXT DEFAULT '{}', last_action_time REAL DEFAULT 0)''')
            
        cursor.execute('''CREATE TABLE IF NOT EXISTS home_skins (
            skin_id TEXT PRIMARY KEY, name TEXT, type TEXT, price INTEGER DEFAULT 0, requirements TEXT DEFAULT '{}', desc TEXT DEFAULT '')''')
        
        cursor.execute('''CREATE TABLE IF NOT EXISTS card_sets (
            set_id TEXT PRIMARY KEY, name TEXT, desc TEXT, rarity TEXT, reward_box_id TEXT, theme TEXT)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS cards (
            card_id TEXT PRIMARY KEY, name TEXT, emoji TEXT, set_id TEXT, rarity_internal TEXT)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS user_cards (
            user_id INTEGER, card_id TEXT, count INTEGER DEFAULT 0, first_at REAL, 
            PRIMARY KEY(user_id, card_id))''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS loot_boxes (
            box_id TEXT PRIMARY KEY, name TEXT, type TEXT, rarity TEXT, contents TEXT, min_level INTEGER, max_level INTEGER)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS user_boxes (
            user_id INTEGER, box_id TEXT, count INTEGER DEFAULT 0, 
            PRIMARY KEY(user_id, box_id))''')

        cursor.execute('''CREATE TABLE IF NOT EXISTS trading_post (
            lot_id INTEGER PRIMARY KEY AUTOINCREMENT, seller_id INTEGER, item_id TEXT, 
            item_type TEXT, price INTEGER, created_at REAL, expires_at REAL, is_bot INTEGER DEFAULT 0)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS tp_history (
            tx_id INTEGER PRIMARY KEY AUTOINCREMENT, seller_id INTEGER, buyer_id INTEGER,
            item_id TEXT, price INTEGER, tax_paid INTEGER, timestamp REAL)''')
            
        cursor.execute('''CREATE TABLE IF NOT EXISTS analytics_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            timestamp REAL, 
            user_id INTEGER, 
            event_category TEXT, 
            event_type TEXT, 
            value_change INTEGER, 
            metadata TEXT)''')
            
        # ТАБЛИЦЫ СЮЖЕТА
        cursor.execute('''CREATE TABLE IF NOT EXISTS stories (
            id TEXT PRIMARY KEY, title TEXT, desc TEXT, req_admin INTEGER DEFAULT 0, start_node_id TEXT DEFAULT 'node_start')''')
        
        try: cursor.execute("ALTER TABLE stories ADD COLUMN start_node_id TEXT DEFAULT 'node_start'")
        except sqlite3.OperationalError: pass
        
        cursor.execute('''CREATE TABLE IF NOT EXISTS story_chapters (
            id TEXT PRIMARY KEY, story_id TEXT, title TEXT)''')
        
        cursor.execute('''CREATE TABLE IF NOT EXISTS story_nodes (
            id TEXT PRIMARY KEY, chapter_id TEXT, node_type TEXT, text TEXT, extra_data TEXT DEFAULT '{}')''')
        
        cursor.execute('''CREATE TABLE IF NOT EXISTS story_choices (
            id INTEGER PRIMARY KEY AUTOINCREMENT, node_id TEXT, text TEXT, req_cond TEXT DEFAULT '{}', action_data TEXT DEFAULT '{}', next_node_id TEXT)''')
            
        conn.commit()

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ МИНИ-ИГР ---
def get_minigame_settings() -> dict:
    return {
        "fish_gold_min": int(get_setting("mg_fish_gold_min", "70")),
        "fish_gold_max": int(get_setting("mg_fish_gold_max", "120")),
        "fish_gem_chance": float(get_setting("mg_fish_gem_chance", "0.10")),
        "fish_gem_amount": int(get_setting("mg_fish_gem_amount", "1")),
        
        "mine_gold_min": int(get_setting("mg_mine_gold_min", "35")),
        "mine_gold_max": int(get_setting("mg_mine_gold_max", "65")),
        "mine_gem_amount": int(get_setting("mg_mine_gem_amount", "1")),
        
        "dice_bet": int(get_setting("mg_dice_bet", "50")),
        "dice_win_gold": int(get_setting("mg_dice_win_gold", "130")),
        
        "lock_gold_min": int(get_setting("mg_lock_gold_min", "150")),
        "lock_gold_max": int(get_setting("mg_lock_gold_max", "250")),
        "lock_gem_chance": float(get_setting("mg_lock_gem_chance", "0.15")),
        "lock_gem_amount": int(get_setting("mg_lock_gem_amount", "1")),
    }

def get_random_material_id() -> str:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT item_id FROM alchemy_ingredients")
        rows = cursor.fetchall()
        pool = [r[0] for r in rows] if rows else []
        pool.append("iron_ingot")
        if pool:
            return random.choice(pool)
    return "iron_ingot"

# --- ФУНКЦИИ ОНЛАЙНА ---
def mark_user_active(user_id: int):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET last_active_time = ?, reengagement_stage = 0 WHERE user_id = ?", (time.time(), user_id))
        conn.commit()

def get_online_users(minutes: int = 15) -> tuple[int, list]:
    threshold = time.time() - (minutes * 60)
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT username FROM users WHERE is_bot=0 AND last_active_time >= ?", (threshold,))
        rows = cursor.fetchall()
        names = [r[0] for r in rows]
        return len(names), names

def check_inactivity_notifications() -> list:
    notifications = []
    now = time.time()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, last_active_time, reengagement_stage FROM users WHERE is_bot=0")
        for u_id, last_time, stage in cursor.fetchall():
            if last_time == 0: continue 
            days_inactive = (now - last_time) / 86400.0
            new_stage = stage
            
            if days_inactive >= 31 and stage < 4:
                new_stage = 4
                notifications.append({"user_id": u_id, "days": 31})
            elif days_inactive >= 17 and stage < 3:
                new_stage = 3
                notifications.append({"user_id": u_id, "days": 17})
            elif days_inactive >= 5 and stage < 2:
                new_stage = 2
                notifications.append({"user_id": u_id, "days": 5})
            elif days_inactive >= 2 and stage < 1:
                new_stage = 1
                notifications.append({"user_id": u_id, "days": 2})
                
            if new_stage != stage:
                cursor.execute("UPDATE users SET reengagement_stage = ? WHERE user_id = ?", (new_stage, u_id))
        conn.commit()
    return notifications

def check_and_notify_regen() -> list:
    notifications = []
    now = int(time.time())
    with get_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("SELECT key, value FROM game_settings WHERE key IN ('max_energy', 'energy_regen_seconds')")
        s_dict = {row[0]: row[1] for row in cursor.fetchall()}
        base_max_e = int(s_dict.get("max_energy", "5"))
        regen_sec_e = int(s_dict.get("energy_regen_seconds", "7200"))
        
        cursor.execute("SELECT user_id, hp, max_hp, last_hp_time, energy, level, last_energy_time, notified_hp, notified_energy, state FROM users WHERE is_bot=0")
        users = cursor.fetchall()
        
        for u in users:
            u_id, hp, max_hp, last_hp_time, energy, lvl, last_e_time, notif_hp, notif_e, state = u
            needs_update = False
            max_e = base_max_e + max(0, lvl // 20)
            
            if hp < max_hp and notif_hp == 1:
                notif_hp = 0
                needs_update = True
            if energy < max_e and notif_e == 1:
                notif_e = 0
                needs_update = True
                
            if state == 'STATE_TOWN' and hp < max_hp and last_hp_time > 0:
                time_passed = now - last_hp_time
                regen_interval = 60
                regen_amount = max(1, int(max_hp * 0.05))
                if time_passed >= regen_interval:
                    cycles = time_passed // regen_interval
                    hp = min(max_hp, hp + (cycles * regen_amount))
                    last_hp_time = last_hp_time + (cycles * regen_interval)
                    needs_update = True
                    
            if hp >= max_hp and notif_hp == 0:
                notifications.append({"user_id": u_id, "type": "hp"})
                notif_hp = 1
                needs_update = True

            if energy < max_e and last_e_time > 0:
                time_passed = now - last_e_time
                if time_passed >= regen_sec_e:
                    cycles = time_passed // regen_sec_e
                    energy = min(max_e, energy + cycles)
                    last_e_time = last_e_time + (cycles * regen_sec_e)
                    needs_update = True
                    
            if energy >= max_e and notif_e == 0:
                notifications.append({"user_id": u_id, "type": "energy"})
                notif_e = 1
                needs_update = True
                
            if needs_update:
                cursor.execute(
                    "UPDATE users SET hp=?, last_hp_time=?, energy=?, last_energy_time=?, notified_hp=?, notified_energy=? WHERE user_id=?", 
                    (hp, last_hp_time, energy, last_e_time, notif_hp, notif_e, u_id)
                )
        conn.commit()
    return notifications

def add_global_event(text: str):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO global_events (text, timestamp) VALUES (?, ?)", (text, time.time()))
        cursor.execute("DELETE FROM global_events WHERE id NOT IN (SELECT id FROM global_events ORDER BY id DESC LIMIT 10)")
        conn.commit()

def get_recent_global_events(limit=5):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT text FROM global_events ORDER BY timestamp DESC LIMIT ?", (limit,))
        return [row[0] for row in cursor.fetchall()]

def seed_bots():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users WHERE is_bot=1")
        if cursor.fetchone()[0] > 0: return

        bot_clans = [("Орден Пепла", 3, 45), ("Тени Камарии", 4, 70), ("Стальные Волки", 2, 25)]
        clan_ids = []
        for c_name, c_lvl, c_raids in bot_clans:
            cursor.execute("INSERT OR IGNORE INTO clans (name, leader_id, level, treasury, weekly_raids, join_requests, clan_vault) VALUES (?, ?, ?, 5000, ?, '[]', '{}')", (c_name, 0, c_lvl, c_raids))
            cursor.execute("SELECT clan_id FROM clans WHERE name=?", (c_name,))
            clan_ids.append(cursor.fetchone()[0])

        bot_names = ["Kaelthas", "ShadowStrike", "Grommash", "Leroy", "Arthas", "Illidan", "Sylvanas", "Rexxar", "Guldan", "Jaina", "Uther", "Thrall", "Varian", "Garrosh", "Malfurion"]
        bot_base_id = 9000000
        for i, name in enumerate(bot_names):
            lvl = random.randint(10, 45)
            max_hp = 100 + (lvl * 15)
            clan_id = random.choice(clan_ids)
            inv = json.dumps({"potions": ["Зелье: Хил", "Зелье: Хил"], "backpack": ["iron_sword", "chainmail"], "materials": {"iron_ingot": 5}})
            stats = json.dumps({"stats": {"pvp_wins": random.randint(5, 50), "bosses_killed": random.randint(10, 100)}})
            
            cursor.execute("""
                INSERT OR IGNORE INTO users (user_id, username, state, hp, max_hp, level, gold, clan_id, inventory, home_data, is_bot)
                VALUES (?, ?, 'STATE_TOWN', ?, ?, ?, ?, ?, ?, ?, 1)
            """, (bot_base_id + i, name, max_hp, max_hp, lvl, random.randint(1000, 5000), clan_id, inv, stats))
            
            if i < len(clan_ids):
                cursor.execute("UPDATE clans SET leader_id = ? WHERE clan_id = ?", (bot_base_id + i, clan_ids[i]))
        conn.commit()

def simulate_bot_activity():
    last_sim = float(get_setting("last_bot_sim", "0"))
    now = time.time()
    
    if now - last_sim < 3600: return

    events_to_add = []
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT lot_id, seller_id, item_id, item_type, is_bot FROM trading_post WHERE expires_at < ?", (now,))
        for lot_id, s_id, i_id, idx_type, is_b in cursor.fetchall():
            if not is_b: give_item(s_id, i_id, idx_type, 1)
            cursor.execute("DELETE FROM trading_post WHERE lot_id=?", (lot_id,))
            
        cursor.execute("SELECT COUNT(*) FROM trading_post WHERE is_bot=0")
        player_lots = cursor.fetchone()[0]
        if player_lots < 50:
            cursor.execute("SELECT user_id FROM users WHERE is_bot=1 ORDER BY RANDOM() LIMIT 2")
            bot_sellers = cursor.fetchall()
            items_pool = [("iron_sword", "weapon", 250), ("chainmail", "armor", 350), ("epic_token", "material", 200)]
            for (bot_id,) in bot_sellers:
                i_id, i_type, bp = random.choice(items_pool)
                price = int(bp * random.uniform(0.9, 1.3))
                cursor.execute("INSERT INTO trading_post (seller_id, item_id, item_type, price, created_at, expires_at, is_bot) VALUES (?, ?, ?, ?, ?, ?, 1)", (bot_id, i_id, i_type, price, now, now + 86400))
                
            cursor.execute("SELECT lot_id, seller_id, item_id, price FROM trading_post WHERE is_bot=0 ORDER BY RANDOM() LIMIT 3")
            for lot_id, s_id, i_id, price in cursor.fetchall():
                bp = get_item_price(i_id)
                if price <= bp * 0.9 and random.random() < 0.5:
                    cursor.execute("DELETE FROM trading_post WHERE lot_id=?", (lot_id,))
                    u = get_user(s_id)
                    if u: update_user(s_id, gold=u['gold'] + price)

        cursor.execute("SELECT username, clan_id FROM users WHERE is_bot=1 ORDER BY RANDOM() LIMIT 3")
        bots = cursor.fetchall()
        
        for bot_name, clan_id in bots:
            action = random.choice(["war", "arena", "dungeon", "craft"])
            if action == "war":
                cursor.execute("SELECT region_id, name FROM war_regions WHERE is_liberated=0 ORDER BY RANDOM() LIMIT 1")
                reg = cursor.fetchone()
                if reg:
                    cursor.execute("UPDATE war_regions SET current_clears = current_clears + ? WHERE region_id=?", (random.randint(15, 40), reg[0]))
                    events_to_add.append(f"🌍 Игрок **{bot_name}** внес крупный вклад в освобождение региона [{reg[1]}].")
            elif action == "dungeon":
                if clan_id != 0:
                    cursor.execute("UPDATE clans SET weekly_raids = weekly_raids + ? WHERE clan_id=?", (random.randint(5, 12), clan_id))
                events_to_add.append(f"💀 Игрок **{bot_name}** зачистил опасное подземелье и добыл редкие реагенты.")
            elif action == "craft":
                events_to_add.append(f"🔨 Игрок **{bot_name}** создал Легендарное снаряжение в Мастерской.")
        
        cursor.execute("INSERT OR REPLACE INTO game_settings (key, value) VALUES ('last_bot_sim', ?)", (str(now),))
        conn.commit()

    for evt in events_to_add:
        add_global_event(evt)

def seed_all():
    with get_connection() as conn:
        cursor = conn.cursor()

        # Базовые настройки игры
        settings = [
            ("flee_loss_percent", "0.3"), ("base_unarmed_dmg", "5"),
            ("max_energy", "5"), ("energy_regen_seconds", "7200"),
            ("energy_cost_solo", "0"), ("energy_cost_event", "1"),
            ("energy_cost_war", "0"), ("energy_cost_minigame", "1"),
            ("armor_formula_k", "60"), ("max_damage_reduction", "0.75"),
            ("clan_create_min_level", "50"), ("clan_create_cost_gems", "100"),
            ("clan_create_cost_gold", "0"), ("dungeon_trap_chance", "0.2"),
            ("dungeon_mimic_chance", "0.15"),
            ("mg_fish_gold_min", "70"), ("mg_fish_gold_max", "120"),
            ("mg_fish_gem_chance", "0.10"), ("mg_fish_gem_amount", "1"),
            ("mg_mine_gold_min", "35"), ("mg_mine_gold_max", "65"),
            ("mg_mine_gem_amount", "1"), ("mg_dice_bet", "50"),
            ("mg_dice_win_gold", "130"), ("mg_lock_gold_min", "150"),
            ("mg_lock_gold_max", "250"), ("mg_lock_gem_chance", "0.15"),
            ("mg_lock_gem_amount", "2")
        ]
        cursor.executemany("INSERT OR REPLACE INTO game_settings VALUES (?, ?)", settings)
        
        # Импортированные таблицы (карточки, предметы, локации, мобы)
        cursor.executemany("INSERT OR REPLACE INTO card_sets VALUES (?, ?, ?, ?, ?, ?)", CARD_SETS)
        cursor.executemany("INSERT OR REPLACE INTO cards VALUES (?, ?, ?, ?, ?)", CARDS)
        cursor.executemany("INSERT OR REPLACE INTO loot_boxes VALUES (?, ?, ?, ?, ?, ?, ?)", LOOT_BOXES)
        cursor.executemany("INSERT OR REPLACE INTO home_skins VALUES (?, ?, ?, ?, ?, ?)", HOME_SKINS)
        cursor.executemany("INSERT OR IGNORE INTO solo_dungeons VALUES (?, ?, ?, ?, ?, ?, ?, ?)", SOLO_DUNGEONS)
        
        for w in WAR_REGIONS:
            try: cursor.execute("INSERT OR IGNORE INTO war_regions (region_id, name, desc, target_clears, current_clears, is_liberated, boss_id, mobs) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", w)
            except: pass
            
        cursor.executemany("INSERT OR REPLACE INTO bestiary VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", BESTIARY)
        
        for d in DAILY_DUNGEONS:
            try: cursor.execute("INSERT OR IGNORE INTO daily_dungeons (day_index, name, desc, mobs, loot_id, loot_name, boss_id, mob_modifier) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", d)
            except: pass
            
        cursor.executemany("INSERT OR REPLACE INTO alchemy_ingredients VALUES (?, ?, ?, ?)", INGREDIENTS)
        cursor.executemany("INSERT OR REPLACE INTO items VALUES (?, ?, ?, ?, ?)", ITEMS)
        cursor.executemany("INSERT OR REPLACE INTO recipes VALUES (?, ?, ?, ?)", RECIPES)
        
        # Обновление таблиц лута
        cursor.execute("DELETE FROM loot_tables")
        cursor.executemany("INSERT INTO loot_tables (location_id, item_id, chance, min_amount, max_amount) VALUES (?, ?, ?, ?, ?)", LOOT_TABLES)
        
        conn.commit()
        seed_bots()
        seed_test_story()

def give_item(user_id: int, item_id: str, item_type: str, amount: int = 1):
    user = get_user(user_id)
    if not user: return
    inv = user.get('inventory', {})
    with get_connection() as conn:
        cur = conn.cursor()
        if item_type == 'card':
            cur.execute("INSERT INTO user_cards (user_id, card_id, count, first_at) VALUES (?, ?, ?, ?) ON CONFLICT(user_id, card_id) DO UPDATE SET count=count+?", (user_id, item_id, amount, time.time(), amount))
        elif item_type == 'box':
            cur.execute("INSERT INTO user_boxes (user_id, box_id, count) VALUES (?, ?, ?) ON CONFLICT(user_id, box_id) DO UPDATE SET count=count+?", (user_id, item_id, amount, amount))
        elif item_type in ['weapon', 'armor']:
            for _ in range(amount): inv.setdefault('backpack', []).append(item_id)
            update_user(user_id, inventory=inv)
        elif item_type == 'material':
            inv.setdefault('materials', {})[item_id] = inv.get('materials', {}).get(item_id, 0) + amount
            update_user(user_id, inventory=inv)
        conn.commit()

def take_item(user_id: int, item_id: str, item_type: str, amount: int = 1) -> bool:
    user = get_user(user_id)
    if not user: return False
    inv = user.get('inventory', {})
    success = False
    with get_connection() as conn:
        cur = conn.cursor()
        if item_type == 'card':
            cur.execute("SELECT count FROM user_cards WHERE user_id=? AND card_id=?", (user_id, item_id))
            res = cur.fetchone()
            if res and res[0] >= amount:
                cur.execute("UPDATE user_cards SET count=count-? WHERE user_id=? AND card_id=?", (amount, user_id, item_id))
                success = True
        elif item_type == 'box':
            cur.execute("SELECT count FROM user_boxes WHERE user_id=? AND box_id=?", (user_id, item_id))
            res = cur.fetchone()
            if res and res[0] >= amount:
                cur.execute("UPDATE user_boxes SET count=count-? WHERE user_id=? AND box_id=?", (amount, user_id, item_id))
                success = True
        elif item_type in ['weapon', 'armor']:
            if item_id in inv.get('backpack', []):
                inv['backpack'].remove(item_id)
                update_user(user_id, inventory=inv)
                success = True
        elif item_type == 'material':
            if inv.get('materials', {}).get(item_id, 0) >= amount:
                inv['materials'][item_id] -= amount
                if inv['materials'][item_id] <= 0: del inv['materials'][item_id]
                update_user(user_id, inventory=inv)
                success = True
        conn.commit()
    return success

def get_all_home_skins() -> dict:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT skin_id, name, type, price, requirements, desc FROM home_skins")
        rows = cursor.fetchall()
        skins = {}
        for row in rows:
            reqs = json.loads(row[4]) if row[4] else {}
            skin_data = {"name": row[1], "type": row[2], "price": row[3], "desc": row[5]}
            skin_data.update(reqs) 
            skins[row[0]] = skin_data
        return skins

def get_all_solo_dungeons():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM solo_dungeons")
        rows = cursor.fetchall()
        res = []
        for r in rows:
            cols = [desc[0] for desc in cursor.description]
            d = dict(zip(cols, r))
            d["mobs"] = json.loads(d["mobs"]) if d["mobs"] else []
            d["room_weights"] = json.loads(d["room_weights"]) if d.get("room_weights") else None
            res.append(d)
        return res

def get_solo_dungeon(d_id: str):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM solo_dungeons WHERE id = ?", (d_id,))
        row = cursor.fetchone()
        if row:
            cols = [desc[0] for desc in cursor.description]
            d = dict(zip(cols, row))
            d["mobs"] = json.loads(d["mobs"]) if d["mobs"] else []
            d["room_weights"] = json.loads(d["room_weights"]) if d.get("room_weights") else None
            return d
    return None

def get_today_dungeon():
    day_index = datetime.datetime.today().weekday()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM daily_dungeons WHERE day_index = ?", (day_index,))
        row = cursor.fetchone()
        if row: 
            cols = [desc[0] for desc in cursor.description]
            d = dict(zip(cols, row))
            d["mobs"] = json.loads(d["mobs"]) if d["mobs"] else []
            d["room_weights"] = json.loads(d["room_weights"]) if d.get("room_weights") else None
            return d
    return None

def get_all_war_regions():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM war_regions ORDER BY region_id ASC")
        rows = cursor.fetchall()
        res = []
        for r in rows:
            cols = [desc[0] for desc in cursor.description]
            d = dict(zip(cols, r))
            d["mobs"] = json.loads(d["mobs"]) if d["mobs"] else []
            d["room_weights"] = json.loads(d["room_weights"]) if d.get("room_weights") else None
            d["pct"] = round(min(100.0, (d["current_clears"] / d["target_clears"]) * 100), 2)
            d["id"] = d["region_id"]
            d["target"] = d["target_clears"]
            d["current"] = d["current_clears"]
            res.append(d)
        return res

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
        if player_lvl >= 30: scale += (player_lvl - 30) * 0.05
        if player_lvl >= 50: scale += (player_lvl - 50) * 0.15

        mob['hp_min'] = int(mob['hp_min'] * scale)
        mob['hp_max'] = int(mob['hp_max'] * scale)
        mob['dmg_min'] = int(mob['dmg_min'] * scale)
        mob['dmg_max'] = int(mob['dmg_max'] * scale)
        mob['gold_min'] = int(mob.get('gold_min', 5) * scale)
        mob['gold_max'] = int(mob.get('gold_max', 15) * scale)
        mob['xp_reward'] = int(mob.get('xp_reward', 10) * scale)
        
        skill_bonus = player_lvl * 0.005 
        new_skills = {}
        for k, v in mob['skills'].items():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                new_skills[k] = min(0.80, v + skill_bonus)
            else:
                new_skills[k] = v
        mob['skills'] = new_skills

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
    if stats.get('pvp_wins', 0) >= 50: titles.append("Чемпион Арены")
    if stats.get('war_clears', 0) >= 20: titles.append("Герой Камарии")
    
    if stats.get('riddles_solved', 0) >= 10: titles.append("Мыслитель")
    if stats.get('riddles_failed', 0) >= 10: titles.append("Пустоголовый")
    if stats.get('kills_fire_lord', 0) >= 1: titles.append("Пожарный")
    if stats.get('kills_goblin_thief', 0) >= 10: titles.append("Гроза гоблинов")
    if stats.get('kills_living_idol', 0) >= 10: titles.append("Разрушитель идолов")
    if stats.get('kills_time_keeper', 0) >= 1: titles.append("Похоронитель хранителей")
    if stats.get('potions_crafted', 0) >= 20: titles.append("Мастер зелий")
    if stats.get('items_crafted', 0) >= 10: titles.append("Кузнец")
    if stats.get('minigames_won', 0) >= 5: titles.append("Счастливчик")

    return sorted(list(set(titles)))

def progress_war_region(region_id: int, user_id: int, home_data: dict = None) -> tuple[dict, int]:
    user = get_user(user_id)
    if home_data is None: home_data = user.get('home_data', {})
    
    medals = home_data.setdefault('medals', [])
    stats = home_data.setdefault('stats', {})
    stats['war_clears'] = stats.get('war_clears', 0) + 1
    
    reg_clears_key = f'war_clears_reg_{region_id}'
    stats[reg_clears_key] = stats.get(reg_clears_key, 0) + 1
    reg_clears = stats[reg_clears_key]
    
    gems_gained = 0
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name, target_clears, current_clears, is_liberated FROM war_regions WHERE region_id = ?", (region_id,))
        row = cursor.fetchone()
        if row:
            r_name, target, current, is_lib = row
            
            if reg_clears == 10:
                m_title = f"🥉 Защитник: {r_name}"
                if m_title not in medals: medals.append(m_title)
            elif reg_clears == 50:
                m_title = f"🥈 Ветеран: {r_name}"
                if m_title not in medals: medals.append(m_title)
            elif reg_clears == 100:
                m_title = f"🥇 Герой: {r_name}"
                if m_title not in medals: medals.append(m_title)

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
            for json_field in ['inventory', 'home_data', 'combat_data', 'known_traits', 'dungeon_data', 'quests_data', 'story_progress']:
                if u_dict.get(json_field): 
                    try: u_dict[json_field] = json.loads(u_dict[json_field])
                    except: u_dict[json_field] = {}
                else: 
                    u_dict[json_field] = {}
                    
            now = int(time.time())
            last_time = u_dict.get('last_energy_time', 0)
            current_energy = u_dict.get('energy', 5)
            lvl = u_dict.get('level', 1)
            
            cursor.execute("SELECT key, value FROM game_settings WHERE key IN ('max_energy', 'energy_regen_seconds')")
            s_dict = {row[0]: row[1] for row in cursor.fetchall()}
            
            base_max = int(s_dict.get("max_energy", "5"))
            regen_seconds = int(s_dict.get("energy_regen_seconds", "7200"))
            max_energy = base_max + max(0, lvl // 20)
            
            if current_energy < max_energy:
                if last_time == 0:
                    cursor.execute("UPDATE users SET last_energy_time = ? WHERE user_id = ?", (now, user_id))
                    conn.commit()
                    u_dict['last_energy_time'] = now
                else:
                    time_passed = now - last_time
                    if time_passed >= regen_seconds:
                        cycles = time_passed // regen_seconds
                        new_energy = min(max_energy, current_energy + cycles)
                        new_last_time = last_time + (cycles * regen_seconds)
                        
                        cursor.execute("UPDATE users SET energy = ?, last_energy_time = ? WHERE user_id = ?", (new_energy, new_last_time, user_id))
                        conn.commit()
                        u_dict['energy'] = new_energy
                        u_dict['last_energy_time'] = new_last_time
            
            last_hp_time = u_dict.get('last_hp_time', 0)
            current_hp = u_dict.get('hp', 100)
            max_player_hp = u_dict.get('max_hp', 100)
            state = u_dict.get('state', 'STATE_TOWN')
            
            if current_hp < max_player_hp and state == 'STATE_TOWN':
                if last_hp_time == 0:
                    cursor.execute("UPDATE users SET last_hp_time = ? WHERE user_id = ?", (now, user_id))
                    conn.commit()
                    u_dict['last_hp_time'] = now
                else:
                    time_passed = now - last_hp_time
                    regen_interval = 60 
                    regen_amount = max(1, int(max_player_hp * 0.05))
                    
                    if time_passed >= regen_interval:
                        cycles = time_passed // regen_interval
                        new_hp = min(max_player_hp, current_hp + (cycles * regen_amount))
                        new_last_hp_time = last_hp_time + (cycles * regen_interval)
                        
                        cursor.execute("UPDATE users SET hp = ?, last_hp_time = ? WHERE user_id = ?", (new_hp, new_last_hp_time, user_id))
                        conn.commit()
                        u_dict['hp'] = new_hp
                        u_dict['last_hp_time'] = new_last_hp_time
            elif current_hp == max_player_hp and last_hp_time != 0:
                cursor.execute("UPDATE users SET last_hp_time = 0 WHERE user_id = ?", (user_id,))
                conn.commit()
                u_dict['last_hp_time'] = 0

            return u_dict
    return None

def update_user(user_id: int, **kwargs):
    with get_connection() as conn:
        cursor = conn.cursor()
        for key, value in kwargs.items():
            if key in ['inventory', 'home_data', 'combat_data', 'known_traits', 'dungeon_data', 'quests_data', 'story_progress']: 
                value = json.dumps(value, ensure_ascii=False)
            cursor.execute(f"UPDATE users SET {key} = ? WHERE user_id = ?", (value, user_id))
        conn.commit()

def consume_energy(user_id: int, amount: int = 1) -> bool:
    if amount <= 0: return True
    user = get_user(user_id) 
    current_energy = user.get('energy', 5)
    
    if current_energy >= amount:
        max_e = get_player_max_energy(user.get('level', 1))
        new_energy = current_energy - amount
        
        if current_energy >= max_e and new_energy < max_e:
            update_user(user_id, energy=new_energy, last_energy_time=int(time.time()))
        else:
            update_user(user_id, energy=new_energy)
        return True
    return False

def get_clan(clan_id: int):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT clan_id, name, leader_id, treasury, level, weekly_raids, join_requests, clan_vault, total_raids, banner, merchant_data, chat_history FROM clans WHERE clan_id = ?", (clan_id,))
        row = cursor.fetchone()
        if row: 
            return {
                "clan_id": row[0], "name": row[1], "leader_id": row[2], 
                "treasury": row[3], "level": row[4], "weekly_raids": row[5], 
                "join_requests": json.loads(row[6]), "clan_vault": row[7],
                "total_raids": row[8],
                "banner": row[9] if len(row) > 9 and row[9] else "",
                "merchant_data": json.loads(row[10]) if len(row) > 10 and row[10] else {},
                "chat_history": json.loads(row[11]) if len(row) > 11 and row[11] else []
            }
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
            if key in ['join_requests', 'merchant_data', 'chat_history']: value = json.dumps(value, ensure_ascii=False)
            cursor.execute(f"UPDATE clans SET {key} = ? WHERE clan_id = ?", (value, clan_id))
        conn.commit()

def get_clan_merchant_deals(clan_id: int) -> dict:
    clan = get_clan(clan_id)
    if not clan: return {"buy": [], "sell": []}
    
    today = datetime.datetime.today().strftime('%Y-%m-%d')
    m_data = clan.get('merchant_data', {})
    
    if m_data.get('date') == today:
        return m_data
        
    lvl = clan['level']
    count = 2 if lvl >= 15 else 1 if lvl >= 5 else 0
    
    with get_connection() as conn:
        items = [r[0] for r in conn.cursor().execute("SELECT item_id FROM items").fetchall()]
        mats = [r[0] for r in conn.cursor().execute("SELECT item_id FROM alchemy_ingredients").fetchall()]
        pool = items + mats
        
        buy_pool = random.sample(pool, min(count, len(pool))) if count > 0 else []
        sell_pool = random.sample(pool, min(count, len(pool))) if count > 0 else []
        
    new_data = {"date": today, "buy": buy_pool, "sell": sell_pool}
    update_clan(clan_id, merchant_data=new_data)
    return new_data

def get_clan_members(clan_id: int):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, username, level, clan_role, state FROM users WHERE clan_id = ?", (clan_id,))
        return [{"user_id": r[0], "username": r[1], "level": r[2], "clan_role": r[3], "state": r[4]} for r in cursor.fetchall()]

def get_top_clans(limit=3):
    check_and_distribute_weekly_clan_rewards()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name, weekly_raids, banner FROM clans ORDER BY weekly_raids DESC LIMIT ?", (limit,))
        return [{"name": row[0], "weekly_raids": row[1], "banner": row[2] if len(row) > 2 else ""} for row in cursor.fetchall()]

def get_all_clans_ranked():
    check_and_distribute_weekly_clan_rewards()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT clan_id, name, level, weekly_raids, join_requests, banner FROM clans ORDER BY weekly_raids DESC, clan_id ASC")
        rows = cursor.fetchall()
        result = []
        for rank, row in enumerate(rows, start=1):
            clan_id, name, level, _, join_reqs_raw, banner = row
            max_members = 5 + level * 5
            cursor.execute("SELECT COUNT(*), AVG(level) FROM users WHERE clan_id = ?", (clan_id,))
            count, avg_lvl = cursor.fetchone()
            result.append({
                "clan_id": clan_id, "rank": rank, "name": name, "level": level,
                "banner": banner if banner else "",
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
            [
                {"type": "kill_mobs", "desc": "Убить 5 монстров", "target": 5},
                {"type": "kill_mobs", "desc": "Убить 10 монстров", "target": 10},
                {"type": "kill_mobs", "desc": "Убить 15 монстров", "target": 15}
            ],
            [
                {"type": "raid_success", "desc": "Зачистить 1 подземелье", "target": 1},
                {"type": "raid_success", "desc": "Зачистить 3 подземелья", "target": 3}
            ],
            [
                {"type": "craft_weapon", "desc": "Скрафтить оружие", "target": 1},
                {"type": "craft_armor", "desc": "Скрафтить броню", "target": 1},
                {"type": "craft_potion", "desc": "Приготовить 1 зелье", "target": 1},
                {"type": "complete_card_set", "desc": "Собрать 1 коллекцию карточек", "target": 1}
            ]
        ]
        selected = [random.choice(cat) for cat in categories]
        quests = []
        for q in selected:
            new_q = q.copy()
            new_q["progress"] = 0
            new_q["completed"] = False
            quests.append(new_q)
        quests_data = {"date": today, "quests": quests, "claimed": False}
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
        res = cursor.execute("SELECT name, emoji FROM cards WHERE card_id = ?", (item_id,)).fetchone()
        if res: return f"{res[1]} {res[0]}"
        res = cursor.execute("SELECT name FROM loot_boxes WHERE box_id = ?", (item_id,)).fetchone()
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

def roll_card(user_id: int, theme: str = None) -> dict:
    user = get_user(user_id)
    pity = user.get('pity_counter', 0)
    
    if pity >= 30:
        rarity = "epic"
        update_user(user_id, pity_counter=0)
    else:
        update_user(user_id, pity_counter=pity + 1)
        r = random.uniform(0, 100)
        if r <= 2: rarity = "legendary"
        elif r <= 7: rarity = "epic"
        elif r <= 20: rarity = "rare"
        elif r <= 45: rarity = "uncommon"
        else: rarity = "common"
        
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT set_id, theme FROM card_sets WHERE rarity=?", (rarity,))
        sets = cur.fetchall()
        
        chosen_set = None
        if theme:
            theme_sets = [s[0] for s in sets if s[1] == theme]
            if theme_sets and random.random() < 0.5:
                chosen_set = random.choice(theme_sets)
        
        if not chosen_set:
            chosen_set = random.choice([s[0] for s in sets])
            
        cur.execute("SELECT card_id, name, emoji FROM cards WHERE set_id=?", (chosen_set,))
        cards = cur.fetchall()
        if not cards: return None
        
        card = random.choice(cards)
        
        cur.execute("""
            INSERT INTO user_cards (user_id, card_id, count, first_at) 
            VALUES (?, ?, 1, ?) 
            ON CONFLICT(user_id, card_id) DO UPDATE SET count = count + 1
        """, (user_id, card[0], time.time()))
        conn.commit()
        
        return {"card_id": card[0], "name": card[1], "emoji": card[2], "rarity": rarity}

_analytics_buffer = []

def log_event(user_id: int, category: str, event_type: str, value: int = 0, meta: dict = None):
    global _analytics_buffer
    if meta is None: meta = {}
    _analytics_buffer.append((
        time.time(), user_id, category, event_type, value, json.dumps(meta, ensure_ascii=False)
    ))
    
    if len(_analytics_buffer) >= 50:
        flush_logs()

def flush_logs():
    global _analytics_buffer
    if not _analytics_buffer: return
    
    logs_to_write = _analytics_buffer[:]
    _analytics_buffer.clear()
    
    with get_connection() as conn:
        conn.cursor().executemany('''
            INSERT INTO analytics_logs (timestamp, user_id, event_category, event_type, value_change, metadata) 
            VALUES (?, ?, ?, ?, ?, ?)
        ''', logs_to_write)
        conn.commit()

def get_item_sources(item_id: str) -> list[str]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT location_id, chance, min_amount, max_amount FROM loot_tables WHERE item_id = ?", (item_id,))
        rows = cursor.fetchall()
        
        if not rows:
            return ["Секретное место (или нигде)"]
            
        cursor.execute("SELECT id, name FROM solo_dungeons")
        solo_map = {r[0]: r[1] for r in cursor.fetchall()}
        
        cursor.execute("SELECT day_index, name FROM daily_dungeons")
        daily_map = {str(r[0]): r[1] for r in cursor.fetchall()}
        
        cursor.execute("SELECT region_id, name FROM war_regions")
        war_map = {str(r[0]): r[1] for r in cursor.fetchall()}
        
    sources = []
    for loc, chance, mn, mx in rows:
        loc_name = loc
        if loc in solo_map:
            loc_name = solo_map[loc]
        elif loc in daily_map:
            loc_name = daily_map[loc]
        elif loc in war_map:
            loc_name = war_map[loc]
        elif loc == "solo":
            loc_name = "Одиночные Боссы"
        elif loc == "event_6" or loc == "6":
            loc_name = "Ивент: Кровавый Колизей"
            
        pct = int(chance * 100) if chance >= 0.01 else "<1"
        amount_str = f"{mn}" if mn == mx else f"{mn}-{mx}"
        sources.append(f"{loc_name} ({pct}%, {amount_str} шт.)")
        
    return list(set(sources))

# --- ФУНКЦИИ СЮЖЕТА ---
def get_available_stories(user_id: int) -> list:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, title, desc, req_admin, start_node_id FROM stories")
        rows = cursor.fetchall()
        stories = []
        for r in rows:
            if r[3] != 0 and r[3] != user_id:
                continue
            stories.append({
                "id": r[0], 
                "title": r[1], 
                "desc": r[2], 
                "start_node_id": r[4] if len(r) > 4 and r[4] else 'node_start'
            })
        return stories

def get_story_node(node_id: str) -> dict:
    with get_connection() as conn:
        row = conn.cursor().execute("SELECT id, chapter_id, node_type, text, extra_data FROM story_nodes WHERE id = ?", (node_id,)).fetchone()
        if row: return {"id": row[0], "chapter_id": row[1], "node_type": row[2], "text": row[3], "extra_data": json.loads(row[4])}
    return {}

def get_story_choices(node_id: str) -> list:
    with get_connection() as conn:
        rows = conn.cursor().execute("SELECT id, text, req_cond, action_data, next_node_id FROM story_choices WHERE node_id = ?", (node_id,)).fetchall()
        return [{"id": r[0], "text": r[1], "req_cond": json.loads(r[2]), "action_data": json.loads(r[3]), "next_node_id": r[4]} for r in rows]

def seed_test_story():
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Очистка старых тестовых данных во избежание дублирования кнопок при рестартах
        cursor.execute("DELETE FROM story_choices WHERE node_id LIKE 'node_%'")
        
        cursor.execute("INSERT OR REPLACE INTO stories (id, title, desc, req_admin, start_node_id) VALUES (?, ?, ?, ?, ?)", ('test_story_1', 'Темный переулок', 'Тестовый квест с выборами, боем и флагами', 243702559, 'node_start'))
        cursor.execute("INSERT OR REPLACE INTO story_chapters (id, story_id, title) VALUES (?, ?, ?)", ('chap_1', 'test_story_1', 'Глава 1: Встреча'))
        
        # Узел 1: Встреча
        cursor.execute("INSERT OR REPLACE INTO story_nodes (id, chapter_id, node_type, text, extra_data) VALUES (?, ?, ?, ?, ?)", ('node_start', 'chap_1', 'text', 'Вы встречаете подозрительного эльфа. Он тянется к кинжалу.', '{}'))
        cursor.execute("INSERT OR IGNORE INTO story_choices (node_id, text, req_cond, action_data, next_node_id) VALUES (?, ?, ?, ?, ?)", ('node_start', '🗡 Напасть первым', '{}', '{}', 'node_combat'))
        cursor.execute("INSERT OR IGNORE INTO story_choices (node_id, text, req_cond, action_data, next_node_id) VALUES (?, ?, ?, ?, ?)", ('node_start', '💬 Выслушать', '{}', '{}', 'node_listen'))

        # Узел 2: Выслушать
        cursor.execute("INSERT OR REPLACE INTO story_nodes (id, chapter_id, node_type, text, extra_data) VALUES (?, ?, ?, ?, ?)", ('node_listen', 'chap_1', 'text', 'Эльф хрипит: "Я отравлен... У тебя есть Зелье: Хил?".', '{}'))
        cursor.execute("INSERT OR IGNORE INTO story_choices (node_id, text, req_cond, action_data, next_node_id) VALUES (?, ?, ?, ?, ?)", ('node_listen', '🧪 Отдать зелье', '{"req_item": "Зелье: Хил"}', '{"take_item": "Зелье: Хил", "set_flag": "helped_elf"}', 'node_reward'))

        # Узел Боя
        cursor.execute("INSERT OR REPLACE INTO story_nodes (id, chapter_id, node_type, text, extra_data) VALUES (?, ?, ?, ?, ?)", ('node_combat', 'chap_1', 'combat', '', '{"mob_id": "goblin_thief", "win_node": "node_reward", "lose_node": "node_fail"}'))
        
        # Узел Награды
        cursor.execute("INSERT OR REPLACE INTO story_nodes (id, chapter_id, node_type, text, extra_data) VALUES (?, ?, ?, ?, ?)", ('node_reward', 'chap_1', 'reward', 'Вы прошли испытание! Эльф (или его труп) оставляет вам награду.', '{"gold": 500, "next_node_id": "node_epilogue"}'))
        
        # Провал
        cursor.execute("INSERT OR REPLACE INTO story_nodes (id, chapter_id, node_type, text, extra_data) VALUES (?, ?, ?, ?, ?)", ('node_fail', 'chap_1', 'text', 'Вас избили и выбросили в канаву.', '{"next_node_id": "town"}'))
        cursor.execute("INSERT OR IGNORE INTO story_choices (node_id, text, req_cond, action_data, next_node_id) VALUES (?, ?, ?, ?, ?)", ('node_fail', 'Отползти в лагерь', '{}', '{}', 'town'))

        # НОВЫЙ УЗЕЛ: Эпилог (Проверка флага)
        cursor.execute("INSERT OR REPLACE INTO story_nodes (id, chapter_id, node_type, text, extra_data) VALUES (?, ?, ?, ?, ?)", ('node_epilogue', 'chap_1', 'text', 'Вы собираетесь уйти, но что-то заставляет вас обернуться.', '{}'))
        cursor.execute("INSERT OR IGNORE INTO story_choices (node_id, text, req_cond, action_data, next_node_id) VALUES (?, ?, ?, ?, ?)", ('node_epilogue', 'Уйти в лагерь', '{}', '{}', 'town'))
        # ПРОВЕРЯЕТ ФЛАГ "helped_elf"
        cursor.execute("INSERT OR IGNORE INTO story_choices (node_id, text, req_cond, action_data, next_node_id) VALUES (?, ?, ?, ?, ?)", ('node_epilogue', 'Секрет спасенного эльфа', '{"req_flag": "helped_elf"}', '{}', 'node_secret'))

        # НОВЫЙ УЗЕЛ: Секрет
        cursor.execute("INSERT OR REPLACE INTO story_nodes (id, chapter_id, node_type, text, extra_data) VALUES (?, ?, ?, ?, ?)", ('node_secret', 'chap_1', 'reward', 'Эльф в благодарность за спасение шепчет вам секрет тайника!', '{"gold": 1000, "next_node_id": "town"}'))

        conn.commit()

