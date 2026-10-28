import time
import json
from collections import Counter
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from database import get_connection, get_user, update_user, get_item, get_item_name, get_item_price, give_item, take_item

router = Router()

class TPState(StatesGroup):
    waiting_price = State()

def get_tp_tax(price: int) -> int:
    if price < 100: return max(1, int(price * 0.05))
    if price <= 999: return int(price * 0.08)
    if price <= 9999: return int(price * 0.11)
    return int(price * 0.14)

def get_listing_fee(price: int) -> int:
    return max(1, int(price * 0.03))


class TradeError(Exception):
    pass


def _change_item(conn, user_id, item_id, item_type, delta):
    """Move one item within the caller's transaction."""
    if item_type in ('card', 'box'):
        table, col = ('user_cards', 'card_id') if item_type == 'card' else ('user_boxes', 'box_id')
        if delta < 0:
            cur = conn.execute(f'UPDATE {table} SET count=count-1 WHERE user_id=? AND {col}=? AND count>0', (user_id, item_id))
            if cur.rowcount != 1:
                raise TradeError('Предмет не найден в инвентаре!')
        elif item_type == 'card':
            conn.execute('INSERT INTO user_cards (user_id,card_id,count,first_at) VALUES (?,?,1,?) ON CONFLICT(user_id,card_id) DO UPDATE SET count=count+1', (user_id, item_id, time.time()))
        else:
            conn.execute('INSERT INTO user_boxes (user_id,box_id,count) VALUES (?,?,1) ON CONFLICT(user_id,box_id) DO UPDATE SET count=count+1', (user_id, item_id))
        return
    row = conn.execute('SELECT inventory FROM users WHERE user_id=?', (user_id,)).fetchone()
    if not row:
        raise TradeError('Игрок не найден!')
    inv = json.loads(row[0] or '{}')
    if item_type in ('weapon', 'armor', 'consumable'):
        category = 'potions' if item_type == 'consumable' else 'backpack'
        items = inv.setdefault(category, [])
        if delta < 0:
            if item_id not in items:
                raise TradeError('Предмет не найден в инвентаре!')
            items.remove(item_id)
        else:
            items.append(item_id)
    elif item_type == 'material':
        items = inv.setdefault('materials', {})
        count = items.get(item_id, 0) + delta
        if count < 0:
            raise TradeError('Предмет не найден в инвентаре!')
        if count:
            items[item_id] = count
        else:
            items.pop(item_id, None)
    else:
        raise TradeError('Этот тип предмета нельзя передать.')
    conn.execute('UPDATE users SET inventory=? WHERE user_id=?', (json.dumps(inv, ensure_ascii=False), user_id))


def _buy_lot(lot_id, buyer_id):
    with get_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute('SELECT item_id,item_type,price,seller_id FROM trading_post WHERE lot_id=?', (lot_id,)).fetchone()
        if not row:
            raise TradeError('Лот больше не доступен!')
        item_id, item_type, price, seller_id = row
        if seller_id == buyer_id:
            raise TradeError('Нельзя купить собственный лот!')
        if price < 1:
            raise TradeError('Некорректная цена лота!')
        tax = get_tp_tax(price)
        profit = price - tax
        cur = conn.execute('UPDATE users SET gold=gold-? WHERE user_id=? AND gold>=?', (price, buyer_id, price))
        if cur.rowcount != 1:
            raise TradeError('Недостаточно золота!')
        cur = conn.execute('UPDATE users SET gold=gold+? WHERE user_id=?', (profit, seller_id))
        if cur.rowcount != 1:
            raise TradeError('Продавец не найден!')
        _change_item(conn, buyer_id, item_id, item_type, 1)
        conn.execute('DELETE FROM trading_post WHERE lot_id=?', (lot_id,))
        conn.execute('INSERT INTO tp_history (seller_id,buyer_id,item_id,price,tax_paid,timestamp) VALUES (?,?,?,?,?,?)', (seller_id, buyer_id, item_id, price, tax, time.time()))
        return item_id, price, seller_id, profit


def _create_lot(user_id, item_id, item_type, price):
    fee = get_listing_fee(price)
    with get_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute('SELECT gold,level FROM users WHERE user_id=?', (user_id,)).fetchone()
        if not row or row[0] < fee:
            raise TradeError(f'Не хватает золота для сбора площадки ({fee} 🪙).')
        max_slots = min(10, 5 + row[1] // 10)
        if conn.execute('SELECT COUNT(*) FROM trading_post WHERE seller_id=?', (user_id,)).fetchone()[0] >= max_slots:
            raise TradeError(f'Достигнут лимит слотов ({max_slots})!')
        _change_item(conn, user_id, item_id, item_type, -1)
        conn.execute("UPDATE users SET gold=gold-?,state='STATE_TOWN' WHERE user_id=?", (fee, user_id))
        now = time.time()
        conn.execute('INSERT INTO trading_post (seller_id,item_id,item_type,price,created_at,expires_at) VALUES (?,?,?,?,?,?)', (user_id, item_id, item_type, price, now, now + 86400))
    return fee


def _cancel_lot(lot_id, user_id):
    with get_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        lot = conn.execute('SELECT item_id,item_type,price FROM trading_post WHERE lot_id=? AND seller_id=?', (lot_id, user_id)).fetchone()
        if not lot:
            raise TradeError('Лот не найден!')
        item_id, item_type, price = lot
        _change_item(conn, user_id, item_id, item_type, 1)
        refund = get_listing_fee(price) // 2
        conn.execute('DELETE FROM trading_post WHERE lot_id=?', (lot_id,))
        conn.execute('UPDATE users SET gold=gold+? WHERE user_id=?', (refund, user_id))
        return refund

def get_card_info(card_id: str):
    with get_connection() as conn:
        r = conn.cursor().execute("SELECT name, emoji, rarity_internal FROM cards WHERE card_id=?", (card_id,)).fetchone()
        if r: return {"name": f"{r[1]} {r[0]}", "rarity": r[2]}
    return None
    
def get_box_info(box_id: str):
    with get_connection() as conn:
        r = conn.cursor().execute("SELECT name, rarity FROM loot_boxes WHERE box_id=?", (box_id,)).fetchone()
        if r: return {"name": r[0], "rarity": r[1]}
    return None

def get_tp_limits(item_id: str, item_type: str):
    if item_type == 'card':
        info = get_card_info(item_id)
        r = info['rarity'] if info else 'common'
        min_p = {"common": 50, "uncommon": 150, "rare": 500, "epic": 2000, "legendary": 10000}.get(r, 50)
        return min_p, min_p * 5
    elif item_type == 'box':
        info = get_box_info(item_id)
        bp = 500 if info and info['rarity'] == 'epic' else 200
        return max(1, int(bp * 0.5)), max(1, int(bp * 3.0))
    else:
        bp = get_item_price(item_id)
        return int(bp * 0.5), int(bp * 3.0)

# --- ГЛАВНОЕ МЕНЮ ТП ---
async def render_tp_main(callback: CallbackQuery):
    """Рисует главное меню барахолки. Без FSM — можно вызывать из любых хендлеров."""
    user = get_user(callback.from_user.id)
    text = (
        "📢 **Барахолка Камарии**\n\n"
        "Свободный рынок, где игроки торгуют напрямую. Никаких аукционов и таймеров — цена фиксирована.\n\n"
        f"💰 Золото: **{user['gold']}** 🪙\n"
        "Что вас интересует?"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Поиск товаров", callback_data="tp_search")],
        [InlineKeyboardButton(text="➕ Выставить лот", callback_data="tp_sell_cats")],
        [InlineKeyboardButton(text="📦 Мои лоты", callback_data="tp_my_lots")],
        [InlineKeyboardButton(text="🔙 Назад к NPC", callback_data="town_market")]
    ])
    update_user(user['user_id'], state='STATE_TOWN')
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data == "tp_main")
async def tp_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await render_tp_main(callback)

# --- ПОИСК (ПОКУПКА) ---
@router.callback_query(F.data == "tp_search")
async def tp_search(callback: CallbackQuery):
    text = "🔍 **Категории товаров**\nВыберите, что ищете:"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗡️ Оружие", callback_data="tp_list:weapon"), InlineKeyboardButton(text="🛡️ Броня", callback_data="tp_list:armor")],
        [InlineKeyboardButton(text="📦 Материалы", callback_data="tp_list:material"), InlineKeyboardButton(text="🎴 Карточки", callback_data="tp_list:card")],
        [InlineKeyboardButton(text="🎁 Лутбоксы", callback_data="tp_list:box")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="tp_main")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data.startswith("tp_list:"))
async def tp_list(callback: CallbackQuery):
    cat = callback.data.split(":")[1]
    user_id = callback.from_user.id
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT lot_id, item_id, price FROM trading_post WHERE item_type=? AND seller_id!=? ORDER BY price ASC LIMIT 15", (cat, user_id))
        lots = cursor.fetchall()
        
    if not lots:
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="tp_search")]])
        return await callback.message.edit_text("В этой категории пока нет товаров от других игроков.", reply_markup=kb)
        
    cat_names = {"weapon": "Оружие", "armor": "Броня", "material": "Материалы", "card": "Карты", "box": "Лутбоксы"}
    text = f"🛒 **Рынок: {cat_names.get(cat)}**\n*(Отображаются 15 самых дешевых лотов)*\n\n"
    buttons = []
    
    for lot_id, item_id, price in lots:
        name = get_item_name(item_id)
        buttons.append([InlineKeyboardButton(text=f"{name} — {price} 🪙", callback_data=f"tp_buy_info:{lot_id}")])
        
    buttons.append([InlineKeyboardButton(text="🔙 К категориям", callback_data="tp_search")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data.startswith("tp_buy_info:"))
async def tp_buy_info(callback: CallbackQuery):
    lot_id = callback.data.split(":")[1]
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT item_id, item_type, price, seller_id FROM trading_post WHERE lot_id=?", (lot_id,))
        lot = cursor.fetchone()
        
    if not lot: return await callback.answer("Этот лот уже выкуплен или снят с продажи!", show_alert=True)
    item_id, item_type, price, seller_id = lot
    name = get_item_name(item_id)
    
    text = f"🛒 **Покупка лота**\n\nПредмет: **{name}**\nЦена: **{price} 🪙**\nПродавец мгновенно получит золото."
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Купить за {price} 🪙", callback_data=f"tp_buy_do:{lot_id}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="tp_search")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data.startswith("tp_buy_do:"))
async def tp_buy_do(callback: CallbackQuery):
    lot_id = callback.data.split(":")[1]
    buyer_id = callback.from_user.id
    try:
        item_id, price, seller_id, seller_profit = _buy_lot(lot_id, buyer_id)
    except TradeError as exc:
        return await callback.answer(str(exc), show_alert=True)

    name = get_item_name(item_id)

    # --- ОТПРАВКА УВЕДОМЛЕНИЯ ПРОДАВЦУ ---
    try:
        notify_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Скрыть", callback_data="hide_notification")]])
        await callback.bot.send_message(
            chat_id=seller_id,
            text=f"💰 **Барахолка: Успешная продажа!**\nВаш лот **{name}** был приобретен за {price} 🪙.\n*(С учетом комиссии площадки вы получили {seller_profit} 🪙)*",
            reply_markup=notify_kb,
            parse_mode="Markdown"
        )
    except Exception:
        pass # Игрок мог заблокировать бота
        
    await callback.answer(f"🎉 Успешно куплено за {price} 🪙!", show_alert=True)
    await render_tp_main(callback)

# --- ПРОДАЖА (ВЫСТАВЛЕНИЕ) ---
@router.callback_query(F.data == "tp_sell_cats")
async def tp_sell_cats(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    max_slots = min(10, 5 + (user.get('level', 1) // 10))
    with get_connection() as conn:
        active_lots = conn.cursor().execute("SELECT COUNT(*) FROM trading_post WHERE seller_id=?", (user['user_id'],)).fetchone()[0]
        
    if active_lots >= max_slots:
        return await callback.answer(f"Достигнут лимит слотов ({max_slots})!", show_alert=True)
        
    text = "➕ **Выставить на продажу**\nВыберите категорию из инвентаря:"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎒 Снаряжение", callback_data="tp_sell_list:equip"), InlineKeyboardButton(text="📦 Ресурсы", callback_data="tp_sell_list:mat")],
        [InlineKeyboardButton(text="🎴 Карточки", callback_data="tp_sell_list:card"), InlineKeyboardButton(text="🎁 Лутбоксы", callback_data="tp_sell_list:box")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="tp_main")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data.startswith("tp_sell_list:"))
async def tp_sell_list(callback: CallbackQuery):
    cat = callback.data.split(":")[1]
    user = get_user(callback.from_user.id)
    inv = user.get('inventory', {})
    buttons = []
    
    if cat == "equip":
        counts = Counter(inv.get("backpack", []))
        for i_id, count in counts.items():
            it = get_item(i_id)
            if not it or it.get('stats', {}).get('req_lvl', 1) < 5: continue # Блокируем common (req_lvl < 5)
            buttons.append([InlineKeyboardButton(text=f"{it['name']} (x{count})", callback_data=f"tp_sell_setup:{i_id}:{it['type']}")])
            
    elif cat == "mat":
        for i_id, count in inv.get("materials", {}).items():
            if count > 0: buttons.append([InlineKeyboardButton(text=f"{get_item_name(i_id)} (x{count})", callback_data=f"tp_sell_setup:{i_id}:material")])
            
    elif cat == "card":
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT card_id, count FROM user_cards WHERE user_id=? AND count>0", (user['user_id'],))
            for c_id, count in cur.fetchall():
                buttons.append([InlineKeyboardButton(text=f"{get_item_name(c_id)} (x{count})", callback_data=f"tp_sell_setup:{c_id}:card")])
                
    elif cat == "box":
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT box_id, count FROM user_boxes WHERE user_id=? AND count>0", (user['user_id'],))
            for b_id, count in cur.fetchall():
                buttons.append([InlineKeyboardButton(text=f"{get_item_name(b_id)} (x{count})", callback_data=f"tp_sell_setup:{b_id}:box")])

    if not buttons:
        return await callback.answer("У вас нет подходящих предметов в этой категории!", show_alert=True)
        
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="tp_sell_cats")])
    await callback.message.edit_text("➕ **Выберите предмет для продажи:**", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@router.callback_query(F.data.startswith("tp_sell_setup:"))
async def tp_sell_setup(callback: CallbackQuery, state: FSMContext):
    _, item_id, item_type = callback.data.split(":")
    if item_type in ('weapon', 'armor'):
        item = get_item(item_id)
        if not item or item['type'] != item_type or item.get('stats', {}).get('req_lvl', 1) < 5:
            return await callback.answer("Этот предмет нельзя выставить!", show_alert=True)
    elif item_type not in ('material', 'card', 'box'):
        return await callback.answer("Этот предмет нельзя выставить!", show_alert=True)
    min_p, max_p = get_tp_limits(item_id, item_type)
    
    await state.set_state(TPState.waiting_price)
    await state.update_data(item_id=item_id, item_type=item_type, min_p=min_p, max_p=max_p)
    update_user(callback.from_user.id, state='STATE_FSM')
    
    name = get_item_name(item_id)
    text = (
        f"➕ **Выставление лота:** {name}\n\n"
        f"Допустимый диапазон цены: от **{min_p}** до **{max_p}** 🪙\n\n"
        "💬 **Отправьте цену сообщением в чат.**\n*(Налог за выставление: 3% от цены, мин 1 🪙)*"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="tp_main")]])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

@router.message(TPState.waiting_price)
async def process_tp_price(message: Message, state: FSMContext):
    if not message.text or not message.text.isdigit():
        return await message.answer("⚠️ Пожалуйста, введите число.")
        
    price = int(message.text)
    data = await state.get_data()
    min_p, max_p = data['min_p'], data['max_p']
    
    if price < min_p or price > max_p:
        return await message.answer(f"⚠️ Цена вне диапазона! Введите от {min_p} до {max_p}.")
        
    user_id = message.from_user.id
    item_id, item_type = data['item_id'], data['item_type']
    try:
        fee = _create_lot(user_id, item_id, item_type, price)
    except TradeError as exc:
        await state.clear()
        update_user(user_id, state='STATE_TOWN')
        return await message.answer(f"❌ {exc}")

    await state.clear()
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="В Барахолку", callback_data="tp_main")]])
    msg = await message.answer(f"✅ Лот **{get_item_name(item_id)}** успешно выставлен за **{price} 🪙**!\nСбор площадки: -{fee} 🪙.", reply_markup=kb, parse_mode="Markdown")
    update_user(user_id, last_msg_id=msg.message_id)

# --- МОИ ЛОТЫ И СНЯТИЕ ---
@router.callback_query(F.data == "tp_my_lots")
async def tp_my_lots(callback: CallbackQuery):
    user_id = callback.from_user.id
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT lot_id, item_id, price FROM trading_post WHERE seller_id=?", (user_id,))
        lots = cursor.fetchall()
        
    if not lots:
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="tp_main")]])
        return await callback.message.edit_text("У вас нет активных лотов.", reply_markup=kb)
        
    text = "📦 **Ваши лоты на продажу:**\nНажмите для снятия лота (возвращается 50% сбора площадки).\n"
    buttons = []
    for lot_id, item_id, price in lots:
        buttons.append([InlineKeyboardButton(text=f"❌ Снять: {get_item_name(item_id)} ({price} 🪙)", callback_data=f"tp_cancel:{lot_id}")])
        
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="tp_main")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data.startswith("tp_cancel:"))
async def tp_cancel(callback: CallbackQuery):
    lot_id = callback.data.split(":")[1]
    user_id = callback.from_user.id
    
    try:
        refund = _cancel_lot(lot_id, user_id)
    except TradeError as exc:
        return await callback.answer(str(exc), show_alert=True)

    await callback.answer(f"Лот снят! Возмещено {refund} 🪙.", show_alert=True)
    await tp_my_lots(callback)

