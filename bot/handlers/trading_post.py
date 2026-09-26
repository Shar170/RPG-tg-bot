import time
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
        return int(bp * 0.5), int(bp * 3.0)
    else:
        bp = get_item_price(item_id)
        return int(bp * 0.5), int(bp * 3.0)

# --- ГЛАВНОЕ МЕНЮ ТП ---
@router.callback_query(F.data == "tp_main")
async def tp_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
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
    buyer = get_user(buyer_id)
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT item_id, item_type, price, seller_id FROM trading_post WHERE lot_id=?", (lot_id,))
        lot = cursor.fetchone()
        
        if not lot: return await callback.answer("Лот больше не доступен!", show_alert=True)
        item_id, item_type, price, seller_id = lot
        
        if buyer['gold'] < price: return await callback.answer("Недостаточно золота!", show_alert=True)
            
        # Удаляем лот (блокируем двойную покупку)
        cursor.execute("DELETE FROM trading_post WHERE lot_id=?", (lot_id,))
        
        # Налоги
        tax = get_tp_tax(price)
        seller_profit = price - tax
        
        # Обновляем золото
        cursor.execute("UPDATE users SET gold = gold - ? WHERE user_id = ?", (price, buyer_id))
        cursor.execute("UPDATE users SET gold = gold + ? WHERE user_id = ?", (seller_profit, seller_id))
        
        # Лог сделки
        cursor.execute("INSERT INTO tp_history (seller_id, buyer_id, item_id, price, tax_paid, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                       (seller_id, buyer_id, item_id, price, tax, time.time()))
        conn.commit()
        
    give_item(buyer_id, item_id, item_type, 1)
    await callback.answer(f"🎉 Успешно куплено за {price} 🪙!", show_alert=True)
    await tp_main(callback, FSMContext(storage=None, key=None))

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
    if not message.text.isdigit():
        return await message.answer("⚠️ Пожалуйста, введите число.")
        
    price = int(message.text)
    data = await state.get_data()
    min_p, max_p = data['min_p'], data['max_p']
    
    if price < min_p or price > max_p:
        return await message.answer(f"⚠️ Цена вне диапазона! Введите от {min_p} до {max_p}.")
        
    user_id = message.from_user.id
    user = get_user(user_id)
    fee = get_listing_fee(price)
    
    if user['gold'] < fee:
        await state.clear()
        update_user(user_id, state='STATE_TOWN')
        return await message.answer(f"❌ У вас не хватает золота для оплаты сбора площадки ({fee} 🪙).")
        
    item_id, item_type = data['item_id'], data['item_type']
    
    # Изымаем предмет и налог
    if not take_item(user_id, item_id, item_type, 1):
        await state.clear()
        update_user(user_id, state='STATE_TOWN')
        return await message.answer("❌ Предмет не найден в инвентаре!")
        
    update_user(user_id, gold=user['gold'] - fee, state='STATE_TOWN')
    
    # Создаем лот
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO trading_post (seller_id, item_id, item_type, price, created_at, expires_at) VALUES (?, ?, ?, ?, ?, ?)",
                       (user_id, item_id, item_type, price, time.time(), time.time() + 86400))
        conn.commit()
        
    await state.clear()
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="В Барахолку", callback_data="tp_main")]])
    await message.answer(f"✅ Лот **{get_item_name(item_id)}** успешно выставлен за **{price} 🪙**!\nСбор площадки: -{fee} 🪙.", reply_markup=kb, parse_mode="Markdown")

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
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT item_id, item_type, price FROM trading_post WHERE lot_id=? AND seller_id=?", (lot_id, user_id))
        lot = cursor.fetchone()
        
        if not lot: return await callback.answer("Лот не найден!", show_alert=True)
        item_id, item_type, price = lot
        
        cursor.execute("DELETE FROM trading_post WHERE lot_id=?", (lot_id,))
        conn.commit()
        
    give_item(user_id, item_id, item_type, 1)
    refund = get_listing_fee(price) // 2
    if refund > 0:
        user = get_user(user_id)
        update_user(user_id, gold=user['gold'] + refund)
        
    await callback.answer(f"Лот снят! Возмещено {refund} 🪙.", show_alert=True)
    await tp_my_lots(callback)
