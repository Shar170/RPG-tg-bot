from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database import get_user, update_user, get_all_ingredients, get_item_name, track_stat

router = Router()

# --- ГЛАВНОЕ МЕНЮ АЛХИМИИ ---
@router.callback_query(F.data == "town_alchemy")
async def open_alchemy_hub(callback: CallbackQuery):
    text = (
        "🧪 **Алхимическая Лаборатория**\n\n"
        "Выберите режим работы:\n\n"
        "🔬 **Исследование** — смешивайте любые ингредиенты наугад, чтобы открывать их скрытые свойства и находить новые эффекты.\n\n"
        "⚗️ **Производство** — быстрое изготовление зелий по уже открытым свойствам. Доступен массовый крафт (x1, x5 или сразу ВСЕ)!"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔬 Исследование", callback_data="alch_mode_explore")],
        [InlineKeyboardButton(text="⚗️ Производство (Массовое)", callback_data="alch_mode_produce")],
        [InlineKeyboardButton(text="🔙 В лагерь", callback_data="town_back")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")


# =====================================================================
# 🔬 РЕЖИМ 1: ИССЛЕДОВАНИЕ (Смешивание вслепую)
# =====================================================================
@router.callback_query(F.data == "alch_mode_explore")
async def explore_pick_first(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    known = user.get("known_traits", {})
    all_ing = get_all_ingredients()
    materials = user['inventory'].get("materials", {})
    
    text = "🔬 **Исследование: Выберите первый ингредиент**\n\nВаши запасы:\n"
    buttons, has_ingredients = [], False
    
    for ing_id, count in sorted(materials.items()):
        if count > 0 and ing_id in all_ing:
            has_ingredients = True
            data = all_ing[ing_id]
            # Показываем открытые свойства или вопросики
            traits_str = ", ".join([t if t in known.get(ing_id, []) else "???" for t in data["traits"]])
            text += f"• **{data['name']}** (x{count})\n  └ [{traits_str}]\n"
            buttons.append([InlineKeyboardButton(text=f"Слот 1: {data['name']}", callback_data=f"alch_exp1:{ing_id}")])
            
    if not has_ingredients:
        text += "\n*У вас нет трав и реагентов для экспериментов.*\n"
        
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="town_alchemy")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data.startswith("alch_exp1:"))
async def explore_pick_second(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    ing1_id = callback.data.split(":")[1]
    all_ing = get_all_ingredients()
    materials = user['inventory'].get("materials", {})
    
    ing1_name = all_ing.get(ing1_id, {}).get("name", ing1_id)
    text = (
        f"🔬 **Исследование**\n\n"
        f"В первом слоте: **{ing1_name}**\n"
        f"Выберите второй ингредиент для смешивания:\n"
    )
    buttons = []
    
    for ing_id, count in sorted(materials.items()):
        if ing_id in all_ing and count > 0:
            # Строгий запрет: ингредиент не может смешиваться сам с собой
            if ing_id == ing1_id:
                continue
                
            buttons.append([InlineKeyboardButton(
                text=f"Смешать с: {all_ing[ing_id]['name']} (x{count})", 
                callback_data=f"alch_exp_mix:{ing1_id}:{ing_id}"
            )])
            
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="alch_mode_explore")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data.startswith("alch_exp_mix:"))
async def explore_execute_mix(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    _, ing1, ing2 = callback.data.split(":")
    
    # Бэкенд-защита от подмены callback_data
    if ing1 == ing2:
        return await callback.answer("Нельзя смешивать одинаковые ингредиенты!", show_alert=True)
    
    inv = user['inventory']
    materials = inv.get("materials", {})
    
    # Проверка наличия ингредиентов
    if materials.get(ing1, 0) < 1 or materials.get(ing2, 0) < 1:
        return await callback.answer("Недостаточно ингредиентов!", show_alert=True)
        
    materials[ing1] -= 1
    if materials[ing1] == 0: del materials[ing1]
    materials[ing2] -= 1
    if ing2 in materials and materials[ing2] == 0: del materials[ing2]
    
    all_ing = get_all_ingredients()
    common_traits = list(set(all_ing[ing1]["traits"]).intersection(set(all_ing[ing2]["traits"])))
    
    known = user.get("known_traits", {})
    known.setdefault(ing1, [])
    known.setdefault(ing2, [])
    
    new_discovered = []
    if common_traits:
        for trait in common_traits:
            if trait not in known[ing1]:
                known[ing1].append(trait)
                new_discovered.append(trait)
            if trait not in known[ing2]:
                known[ing2].append(trait)
                if trait not in new_discovered:
                    new_discovered.append(trait)
            
        trait_str = ", ".join(common_traits)
        potion_name = f"Зелье: {trait_str}"
        inv.setdefault("potions", []).append(potion_name)
        
        track_stat(user['user_id'], 'potions_crafted', 1)
        
        disc_text = f"\n💡 **Открыты свойства:** {', '.join(new_discovered)}!" if new_discovered else "\n(Эти свойства вам уже были известны)"
        result_msg = f"✨ **Эксперимент успешен!**\nСоздано: **[{potion_name}]**{disc_text}"
    else:
        result_msg = "💀 **Неудача.** Общих свойств не обнаружено, смесь испарилась едким дымом."
    
    inv["materials"] = materials
    update_user(user['user_id'], known_traits=known, inventory=inv)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔬 Исследовать еще", callback_data="alch_mode_explore")],
        [InlineKeyboardButton(text="🔙 В меню алхимии", callback_data="town_alchemy")]
    ])
    await callback.message.edit_text(f"🧪 **Результат исследования**\n\n{result_msg}", reply_markup=kb, parse_mode="Markdown")


# =====================================================================
# ⚗️ РЕЖИМ 2: ПРОИЗВОДСТВО (Массовый крафт по открытым свойствам)
# =====================================================================
@router.callback_query(F.data == "alch_mode_produce")
async def produce_catalog(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    known = user.get("known_traits", {})
    all_ing = get_all_ingredients()
    materials = user['inventory'].get("materials", {})
    
    user_mats = [m for m in materials.keys() if materials.get(m, 0) > 0 and m in all_ing]
    grouped_recipes = {} # Группируем рецепты по итоговому эффекту зелья
    
    for i in range(len(user_mats)):
        for j in range(i + 1, len(user_mats)):
            m1, m2 = user_mats[i], user_mats[j]
            shared_known = list(set(known.get(m1, [])).intersection(set(known.get(m2, []))))
            
            if shared_known:
                # Обязательно сортируем, чтобы "Хилл, Мана" и "Мана, Хилл" попали в одну группу
                shared_known.sort() 
                traits_title = ", ".join(shared_known)
                max_craft = min(materials[m1], materials[m2])
                
                if traits_title not in grouped_recipes:
                    grouped_recipes[traits_title] = 0
                grouped_recipes[traits_title] += max_craft
                    
    if not grouped_recipes:
        text = (
            "⚗️ **Производственный цех**\n\n"
            "❌ Нет доступных рецептов из текущих запасов!\n\n"
            "Чтобы варить зелья здесь:\n"
            "1. Откройте общие свойства ингредиентов в режиме **🔬 Исследование**.\n"
            "2. Убедитесь, что у вас в инвентаре есть обе травы с совпадающими открытыми свойствами."
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔬 Перейти к Исследованию", callback_data="alch_mode_explore")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="town_alchemy")]
        ])
        return await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        
    text = "⚗️ **Производство: Выберите зелье для крафта**\nСформировано на основе ваших знаний и запасов:\n\n"
    buttons = []
    
    for traits_title, total_craft in list(grouped_recipes.items())[:15]: 
        # Обрезаем строку до 30 символов, чтобы не выйти за лимит callback_data (64 байта)
        safe_title = traits_title[:30] 
        btn_text = f"🧪 {traits_title} [доступно: {total_craft} шт]"
        buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"alch_grp:{safe_title}")])
        
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="town_alchemy")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")


# --- НОВЫЙ ХЭНДЛЕР: ПОДМЕНЮ ВЫБОРА РЕЦЕПТА ---
@router.callback_query(F.data.startswith("alch_grp:"))
async def produce_group_select(callback: CallbackQuery):
    safe_title = callback.data.split(":", 1)[1]
    user = get_user(callback.from_user.id)
    known = user.get("known_traits", {})
    all_ing = get_all_ingredients()
    materials = user['inventory'].get("materials", {})

    user_mats = [m for m in materials.keys() if materials.get(m, 0) > 0 and m in all_ing]
    buttons = []
    
    for i in range(len(user_mats)):
        for j in range(i + 1, len(user_mats)):
            m1, m2 = user_mats[i], user_mats[j]
            shared_known = list(set(known.get(m1, [])).intersection(set(known.get(m2, []))))
            
            if shared_known:
                shared_known.sort()
                traits_title = ", ".join(shared_known)
                
                # Если сгенерированный эффект совпадает с выбранным из прошлого меню
                if traits_title[:30] == safe_title:
                    max_craft = min(materials[m1], materials[m2])
                    name1 = all_ing[m1]['name']
                    name2 = all_ing[m2]['name']
                    btn_text = f"🌿 {name1} + {name2} [до {max_craft} шт]"
                    buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"alch_prod_sel:{m1}:{m2}")])

    text = f"⚗️ **Рецепты для зелья:** [{safe_title}]\n\nВыберите комбинацию ингредиентов:"
    buttons.append([InlineKeyboardButton(text="🔙 К списку зелий", callback_data="alch_mode_produce")])
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")


# --- ИЗМЕНЕННЫЙ ХЭНДЛЕР: МЕНЮ ВЫБОРА КОЛИЧЕСТВА ---
@router.callback_query(F.data.startswith("alch_prod_sel:"))
async def produce_batch_select(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    _, ing1, ing2 = callback.data.split(":")
    materials = user['inventory'].get("materials", {})
    all_ing = get_all_ingredients()
    
    count1 = materials.get(ing1, 0)
    count2 = materials.get(ing2, 0)
    max_possible = min(count1, count2)
    
    if max_possible < 1:
        return await callback.answer("Ингредиенты закончились!", show_alert=True)
        
    known = user.get("known_traits", {})
    shared_traits = list(set(known.get(ing1, [])).intersection(set(known.get(ing2, []))))
    shared_traits.sort() # Поддерживаем сортировку
    traits_str = ", ".join(shared_traits)
    
    name1 = all_ing[ing1]['name']
    name2 = all_ing[ing2]['name']
    
    text = (
        f"⚗️ **Варка: Зелье [{traits_str}]**\n\n"
        f"Компоненты:\n"
        f"• {name1} (в наличии: {count1})\n"
        f"• {name2} (в наличии: {count2})\n\n"
        f"Максимум можно сварить: **{max_possible} шт.**\n"
        f"Сколько изготовить?"
    )
    
    buttons = []
    row = [InlineKeyboardButton(text="x1", callback_data=f"alch_batch_run:{ing1}:{ing2}:1")]
    if max_possible >= 5:
        row.append(InlineKeyboardButton(text="x5", callback_data=f"alch_batch_run:{ing1}:{ing2}:5"))
    row.append(InlineKeyboardButton(text=f"Все ({max_possible} шт)", callback_data=f"alch_batch_run:{ing1}:{ing2}:{max_possible}"))
    buttons.append(row)
    
    # Кнопка возврата теперь ведет не в корень, а в подменю конкретного зелья
    safe_title = traits_str[:30]
    buttons.append([InlineKeyboardButton(text="🔙 Назад к рецептам", callback_data=f"alch_grp:{safe_title}")])
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")


@router.callback_query(F.data.startswith("alch_batch_run:"))
async def produce_batch_execute(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    _, ing1, ing2, amount_str = callback.data.split(":")
    amount = int(amount_str)
    
    inv = user['inventory']
    materials = inv.get("materials", {})
    all_ing = get_all_ingredients()
    
    max_possible = min(materials.get(ing1, 0), materials.get(ing2, 0))
    craft_qty = min(amount, max_possible)
    
    if craft_qty <= 0:
        return await callback.answer("Недостаточно ресурсов!", show_alert=True)
        
    # Списание материалов
    materials[ing1] -= craft_qty
    if materials[ing1] == 0: del materials[ing1]
    materials[ing2] -= craft_qty
    if ing2 in materials and materials[ing2] == 0: del materials[ing2]
    
    # Определение свойств (берем все фактические общие свойства для зелья)
    common_traits = list(set(all_ing[ing1]["traits"]).intersection(set(all_ing[ing2]["traits"])))
    potion_name = f"Зелье: {', '.join(common_traits)}"
    
    # Добавление пачки зелий
    potions = inv.setdefault("potions", [])
    for _ in range(craft_qty):
        potions.append(potion_name)
        
    track_stat(user['user_id'], 'potions_crafted', craft_qty)
    
    inv["materials"] = materials
    update_user(user['user_id'], inventory=inv)
    
    await callback.answer(f"Сварено {craft_qty} шт.!", show_alert=False)
    
    text = (
        f"🎉 **Готово!**\n\n"
        f"Успешно изготовлено: **{craft_qty}x [{potion_name}]**\n"
        f"Зелья аккуратно уложены в вашу сумку."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚗️ Сварить еще", callback_data="alch_mode_produce")],
        [InlineKeyboardButton(text="🎒 Инвентарь", callback_data="inv_open")],
        [InlineKeyboardButton(text="🔙 В лагерь", callback_data="town_back")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

