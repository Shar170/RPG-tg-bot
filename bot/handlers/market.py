import json
from collections import Counter
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database import get_user, update_user, get_item, get_item_name, get_item_price, get_connection, get_clan

router = Router()

def get_market_items(item_type: str):
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
        text += "\n\n🌟 *(Заметив ваш стяг, купец почтительно кивает)*: *«Для героя из столь могущественного клана у меня скидка 30% на все товары, а лут я скупаю по полной стоимости!»*"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Барахолка (ТП)", callback_data="tp_main")],
        [InlineKeyboardButton(text="🗑 Продать весь лут и старье", callback_data="market_sell_all_loot")],
        [InlineKeyboardButton(text="🧪 Купить зелья", callback_data="market_buy_consumable")],
        [InlineKeyboardButton(text="🗡️ Купить оружие", callback_data="market_buy_weapon"),
         InlineKeyboardButton(text="🛡️ Купить броню", callback_data="market_buy_armor")],
        [InlineKeyboardButton(text="💎 Продать лут вручную", callback_data="market_sell_loot"),
         InlineKeyboardButton(text="👕 Продать снаряжение", callback_data="market_sell_equip")],
        [InlineKeyboardButton(text="🔙 В лагерь", callback_data="town_back")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

# --- ПРОДАТЬ ВЕСЬ ЛУТ (НОВОЕ ТЗ) ---
@router.callback_query(F.data == "market_sell_all_loot")
async def market_sell_all_loot(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    clan = get_clan(user.get('clan_id', 0))
    is_max_clan = clan and clan.get('level', 1) >= 20
    rate = 1.0 if is_max_clan else 0.5
    
    inv = user.get('inventory', {})
    mats = inv.get("materials", {})
    backpack = inv.get("backpack", [])
    eq = inv.get("equipment", {})
    
    w_item = get_item(eq.get("weapon"))
    a_item = get_item(eq.get("armor"))
    curr_dmg = w_item['stats'].get('dmg', 0) if w_item else 0
    curr_def = a_item['stats'].get('def', 0) if a_item else 0
    
    profit = 0
    count_sold = 0
    
    # Продаем все материалы
    for m_id, count in list(mats.items()):
        if count > 0:
            profit += int(get_item_price(m_id) * rate) * count
            count_sold += count
            del mats[m_id]
            
    # Продаем старое снаряжение (хуже надетого)
    new_bp = []
    for i_id in backpack:
        it = get_item(i_id)
        if not it:
            new_bp.append(i_id)
            continue
            
        sell = False
        if it['type'] == 'weapon' and it['stats'].get('dmg', 0) < curr_dmg: sell = True
        elif it['type'] == 'armor' and it['stats'].get('def', 0) < curr_def: sell = True
        elif it['type'] not in ['weapon', 'armor']: new_bp.append(i_id) # Не продаем артефакты и квестовое
        
        if sell:
            profit += int(it['base_price'] * rate)
            count_sold += 1
        else:
            new_bp.append(i_id)
            
    if count_sold == 0:
        return await callback.answer("У вас нет старого лута или материалов для продажи.", show_alert=True)
        
    inv['materials'] = mats
    inv['backpack'] = new_bp
    user['gold'] += profit
    update_user(user['user_id'], gold=user['gold'], inventory=inv)
    
    await callback.answer(f"✅ Продано {count_sold} предметов!\nПолучено: {profit} 🪙", show_alert=True)
    await open_market(callback)

# --- РАЗДЕЛ ПОКУПКИ ---
@router.callback_query(F.data.startswith("market_buy_do:"))
async def market_buy_do(callback: CallbackQuery):
    item_id = callback.data.replace("market_buy_do:", "")
    user = get_user(callback.from_user.id)
    item = get_item(item_id)
    if not item: return await callback.answer("Товар не найден!", show_alert=True)
        
    clan = get_clan(user.get('clan_id', 0))
    is_max_clan = clan and clan.get('level', 1) >= 20
    price = max(1, int(item['base_price'] * 0.7)) if is_max_clan else item['base_price']
        
    if user['gold'] < price: return await callback.answer("Недостаточно золота!", show_alert=True)
        
    user['gold'] -= price
    inv = user['inventory']
    
    if item['type'] in ["weapon", "armor"]: inv.setdefault("backpack", []).append(item_id)
    elif item['type'] == "consumable": inv.setdefault("potions", []).append(item['name'])
    else: inv.setdefault("materials", {})[item_id] = inv.get("materials", {}).get(item_id, 0) + 1
        
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
    if not items: return await callback.answer("В этой категории пока нет товаров!", show_alert=True)
        
    cat_names = {"consumable": "Зелья и припасы", "weapon": "Оружие", "armor": "Броня"}
    text = f"🛒 **Покупка: {cat_names.get(category, 'Товары')}**\n💰 Ваше золото: {user['gold']} 🪙\n\nВыберите товар:"
    
    buttons = []
    for item in items:
        stats_str = ""
        if category == "weapon" and "dmg" in item["stats"]: stats_str = f" (⚔️ {item['stats']['dmg']})"
        elif category == "armor" and "def" in item["stats"]: stats_str = f" (🛡️ {item['stats']['def']})"
            
        display_price = max(1, int(item['price'] * 0.7)) if is_max_clan else item['price']
        buttons.append([InlineKeyboardButton(text=f"{item['name']}{stats_str} — {display_price} 🪙", callback_data=f"market_buy_do:{item['item_id']}")])
        
    buttons.append([InlineKeyboardButton(text="🔙 Назад на рынок", callback_data="town_market")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

# --- РАЗДЕЛ ПРОДАЖИ ЛУТА (ВРУЧНУЮ) ---
@router.callback_query(F.data == "market_sell_loot")
async def market_sell_loot(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    clan = get_clan(user.get('clan_id', 0))
    is_max_clan = clan and clan.get('level', 1) >= 20
    materials = user['inventory'].get("materials", {})
    
    if not materials:
        return await callback.message.edit_text("🤷 У вас нет трофеев и лута для продажи.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="town_market")]]), parse_mode="Markdown")
        
    rate_text = "**100%**" if is_max_clan else "**50%**"
    text = f"💎 **Скупка лута**\n💰 Ваше золото: {user['gold']} 🪙\n\nВыберите предмет для продажи (Торговец берет всё за {rate_text}):\n"
    buttons = []
    
    for mat_id, count in sorted(materials.items()):
        if count > 0:
            name = get_item_name(mat_id)
            price = get_item_price(mat_id)
            if not is_max_clan: price = max(1, price // 2)
            buttons.append([InlineKeyboardButton(text=f"{name} (x{count}) — {price} 🪙/шт", callback_data=f"market_sell_loot_item:{mat_id}")])
            
    buttons.append([InlineKeyboardButton(text="🔙 Назад на рынок", callback_data="town_market")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data.startswith("market_sell_loot_item:"))
async def market_sell_loot_item(callback: CallbackQuery):
    mat_id = callback.data.replace("market_sell_loot_item:", "")
    user = get_user(callback.from_user.id)
    clan = get_clan(user.get('clan_id', 0))
    is_max_clan = clan and clan.get('level', 1) >= 20
    count = user['inventory'].get("materials", {}).get(mat_id, 0)
    
    if count <= 0: return await callback.answer("Этот предмет закончился!", show_alert=True)
        
    name = get_item_name(mat_id)
    price_per_one = get_item_price(mat_id)
    if not is_max_clan: price_per_one = max(1, price_per_one // 2)
    
    text = f"💎 **Продажа ресурса**\n\nПредмет: **{name}**\nВ наличии: **{count} шт.**\nЦена скупки: **{price_per_one} 🪙 за штуку**\n\nСколько продаем?"
    buttons = [[InlineKeyboardButton(text=f"Продать 1 шт. (+{price_per_one} 🪙)", callback_data=f"market_sell_loot_do:{mat_id}:1")]]
    if count >= 5: buttons.append([InlineKeyboardButton(text=f"Продать 5 шт. (+{price_per_one * 5} 🪙)", callback_data=f"market_sell_loot_do:{mat_id}:5")])
    if count > 1: buttons.append([InlineKeyboardButton(text=f"Продать ВСЁ ({count} шт. за {price_per_one * count} 🪙)", callback_data=f"market_sell_loot_do:{mat_id}:{count}")])
        
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
    if materials.get(mat_id, 0) < amount: return await callback.answer("Недостаточно предметов для продажи!", show_alert=True)
        
    price_per_one = max(1, get_item_price(mat_id) // 2) if not is_max_clan else get_item_price(mat_id)
    total_profit = price_per_one * amount
    
    materials[mat_id] -= amount
    if materials[mat_id] <= 0: del materials[mat_id]
        
    user['gold'] += total_profit
    inv['materials'] = materials
    update_user(user['user_id'], gold=user['gold'], inventory=inv)
    await callback.answer(f"Продано {amount} шт. за {total_profit} 🪙!", show_alert=True)
    await market_sell_loot(callback)

# --- РАЗДЕЛ ПРОДАЖИ СНАРЯЖЕНИЯ (ВРУЧНУЮ) ---
@router.callback_query(F.data == "market_sell_equip")
async def market_sell_equip(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    clan = get_clan(user.get('clan_id', 0))
    is_max_clan = clan and clan.get('level', 1) >= 20
    backpack = user['inventory'].get("backpack", [])
    
    if not backpack:
        return await callback.message.edit_text("👕 У вас нет свободного снаряжения для продажи.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="town_market")]]), parse_mode="Markdown")
        
    rate_text = "**100%**" if is_max_clan else "**50%**"
    text = f"👕 **Скупка оружия и брони**\n💰 Ваше золото: {user['gold']} 🪙\n\nВыберите элемент для продажи (Скупка за {rate_text}):\n"
    buttons = []
    
    counts = Counter(backpack)
    for item_id, count in counts.items():
        item_data = get_item(item_id)
        if not item_data: continue
        price = max(1, item_data['base_price'] // 2) if not is_max_clan else item_data['base_price']
        buttons.append([InlineKeyboardButton(text=f"{item_data['name']} (x{count}) — {price} 🪙", callback_data=f"market_sell_equip_do:{item_id}")])
        
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
    if item_id not in backpack: return await callback.answer("Этого снаряжения больше нет!", show_alert=True)
        
    item_data = get_item(item_id)
    price = max(1, item_data['base_price'] // 2) if not is_max_clan else item_data['base_price']
    
    backpack.remove(item_id)
    user['gold'] += price
    inv['backpack'] = backpack
    
    update_user(user['user_id'], gold=user['gold'], inventory=inv)
    await callback.answer(f"Продано: {item_data['name']} за {price} 🪙", show_alert=True)
    await market_sell_equip(callback)

