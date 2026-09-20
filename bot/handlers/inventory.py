from collections import Counter
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database import get_user, update_user, get_item, get_item_name

router = Router()

@router.callback_query(F.data == "inv_open")
async def open_inventory(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    inv = user['inventory']
    equipment = inv.get("equipment", {})
    
    weapon_data = get_item(equipment.get("weapon")) if equipment.get("weapon") else None
    armor_data = get_item(equipment.get("armor")) if equipment.get("armor") else None
    
    base_dmg = 5 + (user.get('level', 1) * 2)
    total_dmg = base_dmg + (weapon_data['stats'].get('dmg', 0) if weapon_data else 0)
    total_def = armor_data['stats'].get('def', 0) if armor_data else 0
    
    w_name = weapon_data['name'] if weapon_data else "Кулаки"
    w_range = "🏹 Дальний" if weapon_data and weapon_data['stats'].get('range') == 'ranged' else "🗡 Ближний"
    a_name = armor_data['name'] if armor_data else "Лохмотья"
    
    safe_username = user['username'].replace('_', '\\_') if user['username'] else "Герой"
    xp_needed = user.get('level', 1) * 100
    
    text = (f"🎒 **Инвентарь ({safe_username})** | Уровень {user.get('level', 1)}\n"
            f"✨ Опыт: {user.get('xp', 0)} / {xp_needed}\n"
            f"💰 Золото: {user['gold']}\n\n"
            f"Оружие: **{w_name}** ({w_range})\nБроня: **{a_name}**\n\n"
            f"📊 Урон: {total_dmg} | Защита: {total_def} | ХП: {user['hp']}/{user['max_hp']}\n\n"
            f"🧪 **Расходники:**\n")
            
    potions = inv.get("potions", [])
    if potions:
        for p_name, count in Counter(potions).items():
            text += f" • {p_name} (x{count})\n"
    else: text += " • Пусто\n"
    
    materials = inv.get("materials", {})
    if materials:
        text += "\n📦 **Материалы:**\n"
        for m_id, count in materials.items():
            text += f" • {get_item_name(m_id)}: {count} шт.\n"
            
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗡 Оружие", callback_data="inv_act_equip"), InlineKeyboardButton(text="🛡 Броня", callback_data="inv_act_equip_armor")],
        [InlineKeyboardButton(text="🧪 Выпить зелье", callback_data="inv_act_drink")],
        [InlineKeyboardButton(text="🔙 В лагерь", callback_data="town_back")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data == "inv_act_equip")
async def show_equip_weapon(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    backpack = user['inventory'].get("backpack", [])
    buttons = [[InlineKeyboardButton(text=f"🗡 {get_item(w)['name']}", callback_data=f"equip_w_{w}")] for w in set(backpack) if get_item(w) and get_item(w)['type'] == 'weapon']
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="inv_open")])
    await callback.message.edit_text("🗡 **Смена оружия**" if len(buttons)>1 else "У вас нет запасного оружия.", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data == "inv_act_equip_armor")
async def show_equip_armor(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    backpack = user['inventory'].get("backpack", [])
    buttons = [[InlineKeyboardButton(text=f"🛡 {get_item(a)['name']}", callback_data=f"equip_a_{a}")] for a in set(backpack) if get_item(a) and get_item(a)['type'] == 'armor']
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="inv_open")])
    await callback.message.edit_text("🛡 **Смена брони**" if len(buttons)>1 else "У вас нет запасной брони.", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data.startswith("equip_w_"))
async def equip_weapon(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    w_id = callback.data.replace("equip_w_", "")
    inv = user['inventory']
    if w_id in inv.get("backpack", []):
        if inv.get("equipment", {}).get("weapon"): inv["backpack"].append(inv["equipment"]["weapon"])
        inv["backpack"].remove(w_id)
        inv.setdefault("equipment", {})["weapon"] = w_id
        update_user(user['user_id'], inventory=inv)
        await callback.answer("Оружие экипировано!")
    await open_inventory(callback)

@router.callback_query(F.data.startswith("equip_a_"))
async def equip_armor(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    a_id = callback.data.replace("equip_a_", "")
    inv = user['inventory']
    if a_id in inv.get("backpack", []):
        if inv.get("equipment", {}).get("armor"): inv["backpack"].append(inv["equipment"]["armor"])
        inv["backpack"].remove(a_id)
        inv.setdefault("equipment", {})["armor"] = a_id
        update_user(user['user_id'], inventory=inv)
        await callback.answer("Броня экипирована!")
    await open_inventory(callback)

@router.callback_query(F.data == "inv_act_drink")
async def drink_potion_menu(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    potions = list(set(user['inventory'].get("potions", [])))
    buttons = [[InlineKeyboardButton(text=f"Выпить: {p}", callback_data=f"drink_p_{i}")] for i, p in enumerate(potions)]
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="inv_open")])
    await callback.message.edit_text("🧪 **Аптечка**\nВыберите зелье:" if potions else "У вас нет зелий.", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data.startswith("drink_p_"))
async def execute_drink(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    idx = int(callback.data.replace("drink_p_", ""))
    unique_potions = list(set(user['inventory'].get("potions", [])))
    
    if idx < len(unique_potions):
        p_name = unique_potions[idx]
        p_lower = p_name.lower()
        
        # ЗАЩИТА: Вне боя можно пить только хилки
        if "рагу" in p_lower or "хил" in p_lower or "реген хп" in p_lower:
            user['inventory']["potions"].remove(p_name)
            heal = int(user['max_hp'] * 0.35) if "рагу" in p_lower else int(user['max_hp'] * 0.25)
            new_hp = min(user['max_hp'], user['hp'] + heal)
            update_user(user['user_id'], hp=new_hp, inventory=user['inventory'])
            await callback.answer(f"Восстановлено {heal} ХП!", show_alert=True)
        else:
            await callback.answer("Это зелье нужно использовать во время боя!", show_alert=True)
            
    await open_inventory(callback)
