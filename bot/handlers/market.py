import json
from collections import Counter
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database import get_user, update_user, get_item, get_item_name, get_item_price, get_connection, get_clan

router = Router()

def get_market_items(item_type: str):
    """Извлекает товары из БД по категории"""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT item_id, name, base_price, stats FROM items WHERE type = ?", (item_type,))
        return [{"item_id": r[0], "name": r[1], "price": r[2], "stats": json.loads(r[3])} for r in cur.fetchall()]


@router.callback_query(F.data == "town_market")
async def open_market(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    clan = get_clan(user.get('clan_id', 0))
    is_max_clan = clan and clan.get('level', 1) >= 20
    
    text = (
        "⚖️ **Рынок Камарии**\n\n"
        f"Ваше золото: **{user['gold']} 🪙**\n\n"
        "Торговец хитро щурится: *«Оружие, броня или целебное варево? А может, хочешь сбыть трофеи из подземелий? У меня лучшие цены!»*"
    )
    
    if is_max_clan:
        text += "\n\n🌟 *(Заметив ваш стяг, купец почтительно кивает)*: *«Для героя из столь могущественного клана у меня действует скидка 30% на все товары, а лут я скупаю по полной стоимости!»*"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧪 Купить зелья", callback_data="market_buy_consumable")],
        [InlineKeyboardButton(text="🗡️ Купить оружие", callback_data="market_buy_weapon"),
         InlineKeyboardButton(text="🛡️ Купить броню", callback_data="market_buy_armor")],
        [InlineKeyboardButton(text="💎 Продать лут", callback_data="market_sell_loot")],
        [InlineKeyboardButton(text="👕 Продать снаряжение", callback_data="market_sell_equip")],
        [InlineKeyboardButton(text="🔙 В лагерь", callback_data="town_back")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

# --- РАЗДЕЛ ПОКУПКИ ---
@router.callback_query(F.data.startswith("market_buy_do:"))
async def market_buy_do(callback: CallbackQuery):
    item_id = callback.data.replace("market_buy_do:", "")
    user = get_user(callback.from_user.id)
    item = get_item(item_id)
    
    if not item:
        return await callback.answer("Товар не найден!", show_alert=True)
        
    clan = get_clan(user.get('clan_id', 0))
    is_max_clan = clan and clan.get('level', 1) >= 20
    
    price = item['base_price']
    if is_max_clan:
        price = max(1, int(price * 0.7))
        
    if user['gold'] < price:
        return await callback.answer("Недостаточно золота!", show_alert=True)
        
    user['gold'] -= price
    inv = user['inventory']
    
    if item['type'] in ["weapon", "armor"]:
        inv.setdefault("backpack", []).append(item_id)
    elif item['type'] == "consumable":
        inv.setdefault("potions", []).append(item['name'])
    else:
        inv.setdefault("materials", {})[item_id] = inv.get("materials", {}).get(item_id, 0) + 1
        
    update_user(user['user_id'], gold=user['gold'], inventory=inv)
    await callback.answer(f"✅ Вы купили: {item['name']} за {price} 🪙", show_alert=True)
    
    callback.data = f"market_buy_{item['type']}"
    await market_buy_category(callback)

@router.callback_query(F.data.in_(["market_buy_consumable", "market_buy_weapon", "market_buy_armor"]))
async def market_buy_category(callback: CallbackQuery):
    category = callback.data.replace("market_buy_", "")
    user = get_user(callback.from_user.id)
    clan = get_clan(user.get('clan_id', 0))
    is_max_clan = clan and clan.get('level', 1) >= 20
    
    items = get_market_items(category)
    if not items:
        return await callback.answer("В этой категории пока нет товаров!", show_alert=True)
        
    cat_names = {"consumable": "Зелья и припасы", "weapon": "Оружие", "armor": "Броня"}
    text = f"🛒 **Покупка: {cat_names.get(category, 'Товары')}**\n💰 Ваше золото: {user['gold']} 🪙\n\nВыберите товар:"
    
    buttons = []
    for item in items:
        stats_str = ""
        if category == "weapon" and "dmg" in item["stats"]:
            stats_str = f" (⚔️ {item['stats']['dmg']})"
        elif category == "armor" and "def" in item["stats"]:
            stats_str = f" (🛡️ {item['stats']['def']})"
            
        display_price = item['price']
        if is_max_clan: display_price = max(1, int(display_price * 0.7))
            
        btn_text = f"{item['name']}{stats_str} — {display_price} 🪙"
        buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"market_buy_do:{item['item_id']}")])
        
    buttons.append([InlineKeyboardButton(text="🔙 Назад на рынок", callback_data="town_market")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

# --- РАЗДЕЛ ПРОДАЖИ ЛУТА ---
@router.callback_query(F.data == "market_sell_loot")
async def market_sell_loot(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    clan = get_clan(user.get('clan_id', 0))
    is_max_clan = clan and clan.get('level', 1) >= 20
    materials = user['inventory'].get("materials", {})
    
    if not materials:
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="town_market")]])
        return await callback.message.edit_text("🤷 У вас нет трофеев и лута для продажи.", reply_markup=kb, parse_mode="Markdown")
        
    rate_text = "**100%**" if is_max_clan else "**50%**"
    text = (
        f"💎 **Скупка лута**\n💰 Ваше золото: {user['gold']} 🪙\n\n"
        f"Выберите предмет для продажи (Торговец берет всё за {rate_text} от стоимости):\n"
    )
    buttons = []
    
    for mat_id, count in sorted(materials.items()):
        if count > 0:
            name = get_item_name(mat_id)
            price = get_item_price(mat_id)
            if not is_max_clan: price = max(1, price // 2)
                
            btn_text = f"{name} (x{count}) — {price} 🪙/шт"
            buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"market_sell_loot_item:{mat_id}")])
            
    buttons.append([InlineKeyboardButton(text="🔙 Назад на рынок", callback_data="town_market")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data.startswith("market_sell_loot_item:"))
async def market_sell_loot_item(callback: CallbackQuery):
    mat_id = callback.data.replace("market_sell_loot_item:", "")
    user = get_user(callback.from_user.id)
    clan = get_clan(user.get('clan_id', 0))
    is_max_clan = clan and clan.get('level', 1) >= 20
    count = user['inventory'].get("materials", {}).get(mat_id, 0)
    
    if count <= 0:
        return await callback.answer("Этот предмет закончился!", show_alert=True)
        
    name = get_item_name(mat_id)
    price_per_one = get_item_price(mat_id)
    if not is_max_clan: price_per_one = max(1, price_per_one // 2)
    
    text = (
        f"💎 **Продажа ресурса**\n\n"
        f"Предмет: **{name}**\n"
        f"В наличии: **{count} шт.**\n"
        f"Цена скупки: **{price_per_one} 🪙 за штуку**\n\n"
        "Сколько продаем?"
    )
    
    buttons = [
        [InlineKeyboardButton(text=f"Продать 1 шт. (+{price_per_one} 🪙)", callback_data=f"market_sell_loot_do:{mat_id}:1")]
    ]
    if count >= 5:
        buttons.append([InlineKeyboardButton(text=f"Продать 5 шт. (+{price_per_one * 5} 🪙)", callback_data=f"market_sell_loot_do:{mat_id}:5")])
    if count > 1:
        buttons.append([InlineKeyboardButton(text=f"Продать ВСЁ ({count} шт. за {price_per_one * count} 🪙)", callback_data=f"market_sell_loot_do:{mat_id}:{count}")])
        
    buttons.append([InlineKeyboardButton(text="🔙 Назад к списку", callback_data="market_sell_loot")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data.startswith("market_sell_loot_do:"))
async def market_sell_loot_do(callback: CallbackQuery):
    _, mat_id, amount_str = callback.data.split(":")
    amount = int(amount_str)
    user = get_user(callback.from_user.id)
    clan = get_clan(user.get('clan_id', 0))
    is_max_clan = clan and clan.get('level', 1) >= 20
    
    inv = user['inventory']
    materials = inv.get("materials", {})
    current_count = materials.get(mat_id, 0)
    
    if current_count < amount:
        return await callback.answer("Недостаточно предметов для продажи!", show_alert=True)
        
    price_per_one = get_item_price(mat_id)
    if not is_max_clan: price_per_one = max(1, price_per_one // 2)
    total_profit = price_per_one * amount
    
    materials[mat_id] -= amount
    if materials[mat_id] <= 0:
        del materials[mat_id]
        
    user['gold'] += total_profit
    inv['materials'] = materials
    
    update_user(user['user_id'], gold=user['gold'], inventory=inv)
    await callback.answer(f"Продано {amount} шт. за {total_profit} 🪙!", show_alert=True)
    await market_sell_loot(callback)

# --- РАЗДЕЛ ПРОДАЖИ СНАРЯЖЕНИЯ ---
@router.callback_query(F.data == "market_sell_equip")
async def market_sell_equip(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    clan = get_clan(user.get('clan_id', 0))
    is_max_clan = clan and clan.get('level', 1) >= 20
    backpack = user['inventory'].get("backpack", [])
    
    if not backpack:
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="town_market")]])
        return await callback.message.edit_text("👕 У вас нет свободного (не экипированного) снаряжения для продажи.", reply_markup=kb, parse_mode="Markdown")
        
    rate_text = "**100%**" if is_max_clan else "**50%**"
    text = (
        f"👕 **Скупка оружия и брони**\n💰 Ваше золото: {user['gold']} 🪙\n\n"
        f"Выберите элемент для продажи (Скупка за {rate_text}).\n"
        "*(Внимание: при нажатии продается сразу 1 шт.!)*\n"
    )
    buttons = []
    
    counts = Counter(backpack)
    for item_id, count in counts.items():
        item_data = get_item(item_id)
        if not item_data: continue
            
        name = item_data['name']
        price = item_data['base_price']
        if not is_max_clan: price = max(1, price // 2)
        
        btn_text = f"{name} (x{count}) — {price} 🪙"
        buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"market_sell_equip_do:{item_id}")])
        
    buttons.append([InlineKeyboardButton(text="🔙 Назад на рынок", callback_data="town_market")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data.startswith("market_sell_equip_do:"))
async def market_sell_equip_do(callback: CallbackQuery):
    item_id = callback.data.replace("market_sell_equip_do:", "")
    user = get_user(callback.from_user.id)
    clan = get_clan(user.get('clan_id', 0))
    is_max_clan = clan and clan.get('level', 1) >= 20
    
    inv = user['inventory']
    backpack = inv.get("backpack", [])
    
    if item_id not in backpack:
        return await callback.answer("Этого снаряжения больше нет в рюкзаке!", show_alert=True)
        
    item_data = get_item(item_id)
    if not item_data:
        return await callback.answer("Ошибка: предмет не найден в базе!", show_alert=True)
        
    price = item_data['base_price']
    if not is_max_clan: price = max(1, price // 2)
    
    backpack.remove(item_id)
    user['gold'] += price
    inv['backpack'] = backpack
    
    update_user(user['user_id'], gold=user['gold'], inventory=inv)
    await callback.answer(f"Продано: {item_data['name']} за {price} 🪙", show_alert=True)
    await market_sell_equip(callback)

