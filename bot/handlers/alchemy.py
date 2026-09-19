# handlers/alchemy.py
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database import get_user, update_user, get_all_ingredients

router = Router()

# 1. ГЛАВНОЕ МЕНЮ АЛХИМИИ (Выбор первого слота)
@router.callback_query(F.data == "town_alchemy")
async def open_alchemy_table(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    known = user.get("known_traits", {})
    all_ing = get_all_ingredients()
    
    inv = user['inventory']
    materials = inv.get("materials", {})
    
    text = "🧪 **Алхимический Котел**\n\nВаши ингредиенты:\n"
    buttons = []
    
    has_ingredients = False
    for ing_id, count in materials.items():
        if count > 0 and ing_id in all_ing:
            has_ingredients = True
            data = all_ing[ing_id]
            # Показываем изученные свойства (открытые или "???")
            disc = known.get(ing_id, [])
            traits_str = ", ".join([t if t in disc else "???" for t in data["traits"]])
            
            text += f"• **{data['name']}** (x{count})\n  └ [{traits_str}]\n"
            
            # Кнопка для выбора в 1-й слот
            buttons.append([InlineKeyboardButton(
                text=f"Слот 1: {data['name']}", 
                callback_data=f"alch:pick1:{ing_id}"
            )])
            
    if not has_ingredients:
        text += "\n*У вас нет подходящих трав. Сначала сходите в Руины!*\n"
        
    buttons.append([InlineKeyboardButton(text="🔙 Вернуться в лагерь", callback_data="town_back")])
    
    await callback.message.edit_text(
        text, 
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), 
        parse_mode="Markdown"
    )

# 2. ВЫБОР ВТОРОГО СЛОТА
@router.callback_query(F.data.startswith("alch:pick1:"))
async def pick_second_slot(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    ing1_id = callback.data.split(":")[2]
    
    all_ing = get_all_ingredients()
    inv = user['inventory']
    materials = inv.get("materials", {})
    
    ing1_name = all_ing[ing1_id]['name']
    
    text = f"🧪 **Алхимический Котел**\n\nВ первом слоте: **{ing1_name}**\nВыберите ингредиент для второго слота:\n"
    buttons = []
    
    for ing_id, count in materials.items():
        if ing_id not in all_ing:
            continue
            
        # Если игрок выбирает тот же самый ингредиент, проверяем, есть ли у него минимум 2 штуки
        if ing_id == ing1_id and count < 2:
            continue
            
        if count > 0:
            ing_name = all_ing[ing_id]['name']
            buttons.append([InlineKeyboardButton(
                text=f"Смешать с: {ing_name}", 
                callback_data=f"alch:mix:{ing1_id}:{ing_id}"
            )])
            
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="town_alchemy")])
    
    await callback.message.edit_text(
        text, 
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), 
        parse_mode="Markdown"
    )

# 3. ЛОГИКА СМЕШИВАНИЯ И КРАФТА
@router.callback_query(F.data.startswith("alch:mix:"))
async def brew_potion(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    _, _, ing1, ing2 = callback.data.split(":")
    
    inv = user['inventory']
    materials = inv.get("materials", {})
    
    # Защита: проверяем, хватает ли ресурсов перед крафтом
    if materials.get(ing1, 0) < 1 or materials.get(ing2, 0) < 1:
        return await callback.answer("Недостаточно ингредиентов!", show_alert=True)
    if ing1 == ing2 and materials.get(ing1, 0) < 2:
        return await callback.answer("Недостаточно ингредиентов!", show_alert=True)
        
    # Списываем ресурсы
    materials[ing1] -= 1
    materials[ing2] -= 1
    
    all_ing = get_all_ingredients()
    
    # Ищем пересечения свойств
    traits1 = set(all_ing[ing1]["traits"])
    traits2 = set(all_ing[ing2]["traits"])
    common_traits = traits1.intersection(traits2)
    
    known = user.get("known_traits", {})
    known.setdefault(ing1, [])
    known.setdefault(ing2, [])
    
    result_msg = ""
    
    if common_traits:
        # Берем первое совпавшее свойство (можно усложнить, если их несколько)
        trait = list(common_traits)[0]
        
        # Открываем свойство для игрока
        if trait not in known[ing1]: known[ing1].append(trait)
        if trait not in known[ing2]: known[ing2].append(trait)
        
        # Выдаем зелье
        potions = inv.setdefault("potions", [])
        potions.append(f"Зелье: {trait}")
        
        result_msg = f"✨ Успех! Свойства срезонировали!\nВы создали: [Зелье: {trait}]!"
    else:
        result_msg = "💀 Свойства не совпали. Ингредиенты превратились в бесполезную жижу."
    
    # Сохраняем обновленный инвентарь и знания
    inv["materials"] = materials
    update_user(user['user_id'], known_traits=known, inventory=inv)
    
    # Показываем результат и кнопку возврата
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Сварить еще", callback_data="town_alchemy")],
        [InlineKeyboardButton(text="🔙 В лагерь", callback_data="town_back")]
    ])
    
    await callback.message.edit_text(
        f"🧪 **Результат Алхимии**\n\n{result_msg}", 
        reply_markup=kb, 
        parse_mode="Markdown"
    )
