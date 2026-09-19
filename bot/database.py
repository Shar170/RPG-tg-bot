# database.py
import sqlite3
import json
import datetime
from config import DB_PATH

def get_connection():
    return sqlite3.connect(DB_PATH)

def init_db():
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # 1. Игроки
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                state TEXT,
                hp INTEGER,
                max_hp INTEGER,
                gold INTEGER,
                inventory TEXT,
                home_data TEXT,
                combat_data TEXT,
                known_traits TEXT,
                dungeon_data TEXT
            )
        ''')
        
        # 2. Ивентовые подземелья
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_dungeons (
                day_index INTEGER PRIMARY KEY,
                name TEXT,
                desc TEXT,
                mobs TEXT,
                loot_id TEXT,
                loot_name TEXT
            )
        ''')
        
        # 3. Бестиарий
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bestiary (
                mob_id TEXT PRIMARY KEY,
                name TEXT,
                hp_min INTEGER,
                hp_max INTEGER,
                dmg_min INTEGER,
                dmg_max INTEGER,
                row_pref TEXT
            )
        ''')
        
        # 4. Алхимия
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS alchemy_ingredients (
                item_id TEXT PRIMARY KEY,
                name TEXT,
                traits TEXT
            )
        ''')

        # 5. Предметы
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS items (
                item_id TEXT PRIMARY KEY,
                name TEXT,
                type TEXT,
                base_price INTEGER,
                stats TEXT
            )
        ''')
        conn.commit()

# --- СИДЕРЫ (Начальные данные) ---
def seed_all():
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Сид Данжей
        cursor.execute("SELECT COUNT(*) FROM daily_dungeons")
        if cursor.fetchone()[0] == 0:
            default_dungeons = [
                (0, "💀 Склеп Безумного Короля", "Воздух пропитан некромантией. Во тьме горят синие огни.", 
                 json.dumps(["Скелет-арбалетчик", "Оживший Мертвец", "Призрак стражи"], ensure_ascii=False), "cave_mushroom", "Костяная пыль"),
                (1, "🌋 Вулканическая Кузня", "Жар обжигает легкие. Повсюду течет магма.", 
                 json.dumps(["Магматический Слизень", "Голем-кузнец", "Огненный Элементаль"], ensure_ascii=False), "fire_root", "Магматическое ядро"),
                (2, "🍄 Ядовитые Топи", "Ваши ноги вязнут в трясине. С деревьев капает кислота.", 
                 json.dumps(["Гигантский Паук", "Гнилой Энт", "Токсичный Слизень"], ensure_ascii=False), "poison_gland", "Ядовитая железа"),
                (3, "⏳ Руины Времени", "Пространство здесь искажено. Камни зависли в воздухе.", 
                 json.dumps(["Хранитель Времени", "Магическая Аномалия", "Мимик-часовщик"], ensure_ascii=False), "time_tear", "Слеза времени"),
                (4, "🩸 Катакомбы Культистов", "Стены исписаны кровавыми рунами. Слышны молитвы.", 
                 json.dumps(["Культист-фанатик", "Демоническая Гончая", "Жрец Бездны"], ensure_ascii=False), "demon_blood", "Кровь демона"),
                (5, "🏜 Золотой Мираж", "Стены пещеры усыпаны золотом, иллюзии сводят с ума.", 
                 json.dumps(["Гоблин-вор", "Золотой Мимик", "Дух Алчности"], ensure_ascii=False), "gold_petal", "Золотой лепесток"),
                (6, "⚔️ Колизей Чемпионов", "Арена древних богов. Здесь нет ловушек, только битва.", 
                 json.dumps(["Падший Чемпион", "Берсерк Арены", "Химера"], ensure_ascii=False), "epic_token", "Эпический жетон")
            ]
            cursor.executemany("INSERT INTO daily_dungeons VALUES (?, ?, ?, ?, ?, ?)", default_dungeons)

        # Сид Бестиария
        cursor.execute("SELECT COUNT(*) FROM bestiary")
        if cursor.fetchone()[0] == 0:
            mobs = [
                ("temple_guard", "Храмовый Страж", 50, 70, 10, 18, "front"),
                ("living_idol", "Оживший Идол", 80, 110, 15, 25, "front"),
                ("khmer_priest", "Кхмерский Жрец", 40, 55, 20, 35, "back"),
                ("poison_slime", "Токсичный Слизень", 30, 45, 8, 12, "front"),
                ("time_keeper", "Хранитель Времени", 100, 130, 25, 40, "back"),
                ("skeleton_crossbow", "Скелет-арбалетчик", 35, 50, 15, 20, "back")
            ]
            cursor.executemany("INSERT INTO bestiary VALUES (?, ?, ?, ?, ?, ?, ?)", mobs)

        # Сид Алхимии
        cursor.execute("SELECT COUNT(*) FROM alchemy_ingredients")
        if cursor.fetchone()[0] == 0:
            ingredients = [
                ("cave_mushroom", "Пещерный гриб", json.dumps(["Хил", "Слабость к яду", "Защита от тьмы", "Замедление"], ensure_ascii=False)),
                ("mountain_moss", "Горный мох", json.dumps(["Броня", "Хил", "Реген ОД", "Уязвимость к огню"], ensure_ascii=False)),
                ("fire_root", "Магматическое ядро", json.dumps(["Урон огнем", "Защита от огня", "Сила", "Ожог"], ensure_ascii=False)),
                ("time_tear", "Слеза времени", json.dumps(["Реген ОД", "Ускорение", "Уклонение", "Хрупкость"], ensure_ascii=False))
            ]
            cursor.executemany("INSERT INTO alchemy_ingredients VALUES (?, ?, ?)", ingredients)

        # Сид Предметов
        cursor.execute("SELECT COUNT(*) FROM items")
        if cursor.fetchone()[0] == 0:
            items = [
                ("repair_kit", "Рем-набор", "consumable", 50, "{}"),
                ("khmer_amulet", "Кхмерский Амулет Жизни", "artifact", 1500, "{}"),
                ("smoke_bomb", "Дымовая бомба", "artifact", 120, "{}"),
                ("iron_ingot", "Железный слиток", "material", 15, "{}"),
                ("wood_sword", "Деревянный меч", "weapon", 10, json.dumps({"dmg": 12})),
                ("iron_sword", "Стальной меч", "weapon", 120, json.dumps({"dmg": 28})),
                ("leather_armor", "Кожаная броня", "armor", 20, json.dumps({"def": 5})),
                ("iron_armor", "Железный доспех", "armor", 150, json.dumps({"def": 15}))
            ]
            cursor.executemany("INSERT INTO items VALUES (?, ?, ?, ?, ?)", items)
            
        conn.commit()

# --- ФУНКЦИИ ИГРОКОВ ---
def get_user(user_id: int):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()
        if user:
            return {
                "user_id": user[0], "username": user[1], "state": user[2],
                "hp": user[3], "max_hp": user[4], "gold": user[5],
                "inventory": json.loads(user[6]),
                "home_data": json.loads(user[7] if user[7] else "{}"),
                "combat_data": json.loads(user[8] if user[8] else "{}"),
                "known_traits": json.loads(user[9] if user[9] else "{}"),
                "dungeon_data": json.loads(user[10] if user[10] else "{}")
            }
    return None

def update_user(user_id: int, **kwargs):
    with get_connection() as conn:
        cursor = conn.cursor()
        for key, value in kwargs.items():
            if key in ['inventory', 'home_data', 'combat_data', 'known_traits', 'dungeon_data']:
                value = json.dumps(value)
            cursor.execute(f"UPDATE users SET {key} = ? WHERE user_id = ?", (value, user_id))
        conn.commit()

# --- ФУНКЦИИ ДАННЫХ ИГРЫ ---
def get_today_dungeon():
    day_index = datetime.datetime.today().weekday()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM daily_dungeons WHERE day_index = ?", (day_index,))
        row = cursor.fetchone()
        if row:
            return {"name": row[1], "desc": row[2], "mobs": json.loads(row[3]), "loot": row[4], "loot_name": row[5]}
    return None

def get_mob_by_name(name: str):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM bestiary WHERE name = ?", (name,))
        row = cursor.fetchone()
        if row:
            return {"mob_id": row[0], "name": row[1], "hp_min": row[2], "hp_max": row[3], "dmg_min": row[4], "dmg_max": row[5], "row_pref": row[6]}
    return {"mob_id": "unknown", "name": name, "hp_min": 40, "hp_max": 50, "dmg_min": 10, "dmg_max": 15, "row_pref": "front"}

def get_all_ingredients():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM alchemy_ingredients")
        rows = cursor.fetchall()
        return {row[0]: {"name": row[1], "traits": json.loads(row[2])} for row in rows}

def get_item(item_id: str):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM items WHERE item_id = ?", (item_id,))
        row = cursor.fetchone()
        if row:
            return {"item_id": row[0], "name": row[1], "type": row[2], "base_price": row[3], "stats": json.loads(row[4])}
    return None
