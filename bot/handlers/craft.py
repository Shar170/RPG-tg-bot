from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database import get_user, update_user, get_all_recipes, get_item, get_item_name, add_quest_progress, add_global_event, track_stat

router = Router()

@router.callback_query(F.data == "town_craft")
async def open_workshop(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    materials = user['inventory'].get("materials", {})
    text = f"🔨 **Мастерская**\n\n💰 Золото: {user['gold']}\n\n**Чертежи:**\n"
    buttons = []
    
    for rec in get_all_recipes():
        result_item = get_item(rec['result_item_id'])
        if not result_item: continue
        
        req_texts, can_craft = [], True
        
        for mat_id, count in rec['materials'].items():
            m_name = get_item_name(mat_id) 
            have = materials.get(mat_id, 0)
            req_texts.append(f"{m_name} ({have}/{count})")
            if have < count: can_craft = False
                
        if user['gold'] < rec['gold']: can_craft = False
            
        text += f"• **{result_item['name']}**\n  └ 🪙 {rec['gold']} | 📦 {', '.join(req_texts)}\n"
        if can_craft: buttons.append([InlineKeyboardButton(text=f"Скрафтить: {result_item['name']}", callback_data=f"craft_do_{rec['recipe_id']}")])

    buttons.append([InlineKeyboardButton(text="🔙 В лагерь", callback_data="town_back")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data.startswith("craft_do_"))
async def do_craft(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    recipe_id = callback.data.replace("craft_do_", "")
    recipe = next((r for r in get_all_recipes() if r['recipe_id'] == recipe_id), None)
    if not recipe: return await callback.answer("Рецепт не найден!", show_alert=True)
    
    inv = user['inventory']
    materials = inv.get("materials", {})
    
    if user['gold'] < recipe['gold'] or any(materials.get(m, 0) < c for m, c in recipe['materials'].items()):
        return await callback.answer("Недостаточно ресурсов!", show_alert=True)
        
    user['gold'] -= recipe['gold']
    for m, c in recipe['materials'].items(): materials[m] -= c
        
    result_item = get_item(recipe['result_item_id'])
    if result_item['type'] in ["weapon", "armor"]: inv.setdefault("backpack", []).append(recipe['result_item_id'])
    elif result_item['type'] == "artifact": inv.setdefault("artifacts", []).append(recipe['result_item_id'])
    else: inv.setdefault("materials", {})[recipe['result_item_id']] = materials.get(recipe['result_item_id'], 0) + 1
        
    inv["materials"] = materials
    update_user(user['user_id'], gold=user['gold'], inventory=inv)
    
    # ПРОГРЕСС КВЕСТОВ И СТАТЫ (Крафт)
    add_quest_progress(user['user_id'], "craft_items", 1)
    track_stat(user['user_id'], 'items_crafted', 1)
    
    # --- ЗАПИСЬ В ВЕСТНИК ---
    if result_item['type'] in ["weapon", "armor"] and recipe['gold'] >= 1000:
        add_global_event(f"🔨 Мастер **{user['username']}** выковал ценное снаряжение: {result_item['name']}.")
    
    await callback.answer(f"✨ Создано: {result_item['name']}!", show_alert=True)
    await open_workshop(callback)
