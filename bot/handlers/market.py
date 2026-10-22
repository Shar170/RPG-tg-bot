import json
from collections import Counter
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database import get_user, update_user, get_item, get_item_name, get_item_price, get_connection, get_clan, log_event
from data.item_names import item_display_name
from i18n import t

router = Router()

def _rate_text(is_max_clan: bool) -> str:
    return t("market.rate.full") if is_max_clan else t("market.rate.half")

def get_market_items(item_type: str):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT item_id, name, base_price, stats FROM items WHERE type = ? AND base_price > 0", (item_type,))
        return [{"item_id": r[0], "name": item_display_name(r[0], r[1]), "price": r[2], "stats": json.loads(r[3])} for r in cur.fetchall()]

@router.callback_query(F.data == "town_market")
async def open_market(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    clan = get_clan(user.get('clan_id', 0))
    is_max_clan = clan and clan.get('level', 1) >= 20
    
    text = (
        t("market.title")
        + t("market.gold", gold=user['gold'])
        + t("market.intro")
    )
    if is_max_clan:
        text += t("market.discount")

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("market.btn.flea"), callback_data="tp_main")],
        [InlineKeyboardButton(text=t("market.btn.sell_all"), callback_data="market_sell_all_loot")],
        [InlineKeyboardButton(text=t("market.btn.buy_potions"), callback_data="market_buy_consumable")],
        [InlineKeyboardButton(text=t("market.btn.buy_weapons"), callback_data="market_buy_weapon"),
         InlineKeyboardButton(text=t("market.btn.buy_armor"), callback_data="market_buy_armor")],
        [InlineKeyboardButton(text=t("market.btn.sell_loot"), callback_data="market_sell_loot"),
         InlineKeyboardButton(text=t("market.btn.sell_equip"), callback_data="market_sell_equip")],
        [InlineKeyboardButton(text=t("market.btn.back_town"), callback_data="town_back")]
    ])
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    except: pass

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
    
    for m_id, count in list(mats.items()):
        if count > 0:
            profit += int(get_item_price(m_id) * rate) * count
            count_sold += count
            del mats[m_id]
            
    new_bp = []
    for i_id in backpack:
        it = get_item(i_id)
        if not it:
            new_bp.append(i_id)
            continue
            
        sell = False
        if it['type'] == 'weapon' and it['stats'].get('dmg', 0) < curr_dmg: sell = True
        elif it['type'] == 'armor' and it['stats'].get('def', 0) < curr_def: sell = True
        # Не-снаряжение не продаётся здесь: оно остаётся в рюкзаке (см. ветку else ниже)
        
        if sell:
            profit += int(it['base_price'] * rate)
            count_sold += 1
        else:
            new_bp.append(i_id)
            
    if count_sold == 0:
        return await callback.answer(t("market.sell_all.none"), show_alert=True)
        
    inv['materials'] = mats
    inv['backpack'] = new_bp
    user['gold'] += profit
    update_user(user['user_id'], gold=user['gold'], inventory=inv)
    
    log_event(user['user_id'], 'economy', 'market_sell_all', profit, {'items_sold': count_sold})
    
    await callback.answer(t("market.sell_all.success", count=count_sold, profit=profit), show_alert=True)
    await open_market(callback)

@router.callback_query(F.data == "market_buy_weapon")
async def market_buy_weapon(callback: CallbackQuery):
    text = t("market.weapon.title")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("market.weapon.melee_low"), callback_data="market_list:weapon:melee:1:20")],
        [InlineKeyboardButton(text=t("market.weapon.melee_high"), callback_data="market_list:weapon:melee:21:99")],
        [InlineKeyboardButton(text=t("market.weapon.ranged_low"), callback_data="market_list:weapon:ranged:1:20")],
        [InlineKeyboardButton(text=t("market.weapon.ranged_high"), callback_data="market_list:weapon:ranged:21:99")],
        [InlineKeyboardButton(text=t("market.btn.back_market"), callback_data="town_market")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data == "market_buy_armor")
async def market_buy_armor(callback: CallbackQuery):
    text = t("market.armor.title")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("market.armor.light"), callback_data="market_list:armor:all:1:20")],
        [InlineKeyboardButton(text=t("market.armor.heavy"), callback_data="market_list:armor:all:21:99")],
        [InlineKeyboardButton(text=t("market.btn.back_market"), callback_data="town_market")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data == "market_buy_consumable")
async def market_buy_consumable(callback: CallbackQuery):
    await market_list_items(callback, "consumable", "all", 0, 99)

@router.callback_query(F.data.startswith("market_list:"))
async def market_list_router(callback: CallbackQuery):
    _, cat, subcat, min_lvl, max_lvl = callback.data.split(":")
    await market_list_items(callback, cat, subcat, int(min_lvl), int(max_lvl))

async def market_list_items(callback: CallbackQuery, category: str, subcat: str, min_lvl: int, max_lvl: int):
    user = get_user(callback.from_user.id)
    clan = get_clan(user.get('clan_id', 0))
    is_max_clan = clan and clan.get('level', 1) >= 20
    
    items = get_market_items(category)
    if not items: return await callback.answer(t("market.no_items_category"), show_alert=True)
    
    filtered_items = []
    for item in items:
        req_lvl = int(item['stats'].get('req_lvl', 1))
        rng = item['stats'].get('range', 'all')
        
        if min_lvl <= req_lvl <= max_lvl:
            if subcat == 'all' or rng == subcat:
                filtered_items.append(item)
                
    if not filtered_items:
        return await callback.answer(t("market.no_items_filter"), show_alert=True)
        
    cat_names = {
        "consumable": t("market.cat.consumable"),
        "weapon": t("market.cat.weapon"),
        "armor": t("market.cat.armor"),
    }
    category_name = cat_names.get(category, t("market.cat.other"))
    text = t("market.list.title", category=category_name, gold=user['gold'])
    
    buttons = []
    for item in filtered_items:
        stats_str = ""
        req_lvl = int(item['stats'].get('req_lvl', 1))
        lvl_str = t("market.level_short", level=req_lvl) if req_lvl > 1 else ""
        
        if category == "weapon" and "dmg" in item["stats"]: stats_str = f" (⚔️ {item['stats']['dmg']})"
        elif category == "armor" and "def" in item["stats"]: stats_str = f" (🛡️ {item['stats']['def']})"
            
        display_price = max(1, int(item['price'] * 0.7)) if is_max_clan else item['price']
        
        cb_data = f"mbuy:{item['item_id']}:{subcat}:{min_lvl}:{max_lvl}"
        buttons.append([InlineKeyboardButton(text=f"{item['name']}{lvl_str}{stats_str} — {display_price} 🪙", callback_data=cb_data)])
        
    if category == "weapon": back_cb = "market_buy_weapon"
    elif category == "armor": back_cb = "market_buy_armor"
    else: back_cb = "town_market"
    
    buttons.append([InlineKeyboardButton(text=t("market.btn.back"), callback_data=back_cb)])
    
    try:
        await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")
    except Exception:
        pass 

@router.callback_query(F.data.startswith("mbuy:"))
async def market_buy_execute(callback: CallbackQuery):
    parts = callback.data.split(":")
    item_id = parts[1]
    subcat = parts[2]
    min_lvl = int(parts[3])
    max_lvl = int(parts[4])
    
    user = get_user(callback.from_user.id)
    item = get_item(item_id)
    if not item: return await callback.answer(t("market.buy.not_found"), show_alert=True)
        
    clan = get_clan(user.get('clan_id', 0))
    is_max_clan = clan and clan.get('level', 1) >= 20
    price = max(1, int(item['base_price'] * 0.7)) if is_max_clan else item['base_price']
    
    if user['gold'] < price: return await callback.answer(t("market.buy.no_gold"), show_alert=True)
        
    user['gold'] -= price
    inv = user['inventory']
    
    # ИСПРАВЛЕНИЕ: Теперь мы сохраняем технический item_id, а не русское название!
    if item['type'] in ["weapon", "armor"]: inv.setdefault("backpack", []).append(item_id)
    elif item['type'] == "consumable": inv.setdefault("potions", []).append(item_id)
    else: inv.setdefault("materials", {})[item_id] = inv.get("materials", {}).get(item_id, 0) + 1
        
    update_user(user['user_id'], gold=user['gold'], inventory=inv)
    
    log_event(user['user_id'], 'economy', 'market_buy', -price, {'item_id': item_id, 'category': item['type']})
    
    await callback.answer(t("market.buy.success", item=item['name'], price=price), show_alert=True)
    await market_list_items(callback, item['type'], subcat, min_lvl, max_lvl)

@router.callback_query(F.data == "market_sell_loot")
async def market_sell_loot(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    clan = get_clan(user.get('clan_id', 0))
    is_max_clan = clan and clan.get('level', 1) >= 20
    materials = user['inventory'].get("materials", {})
    
    if not materials:
        return await callback.message.edit_text(
            t("market.sell_loot.empty"),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t("market.btn.back"), callback_data="town_market")]]),
            parse_mode="Markdown",
        )
        
    rate_text = _rate_text(is_max_clan)
    text = t("market.sell_loot.title", gold=user['gold'], rate=rate_text)
    buttons = []
    
    for mat_id, count in sorted(materials.items()):
        if count > 0:
            name = get_item_name(mat_id)
            price = get_item_price(mat_id)
            if not is_max_clan: price = max(1, price // 2)
            buttons.append([InlineKeyboardButton(text=t("market.price_per_piece", name=name, count=count, price=price), callback_data=f"market_sell_loot_item:{mat_id}")])
            
    buttons.append([InlineKeyboardButton(text=t("market.sell_loot.back"), callback_data="town_market")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data.startswith("market_sell_loot_item:"))
async def market_sell_loot_item(callback: CallbackQuery):
    mat_id = callback.data.replace("market_sell_loot_item:", "")
    user = get_user(callback.from_user.id)
    clan = get_clan(user.get('clan_id', 0))
    is_max_clan = clan and clan.get('level', 1) >= 20
    count = user['inventory'].get("materials", {}).get(mat_id, 0)
    
    if count <= 0: return await callback.answer(t("market.sell_resource.gone"), show_alert=True)
        
    name = get_item_name(mat_id)
    price_per_one = get_item_price(mat_id)
    if not is_max_clan: price_per_one = max(1, price_per_one // 2)
    
    text = t("market.sell_resource.title", item=name, count=count, price=price_per_one)
    buttons = [[InlineKeyboardButton(text=t("market.sell_resource.one", price=price_per_one), callback_data=f"market_sell_loot_do:{mat_id}:1")]]
    if count >= 5: buttons.append([InlineKeyboardButton(text=t("market.sell_resource.five", price=price_per_one * 5), callback_data=f"market_sell_loot_do:{mat_id}:5")])
    if count > 1: buttons.append([InlineKeyboardButton(text=t("market.sell_resource.all", count=count, price=price_per_one * count), callback_data=f"market_sell_loot_do:{mat_id}:{count}")])
        
    buttons.append([InlineKeyboardButton(text=t("market.sell_resource.back_list"), callback_data="market_sell_loot")])
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
    if materials.get(mat_id, 0) < amount: return await callback.answer(t("market.sell_resource.not_enough"), show_alert=True)
        
    price_per_one = max(1, get_item_price(mat_id) // 2) if not is_max_clan else get_item_price(mat_id)
    total_profit = price_per_one * amount
    
    materials[mat_id] -= amount
    if materials[mat_id] <= 0: del materials[mat_id]
        
    user['gold'] += total_profit
    inv['materials'] = materials
    update_user(user['user_id'], gold=user['gold'], inventory=inv)
    
    log_event(user['user_id'], 'economy', 'market_sell_item', total_profit, {'item_id': mat_id, 'amount': amount})
    
    await callback.answer(t("market.sell_resource.success", count=amount, profit=total_profit), show_alert=True)
    await market_sell_loot(callback)

@router.callback_query(F.data == "market_sell_equip")
async def market_sell_equip(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    clan = get_clan(user.get('clan_id', 0))
    is_max_clan = clan and clan.get('level', 1) >= 20
    backpack = user['inventory'].get("backpack", [])
    
    if not backpack:
        return await callback.message.edit_text(
            t("market.sell_equip.empty"),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t("market.btn.back"), callback_data="town_market")]]),
            parse_mode="Markdown",
        )
        
    rate_text = _rate_text(is_max_clan)
    text = t("market.sell_equip.title", gold=user['gold'], rate=rate_text)
    buttons = []
    
    counts = Counter(backpack)
    for item_id, count in counts.items():
        item_data = get_item(item_id)
        if not item_data: continue
        price = max(1, item_data['base_price'] // 2) if not is_max_clan else item_data['base_price']
        buttons.append([InlineKeyboardButton(text=t("market.sell_equip.line", name=item_data['name'], count=count, price=price), callback_data=f"market_sell_equip_do:{item_id}")])
        
    buttons.append([InlineKeyboardButton(text=t("market.sell_loot.back"), callback_data="town_market")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data.startswith("market_sell_equip_do:"))
async def market_sell_equip_do(callback: CallbackQuery):
    item_id = callback.data.replace("market_sell_equip_do:", "")
    user = get_user(callback.from_user.id)
    clan = get_clan(user.get('clan_id', 0))
    is_max_clan = clan and clan.get('level', 1) >= 20
    
    inv = user['inventory']
    backpack = inv.get("backpack", [])
    if item_id not in backpack: return await callback.answer(t("market.sell_equip.gone"), show_alert=True)
        
    item_data = get_item(item_id)
    price = max(1, item_data['base_price'] // 2) if not is_max_clan else item_data['base_price']
    
    backpack.remove(item_id)
    user['gold'] += price
    inv['backpack'] = backpack
    
    update_user(user['user_id'], gold=user['gold'], inventory=inv)
    
    log_event(user['user_id'], 'economy', 'market_sell_equip', price, {'item_id': item_id})
    
    await callback.answer(t("market.sell_equip.success", item=item_data['name'], price=price), show_alert=True)
    await market_sell_equip(callback)

