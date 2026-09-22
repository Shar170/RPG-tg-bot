from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database import get_user, update_user, get_item, get_item_name

router = Router()

def get_weapon_icon(item_data: dict) -> str:
    if not item_data: return "🗡️"
    stats = item_data.get('stats', {})
    if stats.get('range') == 'ranged':
        return "🪄" if "посох" in item_data.get('name', '').lower() else "🏹"
    return "🗡️"

@router.callback_query(F.data == "inv_open")
async def open_inventory(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    inv = user['inventory']
    eq = inv.get("equipment", {})
    
    weapon_item = get_item(eq.get('weapon'))
    armor_item = get_item(eq.get('armor'))
    
    w_name = weapon_item['name'] if weapon_item else "Кулаки"
    w_icon = get_weapon_icon(weapon_item)
    a_name = armor_item['name'] if armor_item else "Лохмотья"
    
    text = (
        f"🎒 **Инвентарь Героя: {user['username']}**\n"
        f"Уровень: **{user.get('level', 1)}** | Золото: **{user['gold']}** 🪙 | Алмазы: **{user.get('gems', 0)}** 💎\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"**Экипировано:**\n"
        f"{w_icon} Оружие: **{w_name}**\n"
        f"🛡️ Броня: **{a_name}**\n"
        f"━━━━━━━━━━━━━━━━━━\n"
    )
    
    backpack = inv.get("backpack", [])
    if backpack:
        text += "**Рюкзак (Запасная экипировка):**\n"
        for item_id in backpack:
            it = get_item(item_id)
            if it:
                icon = get_weapon_icon(it) if it['type'] == 'weapon' else "🛡️"
                req_lvl = it.get('stats', {}).get('req_lvl', 1)
                text += f" • {icon} {it['name']} (Требуется ур. {req_lvl})\n"
    else:
        text += "*Рюкзак пуст.*\n"
        
    potions = inv.get("potions", [])
    if potions:
        text += f"\n🧪 Зелий в сумке: **{len(potions)} шт.**\n"
        
    materials = inv.get("materials", {})
    if materials:
        text += f"📦 Ресурсов: **{sum(materials.values())} шт.**\n"
        
    buttons = []
    if backpack:
        buttons.append([InlineKeyboardButton(text="🔄 Сменить экипировку", callback_data="inv_equip_menu")])
    buttons.append([InlineKeyboardButton(text="🔙 В лагерь", callback_data="town_back")])
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data == "inv_equip_menu")
async def equip_selection_menu(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    backpack = user['inventory'].get("backpack", [])
    
    if not backpack:
        return await callback.answer("В рюкзаке ничего нет!", show_alert=True)
        
    buttons = []
    for item_id in list(set(backpack)):
        it = get_item(item_id)
        if it:
            icon = get_weapon_icon(it) if it['type'] == 'weapon' else "🛡️"
            req_lvl = it.get('stats', {}).get('req_lvl', 1)
            buttons.append([InlineKeyboardButton(
                text=f"{icon} Надеть: {it['name']} (Ур. {req_lvl})", 
                callback_data=f"inv_puton_{item_id}"
            )])
            
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="inv_open")])
    await callback.message.edit_text("⚙️ **Выберите предмет для экипировки:**", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data.startswith("inv_puton_"))
async def equip_item(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    item_id = callback.data.replace("inv_puton_", "")
    
    inv = user['inventory']
    backpack = inv.get("backpack", [])
    eq = inv.get("equipment", {})
    
    if item_id not in backpack:
        return await callback.answer("Предмет не найден!", show_alert=True)
        
    it = get_item(item_id)
    if not it:
        return await callback.answer("Ошибка данных предмета!", show_alert=True)
        
    # ПРОВЕРКА ТРЕБОВАНИЯ ПО УРОВНЮ
    req_lvl = it.get('stats', {}).get('req_lvl', 1)
    if user.get('level', 1) < req_lvl:
        return await callback.answer(f"⛔ Недостаточный уровень! Требуется {req_lvl} ур. (у вас {user.get('level', 1)})", show_alert=True)
        
    slot = "weapon" if it['type'] == "weapon" else "armor"
    old_equipped = eq.get(slot)
    
    backpack.remove(item_id)
    if old_equipped:
        backpack.append(old_equipped)
        
    eq[slot] = item_id
    inv["equipment"] = eq
    inv["backpack"] = backpack
    
    update_user(user['user_id'], inventory=inv)
    await callback.answer(f"Экипировано: {it['name']}!")
    await open_inventory(callback)
