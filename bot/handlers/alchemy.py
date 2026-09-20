from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database import get_user, update_user, get_all_ingredients

router = Router()

@router.callback_query(F.data == "town_alchemy")
async def open_alchemy_table(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    known = user.get("known_traits", {})
    all_ing = get_all_ingredients()
    materials = user['inventory'].get("materials", {})
    
    text = "🧪 **Алхимический Котел**\n\nВаши ингредиенты:\n"
    buttons, has_ingredients = [], False
    
    for ing_id, count in materials.items():
        if count > 0 and ing_id in all_ing:
            has_ingredients = True
            data = all_ing[ing_id]
            traits_str = ", ".join([t if t in known.get(ing_id, []) else "???" for t in data["traits"]])
            text += f"• **{data['name']}** (x{count})\n  └ [{traits_str}]\n"
            buttons.append([InlineKeyboardButton(text=f"Слот 1: {data['name']}", callback_data=f"alch:pick1:{ing_id}")])
            
    if not has_ingredients: text += "\n*У вас нет подходящих трав. Сходите в Руины!*\n"
    buttons.append([InlineKeyboardButton(text="🔙 В лагерь", callback_data="town_back")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data.startswith("alch:pick1:"))
async def pick_second_slot(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    ing1_id = callback.data.split(":")[2]
    all_ing = get_all_ingredients()
    materials = user['inventory'].get("materials", {})
    
    text = f"🧪 **Алхимический Котел**\n\nВ первом слоте: **{all_ing[ing1_id]['name']}**\nВыберите второй ингредиент:\n"
    buttons = []
    
    for ing_id, count in materials.items():
        # ИСПРАВЛЕНИЕ: Теперь нельзя выбрать тот же самый ингредиент
        if ing_id in all_ing and ing_id != ing1_id and count > 0:
            buttons.append([InlineKeyboardButton(text=f"Смешать с: {all_ing[ing_id]['name']}", callback_data=f"alch:mix:{ing1_id}:{ing_id}")])
            
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="town_alchemy")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data.startswith("alch:mix:"))
async def brew_potion(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    _, _, ing1, ing2 = callback.data.split(":")
    
    if ing1 == ing2:
        return await callback.answer("Ошибка: нельзя смешать ингредиент сам с собой!", show_alert=True)
        
    inv = user['inventory']
    materials = inv.get("materials", {})
    
    if materials.get(ing1, 0) < 1 or materials.get(ing2, 0) < 1:
        return await callback.answer("Недостаточно ингредиентов!", show_alert=True)
        
    materials[ing1] -= 1
    materials[ing2] -= 1
    
    all_ing = get_all_ingredients()
    common_traits = set(all_ing[ing1]["traits"]).intersection(set(all_ing[ing2]["traits"]))
    known = user.get("known_traits", {})
    known.setdefault(ing1, []); known.setdefault(ing2, [])
    
    if common_traits:
        trait = list(common_traits)[0]
        if trait not in known[ing1]: known[ing1].append(trait)
        if trait not in known[ing2]: known[ing2].append(trait)
        inv.setdefault("potions", []).append(f"Зелье: {trait}")
        result_msg = f"✨ Успех! Создано: [Зелье: {trait}]!"
    else:
        result_msg = "💀 Свойства не совпали. Ингредиенты испорчены."
    
    inv["materials"] = materials
    update_user(user['user_id'], known_traits=known, inventory=inv)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔄 Сварить еще", callback_data="town_alchemy")], [InlineKeyboardButton(text="🔙 В лагерь", callback_data="town_back")]])
    await callback.message.edit_text(f"🧪 **Результат**\n\n{result_msg}", reply_markup=kb, parse_mode="Markdown")
