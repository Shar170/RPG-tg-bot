import streamlit as st
import sqlite3
import pandas as pd
import json
import os
import io

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, '..', 'bot', 'game_data.db')

st.set_page_config(page_title="RPG Admin", layout="wide")

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

# ==========================================
# 🗄️ СКВОЗНАЯ ПАНЕЛЬ SQL ДЛЯ ВСЕХ ВКЛАДОК
# ==========================================
with st.sidebar:
    st.header("⚡ SQL Консоль")
    st.caption("Доступна во всех вкладках. Выполняет запросы к любым таблицам.")
    
    with st.expander("ℹ️ Список таблиц БД"):
        with get_conn() as conn:
            tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()]
            st.code("\n".join(tables), language="text")

    sql_query = st.text_area("SQL Запрос", height=140, placeholder="UPDATE users SET gold = gold + 500;\n-- или:\nSELECT * FROM users LIMIT 5;")
    
    col_run, col_clear = st.columns([1, 1])
    run_btn = col_run.button("▶️ Выполнить", use_container_width=True)

    if run_btn and sql_query.strip():
        cleaned_query = sql_query.strip()
        try:
            with get_conn() as conn:
                cursor = conn.cursor()
                if cleaned_query.lower().startswith("select") or cleaned_query.lower().startswith("pragma"):
                    result_df = pd.read_sql_query(cleaned_query, conn)
                    st.success(f"Строк получено: {len(result_df)}")
                    st.dataframe(result_df, use_container_width=True)
                else:
                    cursor.execute(cleaned_query)
                    conn.commit()
                    st.success(f"Запрос применен! Изменено строк: {cursor.rowcount}")
                    st.rerun()
        except Exception as e:
            st.error(f"Ошибка SQL: {e}")

# ==========================================
# ОСНОВНОЙ ИНТЕРФЕЙС ВКЛАДОК
# ==========================================
st.title("🛡️ Продвинутая Админ-Панель")
tab1, tab2, tab3, tab4 = st.tabs([
    "🦇 Бестиарий (Урон, Награды и Навыки)", 
    "👥 Игроки", 
    "📊 Таблицы БД",
    "💾 Экспорт SQL"
])

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
            inv_str = st.text_area("JSON Инвентаря", value=json.dumps(json.loads(user['inventory']), indent=4, ensure_ascii=False), height=350)
            
            if st.form_submit_button("💾 Сохранить Игрока"):
                try:
                    parsed_inv = json.loads(inv_str)
                    with get_conn() as conn:
                        conn.execute("UPDATE users SET gold=?, gems=?, hp=?, max_hp=?, level=?, xp=?, clan_id=?, clan_role=?, state=?, inventory=? WHERE user_id=?", 
                                     (new_gold, new_gems, new_hp, new_max_hp, new_level, new_xp, new_clan_id, new_clan_role, new_state, json.dumps(parsed_inv, ensure_ascii=False), int(user['user_id'])))
                        conn.commit()
                    st.success("Игрок обновлен!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Ошибка в JSON: {e}")

with tab3:
    pks = {"game_settings": "key", "loot_tables": "id", "items": "item_id", "daily_dungeons": "day_index", "recipes": "recipe_id", "clans": "clan_id"}
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

# ==========================================
# 💾 ВКЛАДКА ЭКСПОРТА SQL
# ==========================================
with tab4:
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
                # Режим 1: Только структура
                if export_mode.startswith("🏛️"):
                    if line.startswith("INSERT INTO"):
                        continue
                    dump_lines.append(line)
                    
                # Режим 3: Без таблицы игроков
                elif export_mode.startswith("🛡️"):
                    # Пропускаем вставку данных в users
                    if line.startswith('INSERT INTO "users"') or line.startswith("INSERT INTO users"):
                        continue
                    dump_lines.append(line)
                    
                # Режим 2: Полный дамп
                else:
                    dump_lines.append(line)

            sql_result = "\n".join(dump_lines)
            
            # Сохраняем в session_state для скачивания
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
