# handlers/inventory.py
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database import get_user, get_item

router = Router()

@router.callback_query(F.data == "inv_open")
async def open_inventory(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    inv = user['inventory']
    equipment = inv.get("equipment", {})
    
    weapon_id = equipment.get("weapon")
    armor_id = equipment.get("armor")
    
    weapon_data = get_item(weapon_id) if weapon_id else None
    armor_data = get_item(armor_id) if armor_id else None
    
    # Считаем итоговые статы
    base_dmg = 5 # Базовый урон кулаками
    total_dmg = base_dmg + (weapon_data['stats'].get('dmg', 0) if weapon_data else 0)
    total_def = armor_data['stats'].get('def', 0) if armor_data else 0
    
    w_name = weapon_data['name'] if weapon_data else "Кулаки"
    a_name = armor_data['name'] if armor_data else "Лохмотья"
    
    potions = inv.get("potions", [])
    gold = user['gold']
    
    text = (
        f"🎒 **Инвентарь ({user['username']})**\n\n"
        f"💰 Золото: {gold}\n\n"
        f"🗡 **Оружие:** {w_name}\n"
        f"🛡 **Броня:** {a_name}\n\n"
        f"📊 **Ваши характеристики:**\n"
        f"Урон: {total_dmg} | Защита: {total_def} | ХП: {user['hp']}/{user['max_hp']}\n\n"
        f"🧪 **Расходники на поясе:**\n"
    )
    
    if potions:
        for p in potions:
            text += f" • {p}\n"
    else:
        text += " • Пусто\n"
        
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 В лагерь", callback_data="town_back")]
    ])
    
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
