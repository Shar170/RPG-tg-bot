import streamlit as st
import sqlite3
import pandas as pd
import json
import os
import io

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, '..', 'bot', 'game_data.db')

st.set_page_config(page_title="Kamaria RPG Admin", layout="wide", page_icon="🛡️")

def get_conn(): 
    conn = sqlite3.connect(DB_PATH)
    try: conn.execute("ALTER TABLE bestiary ADD COLUMN skills TEXT DEFAULT '{}'")
    except: pass
    try: conn.execute("ALTER TABLE bestiary ADD COLUMN gold_min INTEGER DEFAULT 5")
    except: pass
    try: conn.execute("ALTER TABLE bestiary ADD COLUMN gold_max INTEGER DEFAULT 15")
    except: pass
    try: conn.execute("ALTER TABLE bestiary ADD COLUMN xp_reward INTEGER DEFAULT 10")
    except: pass
    try: conn.execute("CREATE TABLE IF NOT EXISTS game_settings (key TEXT PRIMARY KEY, value TEXT)")
    except: pass
    conn.commit()
    return conn

def fetch_table(table):
    return pd.read_sql_query(f"SELECT * FROM {table}", get_conn())

def save_simple_table(table_name, original_df, edited_df, pk_col):
    with get_conn() as conn:
        cursor = conn.cursor()
        orig_keys = set(original_df[pk_col].astype(str))
        edit_keys = set(edited_df[pk_col].astype(str))
        for key in orig_keys - edit_keys:
            cursor.execute(f"DELETE FROM {table_name} WHERE {pk_col}=?", (key,))
        
        cols = edited_df.columns.tolist()
        placeholders = ",".join(["?"] * len(cols))
        sql = f"INSERT OR REPLACE INTO {table_name} ({','.join(cols)}) VALUES ({placeholders})"
        for _, row in edited_df.iterrows():
            val = tuple(None if pd.isna(x) else x for x in row)
            cursor.execute(sql, val)
        conn.commit()

def get_all_items_dict():
    with get_conn() as conn:
        items = conn.execute("SELECT item_id, name, type FROM items").fetchall()
        alch = conn.execute("SELECT item_id, name FROM alchemy_ingredients").fetchall()
        d = {}
        for i in items: d[i[0]] = {"name": i[1], "type": i[2]}
        for a in alch: d[a[0]] = {"name": a[1], "type": "material"}
        return d

def get_db_schema():
    """Возвращает структуру таблиц и их колонок"""
    schema = {}
    with get_conn() as conn:
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()]
        for t in tables:
            cols = [c[1] for c in conn.execute(f"PRAGMA table_info({t})").fetchall()]
            schema[t] = cols
    return schema

# ==========================================
# 🗄️ БОКОВАЯ ПАНЕЛЬ
# ==========================================
with st.sidebar:
    st.header("⚡ Быстрый SQL")
    st.caption("Быстрая консоль (сквозная во всех вкладках)")
    
    with st.expander("ℹ️ Таблицы БД"):
        schema = get_db_schema()
        for tbl, cols in schema.items():
            st.markdown(f"**`{tbl}`**")
            st.caption(", ".join(cols))

    quick_sql = st.text_area("SQL", height=100, placeholder="SELECT count(*) FROM users;", key="sidebar_sql")
    if st.button("▶️ Выполнить в боковой", use_container_width=True):
        if quick_sql.strip():
            try:
                with get_conn() as conn:
                    cur = conn.cursor()
                    q = quick_sql.strip()
                    if q.lower().startswith(("select", "pragma", "explain")):
                        res_df = pd.read_sql_query(q, conn)
                        st.dataframe(res_df, use_container_width=True)
                    else:
                        cur.execute(q)
                        conn.commit()
                        st.success(f"Затронуто: {cur.rowcount} строк")
                        st.rerun()
            except Exception as e:
                st.error(f"Ошибка: {e}")

# ==========================================
# ОСНОВНОЙ ИНТЕРФЕЙС ВКЛАДОК
# ==========================================
st.title("🛡️ Kamaria RPG — Панель Управления")
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "🦇 Бестиарий", 
    "👥 Игроки", 
    "📖 Рецепты и Алхимия",
    "💻 SQL Запросы",
    "📊 Таблицы БД",
    "💾 Экспорт SQL"
])

# --- ВКЛАДКА 1: БЕСТИАРИЙ ---
with tab1:
    mobs_df = fetch_table("bestiary")
    selected_mob_name = st.selectbox("Выберите монстра:", mobs_df['name'])
    
    if selected_mob_name:
        mob = mobs_df[mobs_df['name'] == selected_mob_name].iloc[0]
        skills_raw = mob.get('skills', '{}')
        if pd.isna(skills_raw) or not skills_raw: skills_raw = '{}'
        skills = json.loads(skills_raw)
        
        with st.form("mob_editor"):
            st.subheader(f"Статы: {mob['name']} ({mob['mob_id']})")
            
            c1, c2, c3 = st.columns(3)
            new_hp_min = c1.number_input("HP Min", value=int(mob['hp_min']))
            new_hp_max = c2.number_input("HP Max", value=int(mob['hp_max']))
            new_pref = c3.selectbox("Ряд (front/back)", ["front", "back"], index=0 if mob['row_pref']=="front" else 1)
            
            c4, c5, _ = st.columns(3)
            new_dmg_min = c4.number_input("Урон Min", value=int(mob['dmg_min']))
            new_dmg_max = c5.number_input("Урон Max", value=int(mob['dmg_max']))
            
            st.markdown("### 💰 Награды (Базовые)")
            c_g1, c_g2, c_xp = st.columns(3)
            new_gold_min = c_g1.number_input("Золото Min", value=int(mob.get('gold_min', 5)))
            new_gold_max = c_g2.number_input("Золото Max", value=int(mob.get('gold_max', 15)))
            new_mob_xp = c_xp.number_input("Опыт (XP)", value=int(mob.get('xp_reward', 10)))
            
            st.markdown("### 🧬 Навыки (0.0 - 1.0)")
            sc1, sc2, sc3 = st.columns(3)
            s_dodge = sc1.slider("Уворот", 0.0, 1.0, float(skills.get('dodge', 0.0)))
            s_counter = sc2.slider("Контратака", 0.0, 1.0, float(skills.get('counter', 0.0)))
            s_repo = sc3.slider("Смена позиции", 0.0, 1.0, float(skills.get('reposition', 0.0)))
            
            sc4, sc5, sc6 = st.columns(3)
            s_poison = sc4.slider("Яд", 0.0, 1.0, float(skills.get('poison', 0.0)))
            s_burn = sc5.slider("Поджог", 0.0, 1.0, float(skills.get('burn', 0.0)))
            s_heal = sc6.slider("Лечение", 0.0, 1.0, float(skills.get('heal', 0.0)))
            
            if st.form_submit_button("💾 Сохранить Монстра"):
                new_skills = json.dumps({"dodge": s_dodge, "counter": s_counter, "reposition": s_repo, "poison": s_poison, "burn": s_burn, "heal": s_heal})
                with get_conn() as conn:
                    conn.execute("UPDATE bestiary SET hp_min=?, hp_max=?, dmg_min=?, dmg_max=?, row_pref=?, skills=?, gold_min=?, gold_max=?, xp_reward=? WHERE mob_id=?", 
                                 (new_hp_min, new_hp_max, new_dmg_min, new_dmg_max, new_pref, new_skills, new_gold_min, new_gold_max, new_mob_xp, str(mob['mob_id'])))
                    conn.commit()
                st.success("Монстр сохранен!")
                st.rerun()

# --- ВКЛАДКА 2: ИГРОКИ ---
with tab2:
    users_df = fetch_table("users")
    if not users_df.empty:
        selected_user = st.selectbox("Выберите игрока:", users_df['username'])
        user = users_df[users_df['username'] == selected_user].iloc[0]
        
        with st.expander("🎁 Выдать предмет игроку"):
            with st.form("give_item_form"):
                all_items = get_all_items_dict()
                options = {k: f"{v['name']} ({k}) [{v['type']}]" for k, v in all_items.items()}
                sel_item = st.selectbox("Предмет", list(options.keys()), format_func=lambda x: options[x])
                qty = st.number_input("Количество", min_value=1, value=1)
                
                if st.form_submit_button("Выдать в инвентарь"):
                    with get_conn() as conn:
                        cur = conn.execute("SELECT inventory FROM users WHERE user_id=?", (int(user['user_id']),))
                        inv = json.loads(cur.fetchone()[0])
                        itype = all_items[sel_item]['type']
                        
                        if itype in ['weapon', 'armor']:
                            for _ in range(qty): inv.setdefault('backpack', []).append(sel_item)
                        elif itype == 'artifact':
                            for _ in range(qty): inv.setdefault('artifacts', []).append(sel_item)
                        elif itype == 'consumable':
                            for _ in range(qty): inv.setdefault('potions', []).append(all_items[sel_item]['name'])
                        else:
                            inv.setdefault('materials', {})[sel_item] = inv.setdefault('materials', {}).get(sel_item, 0) + qty
                            
                        conn.execute("UPDATE users SET inventory=? WHERE user_id=?", (json.dumps(inv, ensure_ascii=False), int(user['user_id'])))
                        conn.commit()
                    st.success("Выдано!")
                    st.rerun()

        with st.form("user_editor"):
            st.subheader(f"Профиль: {user['username']}")
            
            c1, c2, c3 = st.columns(3)
            new_gold = c1.number_input("Золото 🪙", value=int(user['gold']))
            new_gems = c2.number_input("Алмазы 💎", value=int(user.get('gems', 0)))
            new_state = c3.text_input("Состояние (state)", value=str(user['state']))
            
            c4, c5, c6 = st.columns(3)
            new_hp = c4.number_input("Текущее ХП", value=int(user['hp']))
            new_max_hp = c5.number_input("Макс ХП", value=int(user['max_hp']))
            new_level = c6.number_input("Уровень", value=int(user.get('level', 1)))
            
            c7, c8, c9 = st.columns(3)
            new_xp = c7.number_input("Опыт (XP)", value=int(user.get('xp', 0)))
            new_clan_id = c8.number_input("ID Клана (0 = нет)", value=int(user.get('clan_id', 0)))
            
            current_role = user.get('clan_role', 'thrall')
            if current_role not in ["thrall", "lindeman", "hedwing"]: current_role = "thrall"
            new_clan_role = c9.selectbox("Роль в клане", ["thrall", "lindeman", "hedwing"], index=["thrall", "lindeman", "hedwing"].index(current_role))
            
            st.markdown("### 🎒 Прямое редактирование Инвентаря (JSON)")
            inv_str = st.text_area("JSON Инвентаря", value=json.dumps(json.loads(user['inventory']), indent=4, ensure_ascii=False), height=300)
            
            st.markdown("### 🏡 Данные Дома / Статистика (JSON)")
            home_raw = user.get('home_data', '{}')
            if pd.isna(home_raw) or not home_raw: home_raw = '{}'
            home_str = st.text_area("JSON home_data", value=json.dumps(json.loads(home_raw), indent=4, ensure_ascii=False), height=180)

            if st.form_submit_button("💾 Сохранить Игрока"):
                try:
                    parsed_inv = json.loads(inv_str)
                    parsed_home = json.loads(home_str)
                    with get_conn() as conn:
                        conn.execute("""
                            UPDATE users SET 
                                gold=?, gems=?, hp=?, max_hp=?, level=?, xp=?, 
                                clan_id=?, clan_role=?, state=?, inventory=?, home_data=? 
                            WHERE user_id=?
                        """, (
                            new_gold, new_gems, new_hp, new_max_hp, new_level, new_xp, 
                            new_clan_id, new_clan_role, new_state, 
                            json.dumps(parsed_inv, ensure_ascii=False), 
                            json.dumps(parsed_home, ensure_ascii=False), 
                            int(user['user_id'])
                        ))
                        conn.commit()
                    st.success("Игрок успешно обновлен!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Ошибка валидации JSON: {e}")

# --- ВКЛАДКА 3: РЕЦЕПТЫ И АЛХИМИЯ ---
with tab3:
    st.subheader("🔨 Рецепты Мастерской (Кузница)")
    recipes_df = fetch_table("recipes")
    items_dict = get_all_items_dict()
    
    if not recipes_df.empty:
        parsed_recipes = []
        for _, row in recipes_df.iterrows():
            res_id = str(row['result_item_id'])
            res_name = items_dict.get(res_id, {}).get("name", res_id)
            
            mats_raw = row['materials_needed']
            try:
                mats_dict = json.loads(mats_raw) if isinstance(mats_raw, str) else mats_raw
                mats_formatted = ", ".join([f"{items_dict.get(k, {}).get('name', k)}: {v} шт." for k, v in mats_dict.items()])
            except:
                mats_formatted = str(mats_raw)
                
            parsed_recipes.append({
                "ID Рецепта": row['recipe_id'],
                "Результат": f"{res_name} ({res_id})",
                "Требуемые ресурсы": mats_formatted,
                "Стоимость (🪙 Золото)": int(row['gold_cost'])
            })
        st.dataframe(pd.DataFrame(parsed_recipes), use_container_width=True)
    else:
        st.info("Таблица рецептов пуста.")

    with st.expander("➕ Добавить новый рецепт крафта"):
        with st.form("add_recipe_form"):
            c_r1, c_r2 = st.columns(2)
            new_r_id = c_r1.text_input("ID Рецепта (уникальный)", placeholder="rec_mithril_blade")
            new_res_id = c_r2.selectbox("Создаваемый предмет", list(items_dict.keys()), format_func=lambda x: f"{items_dict[x]['name']} ({x})")
            
            c_m1, c_m2 = st.columns([2, 1])
            new_mats_json = c_m1.text_input('Материалы (JSON)', value='{"iron_ingot": 5}')
            new_gold_cost = c_m2.number_input("Цена в золоте", min_value=0, value=100)
            
            if st.form_submit_button("Добавить рецепт"):
                try:
                    json.loads(new_mats_json)
                    with get_conn() as conn:
                        conn.execute("INSERT OR REPLACE INTO recipes (recipe_id, result_item_id, materials_needed, gold_cost) VALUES (?, ?, ?, ?)",
                                     (new_r_id.strip(), new_res_id, new_mats_json.strip(), int(new_gold_cost)))
                        conn.commit()
                    st.success("Рецепт успешно добавлен!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Ошибка валидации: {e}")

    st.divider()
    st.subheader("🧪 Алхимический Справочник (Свойства ингредиентов)")
    alch_df = fetch_table("alchemy_ingredients")
    if not alch_df.empty:
        alch_display = []
        for _, row in alch_df.iterrows():
            traits_raw = row['traits']
            try:
                traits_list = json.loads(traits_raw) if isinstance(traits_raw, str) else traits_raw
                traits_str = " • ".join(traits_list)
            except:
                traits_str = str(traits_raw)
                
            alch_display.append({
                "ID": row['item_id'],
                "Название": row['name'],
                "Свойства (Traits)": traits_str,
                "Базовая цена": row.get('base_price', 10)
            })
        st.dataframe(pd.DataFrame(alch_display), use_container_width=True)

# =====================================================================
# 💻 ВКЛАДКА 4: РАЗДЕЛ ДЛЯ ПРЯМЫХ SQL ЗАПРОСОВ (НОВОЕ!)
# =====================================================================
with tab4:
    st.subheader("💻 Прямые SQL запросы к базе данных")
    st.markdown("Здесь можно исполнять любые запросы: `SELECT`, `UPDATE`, `INSERT`, `DELETE`, `ALTER TABLE` и целые скрипты.")

    # Быстрые шаблоны
    with st.expander("⚡ Готовые шаблоны запросов (кликните, чтобы скопировать)"):
        c_t1, c_t2 = st.columns(2)
        with c_t1:
            st.code("-- Посмотреть топ-10 богатых игроков\nSELECT username, gold, gems, level FROM users ORDER BY gold DESC LIMIT 10;", language="sql")
            st.code("-- Выдать всем игрокам по 500 золота и 10 алмазов\nUPDATE users SET gold = gold + 500, gems = gems + 10;", language="sql")
            st.code("-- Сбросить стейт зависших игроков в лагерь\nUPDATE users SET state = 'STATE_TOWN' WHERE state != 'STATE_TOWN';", language="sql")
        with c_t2:
            st.code("-- Накрутить статистику убийств конкретному игроку\nUPDATE users SET home_data = json_set(home_data, '$.mobs_killed', 50, '$.bosses_killed', 5) WHERE username = 'ВАШ_НИК';", language="sql")
            st.code("-- Восстановить энергию всем до 5\nUPDATE users SET energy = 5;", language="sql")
            st.code("-- Список всех таблиц и количества строк\nSELECT name, type FROM sqlite_master WHERE type='table';", language="sql")

    # Основная область ввода
    col_editor, col_schema = st.columns([3, 1])

    with col_schema:
        st.markdown("**Схема таблиц:**")
        schema = get_db_schema()
        selected_tbl_info = st.selectbox("Таблица для инспекции:", list(schema.keys()))
        if selected_tbl_info:
            cols = schema[selected_tbl_info]
            st.code("\n".join(cols), language="text")

    with col_editor:
        user_sql = st.text_area(
            "Введите SQL запрос или скрипт:",
            height=220,
            placeholder="SELECT * FROM users WHERE level >= 10;\n-- или любой UPDATE/INSERT",
            key="main_sql_input"
        )
        
        col_exec, col_clear, _ = st.columns([1, 1, 2])
        exec_btn = col_exec.button("🚀 Выполнить запрос", type="primary", use_container_width=True)

    if exec_btn:
        if not user_sql.strip():
            st.warning("Запрос пустой!")
        else:
            q = user_sql.strip()
            # Проверяем, одиночный ли это SELECT
            is_select = q.lower().startswith(("select", "pragma", "explain", "with")) and ";" not in q.rstrip(";")
            
            try:
                with get_conn() as conn:
                    cursor = conn.cursor()
                    
                    if is_select:
                        df_res = pd.read_sql_query(q, conn)
                        st.success(f"Запрос выполнен успешно! Найдено строк: **{len(df_res)}**")
                        st.dataframe(df_res, use_container_width=True)
                        
                        # Возможность скачать выборку в CSV
                        csv = df_res.to_csv(index=False).encode('utf-8')
                        st.download_button(
                            "📥 Скачать результат в CSV",
                            data=csv,
                            file_name="query_result.csv",
                            mime="text/csv"
                        )
                    else:
                        # Если это скрипт или DDL/DML операция
                        cursor.executescript(q)
                        conn.commit()
                        st.success("✅ Запрос / Скрипт успешно применен к базе данных!")
                        st.info(f"Затронуто строк (последняя операция): {cursor.rowcount}")
                        
            except Exception as e:
                st.error(f"❌ Ошибка выполнения SQL:\n\n`{str(e)}`")

# --- ВКЛАДКА 5: ТАБЛИЦЫ БД ---
with tab5:
    pks = {"game_settings": "key", "loot_tables": "id", "items": "item_id", "daily_dungeons": "day_index", "recipes": "recipe_id", "clans": "clan_id", "alchemy_ingredients": "item_id"}
    table_to_edit = st.selectbox("Таблица:", list(pks.keys()))
    df = fetch_table(table_to_edit)
    edited = st.data_editor(df, num_rows="dynamic", use_container_width=True, key=f"tbl_{table_to_edit}")
    
    if st.button(f"💾 Сохранить {table_to_edit}"):
        try:
            save_simple_table(table_to_edit, df, edited, pks[table_to_edit])
            st.success("Таблица сохранена!")
            st.rerun()
        except Exception as e:
            st.error(f"Ошибка: {e}")

# --- ВКЛАДКА 6: ЭКСПОРТ SQL ---
with tab6:
    st.subheader("📥 Выгрузка базы данных в формате SQL")
    st.markdown("Сгенерируйте и скачайте SQL-дамп текущей базы данных.")

    export_mode = st.radio(
        "Выберите режим экспорта:",
        [
            "🏛️ Только структура (без строк данных)",
            "📦 Вся база данных целиком (структура + все данные)",
            "🛡️ Вся база без игроков (контент игры, настройки, лут, но без users)"
        ]
    )

    if st.button("⚙️ Сгенерировать SQL скрипт"):
        with get_conn() as conn:
            dump_lines = []
            
            for line in conn.iterdump():
                if export_mode.startswith("🏛️"):
                    if line.startswith("INSERT INTO"):
                        continue
                    dump_lines.append(line)
                elif export_mode.startswith("🛡️"):
                    if line.startswith('INSERT INTO "users"') or line.startswith("INSERT INTO users"):
                        continue
                    dump_lines.append(line)
                else:
                    dump_lines.append(line)

            sql_result = "\n".join(dump_lines)
            st.session_state['exported_sql'] = sql_result
            
            if export_mode.startswith("🏛️"):
                st.session_state['export_filename'] = "schema_only.sql"
            elif export_mode.startswith("🛡️"):
                st.session_state['export_filename'] = "game_data_no_users.sql"
            else:
                st.session_state['export_filename'] = "full_backup.sql"

    if 'exported_sql' in st.session_state:
        st.success(f"SQL скрипт успешно сформирован! Размер: {len(st.session_state['exported_sql'].encode('utf-8')) / 1024:.2f} КБ")
        
        st.download_button(
            label=f"💾 Скачать {st.session_state['export_filename']}",
            data=st.session_state['exported_sql'],
            file_name=st.session_state['export_filename'],
            mime="application/sql",
            use_container_width=True
        )
        
        with st.expander("👀 Предпросмотр сгенерированного SQL (первые 100 строк)"):
            preview_lines = "\n".join(st.session_state['exported_sql'].splitlines()[:100])
            st.code(preview_lines, language="sql")
