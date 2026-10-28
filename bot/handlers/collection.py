import json
import random
import time
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database import get_connection, get_user, update_user, log_event, add_quest_progress, sync_medals

router = Router()

# Баланс экономики пыли
DUST_REWARD = {
    "common": 1,
    "uncommon": 5,
    "rare": 20,
    "epic": 100,
    "legendary": 300
}

DUST_COST = {
    "common": 10,
    "uncommon": 30,
    "rare": 100,
    "epic": 400,
    "legendary": 1000
}

def get_all_sets():
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT set_id, name, desc, rarity, reward_box_id FROM card_sets")
        return {r[0]: {"name": r[1], "desc": r[2], "rarity": r[3], "reward": r[4]} for r in cur.fetchall()}

def get_cards_in_set(set_id):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT card_id, name, emoji, rarity_internal FROM cards WHERE set_id=?", (set_id,))
        return [{"card_id": r[0], "name": r[1], "emoji": r[2], "rarity": r[3]} for r in cur.fetchall()]

def get_user_cards_dict(user_id):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT card_id, count FROM user_cards WHERE user_id=? AND count > 0", (user_id,))
        return {r[0]: r[1] for r in cur.fetchall()}

def get_user_boxes_dict(user_id):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT box_id, count FROM user_boxes WHERE user_id=? AND count > 0", (user_id,))
        return {r[0]: r[1] for r in cur.fetchall()}

@router.callback_query(F.data == "collection_main")
async def collection_main(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    dust = user.get('dust', 0)
    
    text = (
        "🃏 **Альбом Коллекционера**\n\n"
        "Собирайте наборы карточек из подземелий, чтобы обменивать их на ценные Лутбоксы.\n\n"
        f"✨ Магическая пыль: **{dust}**\n*(Пыль получается при распылении дубликатов. Используйте её для создания недостающих карт!)*\n\n"
        "Куда заглянем?"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎴 Мои Наборы", callback_data="collection_sets")],
        [InlineKeyboardButton(text="📦 Мои Лутбоксы", callback_data="collection_boxes")],
        [InlineKeyboardButton(text="✨ Создать карту (за пыль)", callback_data="collection_craft_sets")],
        [InlineKeyboardButton(text="♻️ Распылить дубликаты", callback_data="collection_dust")],
        [InlineKeyboardButton(text="🔙 В Дом", callback_data="town_home")]
    ])
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    except: pass

# ==========================================
# --- ПРОСМОТР И СБОРКА НАБОРОВ ---
# ==========================================
@router.callback_query(F.data == "collection_sets")
async def collection_sets(callback: CallbackQuery):
    user_cards = get_user_cards_dict(callback.from_user.id)
    sets = get_all_sets()
    
    text = "🎴 **Альбом Наборов**\nВыберите набор для просмотра:\n\n"
    buttons = []
    
    for set_id, s_info in sets.items():
        cards_in_set = get_cards_in_set(set_id)
        
        # Строим визуальный ряд эмодзи для кнопки и считаем собранные
        emoji_str = ""
        collected = 0
        for c in cards_in_set:
            if c['card_id'] in user_cards:
                emoji_str += c['emoji']
                collected += 1
            else:
                emoji_str += "❔"
                
        status_icon = "🟢" if collected == len(cards_in_set) else "🔴"
        btn_text = f"{status_icon} {s_info['name']} [{emoji_str}]"
        buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"collection_view:{set_id}")])
        
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="collection_main")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data.startswith("collection_view:"))
async def collection_view_set(callback: CallbackQuery):
    set_id = callback.data.split(":")[1]
    sets = get_all_sets()
    s_info = sets.get(set_id)
    if not s_info: return await callback.answer("Набор не найден!")
    
    user_cards = get_user_cards_dict(callback.from_user.id)
    cards = get_cards_in_set(set_id)
    
    total = len(cards)
    collected = sum(1 for c in cards if c['card_id'] in user_cards)
    
    text = (
        f"🎴 **Набор: {s_info['name']}**\n"
        f"_{s_info['desc']}_\n\n"
        f"Собрано: **{collected}/{total}**\n\n"
        f"**Список карт:**\n"
    )
    
    for c in cards:
        if c['card_id'] in user_cards:
            count = user_cards[c['card_id']]
            dupes_text = f" *(Дубликатов: {count - 1})*" if count > 1 else ""
            text += f"• {c['emoji']} **{c['name']}** — {count} шт.{dupes_text}\n"
        else:
            text += f"• ❔ *Неизвестная карта*\n"
            
    buttons = []
    if collected == total:
        text += "\n🎉 **Набор собран!** Вы можете сдать 1 копию каждой карты в обмен на награду."
        buttons.append([InlineKeyboardButton(text="🎁 Получить Лутбокс", callback_data=f"collection_claim:{set_id}")])
        
    buttons.append([InlineKeyboardButton(text="🔙 К списку наборов", callback_data="collection_sets")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data.startswith("collection_claim:"))
async def collection_claim_reward(callback: CallbackQuery):
    set_id = callback.data.split(":")[1]
    sets = get_all_sets()
    s_info = sets.get(set_id)
    user_id = callback.from_user.id
    user_cards = get_user_cards_dict(user_id)
    cards = get_cards_in_set(set_id)
    
    if any(c['card_id'] not in user_cards for c in cards):
        return await callback.answer("Набор не собран полностью!", show_alert=True)
        
    box_id = s_info['reward']
    
    with get_connection() as conn:
        cur = conn.cursor()
        for c in cards:
            cur.execute("UPDATE user_cards SET count = count - 1 WHERE user_id=? AND card_id=?", (user_id, c['card_id']))
        cur.execute("INSERT INTO user_boxes (user_id, box_id, count) VALUES (?, ?, 1) ON CONFLICT(user_id, box_id) DO UPDATE SET count=count+1", (user_id, box_id))
        conn.commit()
        
    # ПРОГРЕСС КВЕСТА И ЛОГИРОВАНИЕ
    add_quest_progress(user_id, "complete_card_set", 1)
    log_event(user_id, 'collection', 'claim_set_reward', 1, {'set_id': set_id, 'box_id': box_id})
        
    await callback.answer("🎉 Набор сдан! Лутбокс добавлен в вашу кладовую.", show_alert=True)
    await collection_main(callback)

# ==========================================
# --- РАСПЫЛЕНИЕ И КРАФТ КАРТ ---
# ==========================================
@router.callback_query(F.data == "collection_dust")
async def collection_dust_duplicates(callback: CallbackQuery):
    user_id = callback.from_user.id
    dust_gained = 0
    
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT u.card_id, u.count, c.rarity_internal 
            FROM user_cards u 
            JOIN cards c ON u.card_id = c.card_id 
            WHERE u.user_id=? AND u.count > 1
        """, (user_id,))
        dupes = cur.fetchall()
        
        for card_id, count, rarity in dupes:
            extra = count - 1
            reward_per_card = DUST_REWARD.get(rarity, 1)
            dust_gained += extra * reward_per_card
            cur.execute("UPDATE user_cards SET count = 1 WHERE user_id=? AND card_id=?", (user_id, card_id))
            
        if dust_gained > 0:
            cur.execute("UPDATE users SET dust = dust + ? WHERE user_id=?", (dust_gained, user_id))
        conn.commit()
        
    if dust_gained == 0:
        await callback.answer("У вас нет дубликатов для распыления!", show_alert=True)
    else:
        # ЛОГИРОВАНИЕ
        log_event(user_id, 'collection', 'dust_cards', dust_gained)
        await callback.answer(f"♻️ Распылено дубликатов! Получено пыли: +{dust_gained} ✨", show_alert=True)
        await collection_main(callback)

@router.callback_query(F.data == "collection_craft_sets")
async def collection_craft_sets(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    dust = user.get('dust', 0)
    user_cards = get_user_cards_dict(user['user_id'])
    sets = get_all_sets()
    
    text = f"✨ **Создание карт** | Пыль: **{dust}**\n\nВыберите набор, в котором вам не хватает карт:"
    buttons = []
    
    for set_id, s_info in sets.items():
        cards_in_set = get_cards_in_set(set_id)
        total = len(cards_in_set)
        collected = sum(1 for c in cards_in_set if c['card_id'] in user_cards)
        
        if collected < total:
            btn_text = f"{s_info['name']} ({collected}/{total})"
            buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"coll_cr_set:{set_id}")])
        
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="collection_main")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data.startswith("coll_cr_set:"))
async def collection_craft_cards_list(callback: CallbackQuery):
    set_id = callback.data.split(":")[1]
    user = get_user(callback.from_user.id)
    dust = user.get('dust', 0)
    user_cards = get_user_cards_dict(user['user_id'])
    
    sets = get_all_sets()
    s_info = sets.get(set_id)
    cards = get_cards_in_set(set_id)
    
    text = f"✨ **Создание карт: {s_info['name']}**\nУ вас пыли: **{dust}**\n\nВыберите карту для создания:\n"
    buttons = []
    
    for c in cards:
        if c['card_id'] not in user_cards:
            cost = DUST_COST.get(c['rarity'], 10)
            btn_text = f"{c['emoji']} {c['name']} — {cost} ✨"
            buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"coll_cr_do:{c['card_id']}")])
            
    if not buttons:
        text = f"✨ **Создание карт: {s_info['name']}**\n\n🎉 Вы скрафтили все недостающие карты в этом наборе!"
            
    buttons.append([InlineKeyboardButton(text="🔙 К выбору набора", callback_data="collection_craft_sets")])
    
    try:
        await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")
    except: pass

@router.callback_query(F.data.startswith("coll_cr_do:"))
async def collection_craft_execute(callback: CallbackQuery):
    card_id = callback.data.split(":")[1]
    user = get_user(callback.from_user.id)
    dust = user.get('dust', 0)
    
    # СТРОГАЯ ПРОВЕРКА ОТ ДАБЛ-КЛИКОВ: есть ли уже эта карта
    user_cards = get_user_cards_dict(user['user_id'])
    
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT name, emoji, set_id, rarity_internal FROM cards WHERE card_id=?", (card_id,))
        card_info = cur.fetchone()
        
    if not card_info:
        return await callback.answer("Карта не найдена!", show_alert=True)
        
    c_name, c_emoji, set_id, rarity = card_info
    
    # Если юзер уже скрафтил карту, но успел кликнуть еще раз до обновления меню
    if card_id in user_cards:
        await callback.answer("Эта карта уже есть в вашей коллекции!", show_alert=True)
        callback.data = f"coll_cr_set:{set_id}"
        return await collection_craft_cards_list(callback)
    
    cost = DUST_COST.get(rarity, 10)
    
    if dust < cost:
        return await callback.answer(f"Недостаточно пыли! Нужно {cost} ✨", show_alert=True)
        
    # Списываем пыль и добавляем карту (строго count = 1, чтобы не генерить дубликаты)
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE users SET dust = dust - ? WHERE user_id=?", (cost, user['user_id']))
        cur.execute("""
            INSERT INTO user_cards (user_id, card_id, count, first_at) 
            VALUES (?, ?, 1, ?) 
            ON CONFLICT(user_id, card_id) DO UPDATE SET count = 1
        """, (user['user_id'], card_id, time.time()))
        conn.commit()
        
    # ЛОГИРОВАНИЕ
    log_event(user['user_id'], 'collection', 'craft_card', -cost, {'card_id': card_id})
    sync_medals(user['user_id'])
        
    await callback.answer(f"✨ Создано: {c_emoji} {c_name}!", show_alert=True)
    
    # Возвращаем в список карт этого сета (кнопка скупленной карты исчезнет)
    callback.data = f"coll_cr_set:{set_id}"
    await collection_craft_cards_list(callback)

# ==========================================
# --- ОТКРЫТИЕ ЛУТБОКСОВ ---
# ==========================================
@router.callback_query(F.data == "collection_boxes")
async def collection_boxes(callback: CallbackQuery):
    user_boxes = get_user_boxes_dict(callback.from_user.id)
    
    if not user_boxes:
        text = "📦 **Мои Лутбоксы**\n\nУ вас пока нет нераспечатанных коробок. Собирайте полные наборы карточек, чтобы их получать!"
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="collection_main")]])
        return await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        
    text = "📦 **Мои Лутбоксы**\n\nВыберите сундук для открытия:\n"
    buttons = []
    
    with get_connection() as conn:
        cur = conn.cursor()
        for b_id, count in user_boxes.items():
            cur.execute("SELECT name FROM loot_boxes WHERE box_id=?", (b_id,))
            b_name = cur.fetchone()[0]
            buttons.append([InlineKeyboardButton(text=f"Открыть: {b_name} (x{count})", callback_data=f"box_open:{b_id}")])
            
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="collection_main")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

def _open_box(user_id: int, box_id: str) -> str:
    """Consume a box and grant every reward in one SQLite transaction."""
    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        box = conn.execute("SELECT name,type,contents FROM loot_boxes WHERE box_id=?", (box_id,)).fetchone()
        user = conn.execute("SELECT gold,gems,inventory,level FROM users WHERE user_id=?", (user_id,)).fetchone()
        if not box or not user:
            raise ValueError("Бокс не найден!")
        cur = conn.execute("UPDATE user_boxes SET count=count-1 WHERE user_id=? AND box_id=? AND count>0", (user_id, box_id))
        if cur.rowcount != 1:
            raise ValueError("У вас нет этого бокса!")
        b_name, b_type, raw = box
        contents = json.loads(raw)
        inv = json.loads(user[2] or '{}')
        log = f"🎁 **Открыт {b_name}!**\n\nВы получили:\n"
        gold, gems = contents.get('gold', 0), contents.get('gems', 0)
        if gold:
            log += f"🪙 Золото: {gold}\n"
        if gems:
            log += f"💎 Алмазы: {gems}\n"
        if b_type == 'mats':
            pool = conn.execute("SELECT item_id,name FROM alchemy_ingredients").fetchall()
            for mat_id, name in random.choices(pool, k=contents.get('count', 3)):
                materials = inv.setdefault('materials', {})
                materials[mat_id] = materials.get(mat_id, 0) + 1
                log += f"📦 {name} (Ингредиент)\n"
        elif b_type in ('weapon', 'armor', 'epic_mix', 'leg_mix'):
            count = contents.get('equip_count', 2) if b_type == 'epic_mix' else contents.get('count', 1)
            max_level = (user[3] or 1) + 2
            if b_type in ('epic_mix', 'leg_mix'):
                pool = conn.execute("SELECT item_id,name,type FROM items WHERE type IN ('weapon','armor') AND CAST(json_extract(stats, '$.req_lvl') AS INTEGER)<=?", (max_level,)).fetchall()
            else:
                pool = conn.execute("SELECT item_id,name,type FROM items WHERE type=? AND CAST(json_extract(stats, '$.req_lvl') AS INTEGER)<=?", (b_type, max_level)).fetchall()
            if pool:
                for item_id, name, kind in random.choices(pool, k=count):
                    inv.setdefault('backpack', []).append(item_id)
                    log += f"{'⚔️' if kind == 'weapon' else '🛡'} {name} (Снаряжение)\n"
        elif b_type == 'cards':
            pool = conn.execute("SELECT card_id,name,emoji,rarity_internal FROM cards").fetchall()
            if pool:
                for card_id, name, emoji, rarity in random.choices(pool, k=contents.get('count', 3)):
                    conn.execute("INSERT INTO user_cards (user_id,card_id,count,first_at) VALUES (?,?,1,?) ON CONFLICT(user_id,card_id) DO UPDATE SET count=count+1", (user_id, card_id, time.time()))
                    log += f"🎴 {emoji} {name} ({rarity})\n"
        conn.execute("UPDATE users SET gold=gold+?,gems=gems+?,inventory=? WHERE user_id=?", (gold, gems, json.dumps(inv, ensure_ascii=False), user_id))
        return log


@router.callback_query(F.data.startswith("box_open:"))
async def box_open(callback: CallbackQuery):
    box_id = callback.data.split(":", 1)[1]
    user_id = callback.from_user.id
    try:
        log = _open_box(user_id, box_id)
    except ValueError as exc:
        return await callback.answer(str(exc), show_alert=True)
    sync_medals(user_id)
    log_event(user_id, 'collection', 'open_box', 1, {'box_id': box_id})
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 Открыть еще один", callback_data="collection_boxes")],
        [InlineKeyboardButton(text="🔙 В альбом", callback_data="collection_main")]
    ])
    await callback.message.edit_text(log, reply_markup=kb, parse_mode="Markdown")
