import json
import datetime
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from database import (
    get_user, update_user, get_clan, update_clan, 
    get_clan_by_name, get_all_clans_ranked, get_clan_members,
    get_connection, get_clan_creation_requirements, get_item_name,
    get_clan_merchant_deals, get_item_price, get_item
)

router = Router()

class ClanStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_gold = State()
    waiting_for_gems = State()
    waiting_for_withdraw_gold = State()
    waiting_for_withdraw_gems = State()
    waiting_for_banner = State()
    waiting_for_chat_msg = State()

def format_clan_requirements_text(reqs: dict, short: bool = False) -> str:
    parts = []
    if reqs["min_level"] > 0:
        parts.append(f"{reqs['min_level']} ур." if short else f"Уровень {reqs['min_level']}+")
    if reqs["cost_gems"] > 0:
        parts.append(f"{reqs['cost_gems']} 💎")
    if reqs["cost_gold"] > 0:
        parts.append(f"{reqs['cost_gold']} 🪙")
        
    if not parts:
        return "Бесплатно"
    return " + ".join(parts) if short else ", ".join(parts)

def get_clan_main_kb(user: dict):
    buttons = []
    clan_id = user.get('clan_id', 0)
    if clan_id == 0:
        reqs = get_clan_creation_requirements()
        cost_badge = format_clan_requirements_text(reqs, short=True)
        btn_label = f"➕ Создать клан ({cost_badge})" if cost_badge != "Бесплатно" else "➕ Создать клан"
        
        buttons.append([InlineKeyboardButton(text="🔍 Поиск кланов", callback_data="clan_search_list")])
        buttons.append([InlineKeyboardButton(text=btn_label, callback_data="clan_create_start")])
    else:
        buttons.append([InlineKeyboardButton(text="🏰 Мой Клан", callback_data="clan_my_info")])
        buttons.append([InlineKeyboardButton(text="🔍 Поиск кланов", callback_data="clan_search_list")])
        buttons.append([InlineKeyboardButton(text="📦 Казна и Склад", callback_data="clan_vault_view")])
    buttons.append([InlineKeyboardButton(text="🔙 В лагерь", callback_data="town_back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# --- ГЛАВНЫЙ ВХОД В КЛАНОВЫЙ ЗАЛ ---
@router.callback_query(F.data == "clan_main")
async def clan_main_menu(callback: CallbackQuery, state: FSMContext):
    if state: await state.clear()
    user = get_user(callback.from_user.id)
    clan_id = user.get('clan_id', 0)
    
    text = (
        "🛡️ **Клановый Зал**\n\n"
        "Объединяйтесь с другими искателями приключений!\n\n"
        "🏆 **Еженедельные награды Топ-3 кланам в казну:**\n"
        "🥇 1 место — **10 💎**\n"
        "🥈 2 место — **5 💎**\n"
        "🥉 3 место — **1 💎**\n"
        "*(Награды начисляются каждый понедельник в казну)*\n\n"
    )
    if clan_id != 0:
        clan = get_clan(clan_id)
        banner = f"{clan.get('banner', '')} " if clan and clan.get('banner') else ""
        c_name = clan['name'] if clan else "Неизвестно"
        text += f"Вы состоите в клане: **{banner}{c_name}**"
    else:
        reqs = get_clan_creation_requirements()
        reqs_str = format_clan_requirements_text(reqs, short=False)
        text += "Вы пока одиночка. Найдите клан в поиске или создайте свой!"
        if reqs_str != "Бесплатно":
            text += f"\n*(Основание клана: {reqs_str})*"
        
    await callback.message.edit_text(text, reply_markup=get_clan_main_kb(user), parse_mode="Markdown")

# --- СОЗДАНИЕ КЛАНА ---
@router.callback_query(F.data == "clan_create_start")
async def clan_create_start(callback: CallbackQuery, state: FSMContext):
    user = get_user(callback.from_user.id)
    if user.get('clan_id', 0) != 0:
        return await callback.answer("Вы уже состоите в клане!", show_alert=True)
    
    reqs = get_clan_creation_requirements()
    user_lvl = user.get('level', 1)
    user_gems = user.get('gems', 0)
    user_gold = user.get('gold', 0)
    
    if reqs["min_level"] > 0 and user_lvl < reqs["min_level"]:
        return await callback.answer(f"⛔ Недостаточный уровень! Требуется {reqs['min_level']} ур.", show_alert=True)
    if reqs["cost_gems"] > 0 and user_gems < reqs["cost_gems"]:
        return await callback.answer(f"⛔ Недостаточно кристаллов! Требуется {reqs['cost_gems']} 💎.", show_alert=True)
    if reqs["cost_gold"] > 0 and user_gold < reqs["cost_gold"]:
        return await callback.answer(f"⛔ Недостаточно золота! Требуется {reqs['cost_gold']} 🪙.", show_alert=True)
        
    req_lines = []
    if reqs["min_level"] > 0: req_lines.append(f"• Уровень: **{reqs['min_level']}** ✅")
    if reqs["cost_gems"] > 0: req_lines.append(f"• Стоимость: **{reqs['cost_gems']} 💎**")
    if reqs["cost_gold"] > 0: req_lines.append(f"• Стоимость: **{reqs['cost_gold']} 🪙**")
    req_display = "\n".join(req_lines) if req_lines else "• Без особых требований"

    await state.set_state(ClanStates.waiting_for_name)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="clan_main")]])
    await callback.message.edit_text(
        f"🏰 **Основание нового Клана**\n\n{req_display}\n\nВведите название для вашего клана (от 3 до 20 символов):", 
        reply_markup=kb, parse_mode="Markdown"
    )

@router.message(ClanStates.waiting_for_name)
async def clan_create_name_input(message: Message, state: FSMContext):
    name = message.text.strip()
    user = get_user(message.from_user.id)
    reqs = get_clan_creation_requirements()
    
    if len(name) < 3 or len(name) > 20:
        return await message.answer("⚠️ Название должно быть от 3 до 20 символов! Попробуйте снова:")
    if get_clan_by_name(name):
        return await message.answer("⚠️ Клан с таким названием уже существует! Придумайте другое:")
        
    if reqs["min_level"] > 0 and user.get('level', 1) < reqs["min_level"]: return await message.answer("⛔ Недостаточный уровень!")
    if reqs["cost_gems"] > 0 and user.get('gems', 0) < reqs["cost_gems"]: return await message.answer("⛔ Не хватает кристаллов!")
    if reqs["cost_gold"] > 0 and user.get('gold', 0) < reqs["cost_gold"]: return await message.answer("⛔ Не хватает золота!")
        
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("INSERT INTO clans (name, leader_id, level, treasury, weekly_raids, total_raids, join_requests, clan_vault) VALUES (?, ?, 1, 0, 0, 0, '[]', '{\"gems\": 0, \"items\": {}}')", (name, user['user_id']))
        new_clan_id = cur.lastrowid
        conn.commit()
        
    new_gems = max(0, user.get('gems', 0) - reqs["cost_gems"])
    new_gold = max(0, user.get('gold', 0) - reqs["cost_gold"])
    update_user(user['user_id'], gems=new_gems, gold=new_gold, clan_id=new_clan_id, clan_role='hedwing')
    await state.clear()
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏰 В мой клан", callback_data="clan_my_info")],
        [InlineKeyboardButton(text="🔙 В лагерь", callback_data="town_back")]
    ])
    await message.answer(f"🎉 **Великое событие!**\nКлан **{name}** успешно основан!\nВы назначены его верховным лидером.", reply_markup=kb, parse_mode="Markdown")

# --- МОЙ КЛАН (ПРОФИЛЬ) ---
@router.callback_query(F.data == "clan_my_info")
async def show_my_clan(callback: CallbackQuery, state: FSMContext):
    if state: await state.clear()
    user = get_user(callback.from_user.id)
    clan_id = user.get('clan_id', 0)
    if clan_id == 0:
        return await callback.answer("Вы не состоите в клане!", show_alert=True)
        
    clan = get_clan(clan_id)
    if not clan:
        update_user(user['user_id'], clan_id=0, clan_role='thrall')
        return await callback.answer("Клан был распущен!", show_alert=True)
        
    members = get_clan_members(clan_id)
    max_m = 5 + clan['level'] * 5
    is_leader = (user['user_id'] == clan['leader_id'])
    
    role_titles = {'hedwing': '👑 Глава', 'lindeman': '⚔️ Офицер', 'thrall': '🛡️ Рядовой'}
    members_text = ""
    for m in members:
        r_str = role_titles.get(m['clan_role'], '🛡️')
        members_text += f" • {r_str} **{m['username']}** (Ур. {m['level']})\n"
        
    reqs_count = len(clan.get('join_requests', []))
    banner_str = f"{clan.get('banner', '')} " if clan.get('banner') else ""
    
    text = (
        f"🏰 **Клан: {banner_str}{clan['name']}**\n\n"
        f"Уровень: **{clan['level']}**\n"
        f"Рейдов за всё время: **{clan.get('total_raids', 0)}**\n"
        f"Бойцов: **{len(members)} / {max_m}**\n\n"
        f"👥 **Состав клана:**\n{members_text}\n"
    )
    if is_leader and reqs_count > 0:
        text += f"📬 **Входящие заявки:** {reqs_count} шт.\n"
        
    buttons = []
    # --- НОВЫЕ КНОПКИ: ЧАТ И ТОРГОВЕЦ ---
    buttons.append([InlineKeyboardButton(text="💬 Чат клана", callback_data="clan_chat_view")])
    
    if clan['level'] >= 5:
        buttons.append([InlineKeyboardButton(text="⚖️ Клановый Торговец", callback_data="clan_merchant_view")])
        
    if is_leader:
        # Установка стяга со 2 уровня
        if clan['level'] >= 2:
            buttons.append([InlineKeyboardButton(text="🏳️ Изменить стяг", callback_data="clan_set_banner_ask")])
        buttons.append([InlineKeyboardButton(text="🔼 Улучшить клан", callback_data="clan_upgrade_ask")])
        if reqs_count > 0:
            buttons.append([InlineKeyboardButton(text=f"📬 Заявки ({reqs_count})", callback_data="clan_requests_view")])
        
    if user['clan_role'] in ['hedwing', 'lindeman']:
        buttons.append([InlineKeyboardButton(text="👥 Управление составом", callback_data="clan_manage_list")])
        
    buttons.append([InlineKeyboardButton(text="📦 Казна и Склад", callback_data="clan_vault_view")])
    buttons.append([InlineKeyboardButton(text="🚪 Покинуть клан", callback_data="clan_leave_confirm")])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="clan_main")])
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

# --- СТЯГ КЛАНА ---
@router.callback_query(F.data == "clan_set_banner_ask")
async def clan_set_banner_ask(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ClanStates.waiting_for_banner)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="clan_my_info")]])
    await callback.message.edit_text("🏳️ **Установка стяга клана**\n\nОтправьте 1 или 2 эмодзи (например, 🐺 или ⚔️), которые будут отображаться рядом с названием клана:", reply_markup=kb, parse_mode="Markdown")

@router.message(ClanStates.waiting_for_banner)
async def clan_set_banner_do(message: Message, state: FSMContext):
    user = get_user(message.from_user.id)
    clan = get_clan(user.get('clan_id', 0))
    
    if not clan or clan['leader_id'] != user['user_id']:
        return await message.answer("Только лидер может изменять стяг!")
        
    banner = message.text.strip()
    if len(banner) > 4: # Emoji могут занимать несколько байт, 4 - безопасный лимит для 1-2 эмодзи
        return await message.answer("⚠️ Слишком длинный стяг! Попробуйте использовать 1-2 эмодзи.")
        
    update_clan(clan['clan_id'], banner=banner)
    await state.clear()
    
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 В клан", callback_data="clan_my_info")]])
    await message.answer(f"✅ Стяг клана успешно изменен на {banner}!", reply_markup=kb)

# --- ЧАТ КЛАНА ---
@router.callback_query(F.data == "clan_chat_view")
async def clan_chat_view(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    clan = get_clan(user.get('clan_id', 0))
    if not clan: return await callback.answer("У вас нет клана!", show_alert=True)
    
    chat = clan.get('chat_history', [])
    banner_str = f"{clan.get('banner', '')} " if clan.get('banner') else ""
    text = f"💬 **Чат клана: {banner_str}{clan['name']}**\n\n"
    
    if not chat:
        text += "*Сообщений пока нет...*\n"
    else:
        for msg in chat[-15:]: # Показываем последние 15
            text += f"👤 **{msg['user']}** `[{msg['time']}]`:\n{msg['text']}\n\n"
            
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Написать сообщение", callback_data="clan_chat_write")],
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="clan_chat_view")],
        [InlineKeyboardButton(text="🔙 В меню клана", callback_data="clan_my_info")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data == "clan_chat_write")
async def clan_chat_write(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ClanStates.waiting_for_chat_msg)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="clan_chat_view")]])
    await callback.message.edit_text("✍️ Введите ваше сообщение для клана (до 200 символов):", reply_markup=kb, parse_mode="Markdown")

@router.message(ClanStates.waiting_for_chat_msg)
async def clan_chat_receive(message: Message, state: FSMContext):
    user = get_user(message.from_user.id)
    clan = get_clan(user.get('clan_id', 0))
    if not clan: return
    
    chat = clan.get('chat_history', [])
    now_str = datetime.datetime.now().strftime("%H:%M")
    
    new_msg = {
        "user": user['username'],
        "text": message.text[:200], # Защита от спама длинным текстом
        "time": now_str
    }
    
    chat.append(new_msg)
    chat = chat[-50:] # Храним только последние 50 в базе
    
    update_clan(clan['clan_id'], chat_history=chat)
    await state.clear()
    
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💬 Открыть чат", callback_data="clan_chat_view")]])
    await message.answer("✅ Сообщение отправлено в клан!", reply_markup=kb)

# --- КЛАНОВЫЙ ТОРГОВЕЦ ---
@router.callback_query(F.data == "clan_merchant_view")
async def clan_merchant_view(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    clan = get_clan(user.get('clan_id', 0))
    
    if not clan or clan['level'] < 5:
        return await callback.answer("Торговец прибывает только в кланы 5-го уровня и выше!", show_alert=True)
        
    deals = get_clan_merchant_deals(clan['clan_id'])
    
    text = f"⚖️ **Клановый Торговец**\n💰 Ваше золото: {user['gold']} 🪙\n\n"
    buttons = []
    
    if clan['level'] >= 20:
        text += (
            "🌟 **Элитный доступ (Ур. 20):**\n"
            "Торговец теперь предоставляет постоянную **скидку 30%** на покупку и скупает лут по **100% стоимости** на ВСЕ возможные товары!\n\n"
            "*(Все клановые сделки теперь проходят через основной Городской Рынок, скидки активированы автоматически)*\n"
        )
        buttons.append([InlineKeyboardButton(text="⚖️ Перейти на Городской Рынок", callback_data="town_market")])
    else:
        text += "Торговец предлагает особые сделки на случайные товары, которые обновляются каждую полночь!\n\n"
        
        text += "🛒 **Товары со скидкой 30%:**\n"
        for i_id in deals.get('buy', []):
            price = max(1, int(get_item_price(i_id) * 0.7))
            text += f"• {get_item_name(i_id)} — {price} 🪙\n"
            buttons.append([InlineKeyboardButton(text=f"Купить: {get_item_name(i_id)}", callback_data=f"c_merch_buy_{i_id}")])
            
        text += "\n💎 **Скупка без штрафа (100% цены):**\n"
        for i_id in deals.get('sell', []):
            price = get_item_price(i_id)
            text += f"• {get_item_name(i_id)} — {price} 🪙\n"
            buttons.append([InlineKeyboardButton(text=f"Продать: {get_item_name(i_id)}", callback_data=f"c_merch_sell_{i_id}")])
            
    buttons.append([InlineKeyboardButton(text="🔙 В меню клана", callback_data="clan_my_info")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data.startswith("c_merch_buy_"))
async def clan_merchant_buy(callback: CallbackQuery):
    i_id = callback.data.replace("c_merch_buy_", "")
    user = get_user(callback.from_user.id)
    price = max(1, int(get_item_price(i_id) * 0.7))
    
    if user['gold'] < price:
        return await callback.answer("Недостаточно золота!", show_alert=True)
        
    item = get_item(i_id)
    inv = user['inventory']
    
    if item and item['type'] in ["weapon", "armor"]:
        inv.setdefault("backpack", []).append(i_id)
    elif item and item['type'] == "consumable":
        inv.setdefault("potions", []).append(item['name'])
    else:
        # Ресурс или ингредиент
        inv.setdefault("materials", {})[i_id] = inv.get("materials", {}).get(i_id, 0) + 1
        
    user['gold'] -= price
    update_user(user['user_id'], gold=user['gold'], inventory=inv)
    await callback.answer(f"Успешная покупка: {get_item_name(i_id)} за {price} 🪙", show_alert=True)
    await clan_merchant_view(callback)

@router.callback_query(F.data.startswith("c_merch_sell_"))
async def clan_merchant_sell(callback: CallbackQuery):
    i_id = callback.data.replace("c_merch_sell_", "")
    user = get_user(callback.from_user.id)
    
    inv = user['inventory']
    has_item = False
    
    if i_id in inv.get("backpack", []):
        inv["backpack"].remove(i_id)
        has_item = True
    elif inv.get("materials", {}).get(i_id, 0) > 0:
        inv["materials"][i_id] -= 1
        if inv["materials"][i_id] <= 0: del inv["materials"][i_id]
        has_item = True
    else:
        # Проверка зелий по имени (если это расходник)
        item_name = get_item_name(i_id)
        if item_name in inv.get("potions", []):
            inv["potions"].remove(item_name)
            has_item = True

    if not has_item:
        return await callback.answer("У вас нет этого предмета для продажи!", show_alert=True)
        
    price = get_item_price(i_id)
    user['gold'] += price
    
    update_user(user['user_id'], gold=user['gold'], inventory=inv)
    await callback.answer(f"Успешно продано за {price} 🪙", show_alert=True)
    await clan_merchant_view(callback)


# --- ПРОКАЧКА КЛАНА ---
@router.callback_query(F.data == "clan_upgrade_ask")
async def clan_upgrade_ask(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    clan = get_clan(user.get('clan_id', 0))
    
    if not clan or clan['leader_id'] != user['user_id']:
        return await callback.answer("Только лидер может улучшать клан!", show_alert=True)
        
    cur_lvl = clan['level']
    req_gold = 9000 + (cur_lvl * 1000)
    req_gems = 90 + (cur_lvl * 10)
    req_raids = cur_lvl * 100
    
    vault_raw = clan.get('clan_vault', '{}')
    vault = json.loads(vault_raw) if isinstance(vault_raw, str) else vault_raw
    cur_gold = clan['treasury']
    cur_gems = vault.get('gems', 0)
    cur_raids = clan.get('total_raids', 0)
    
    gold_mark = "✅" if cur_gold >= req_gold else "❌"
    gems_mark = "✅" if cur_gems >= req_gems else "❌"
    raids_mark = "✅" if cur_raids >= req_raids else "❌"
    
    text = (
        f"🔼 **Улучшение клана до {cur_lvl + 1} уровня**\n\n"
        f"Новый уровень увеличит максимальное количество участников на 5!\n"
        f"*(На 5 и 15 уровнях клановый торговец расширяет ассортимент, а на 20 уровне скидка распространяется на всё!)*\n\n"
        f"**Требования:**\n"
        f"• Золото в казне: **{cur_gold} / {req_gold}** 🪙 {gold_mark}\n"
        f"• Кристаллы в казне: **{cur_gems} / {req_gems}** 💎 {gems_mark}\n"
        f"• Всего рейдов пройдено: **{cur_raids} / {req_raids}** ⚔️ {raids_mark}\n\n"
        f"*(Ресурсы будут списаны из казны)*"
    )
    
    buttons = []
    if cur_gold >= req_gold and cur_gems >= req_gems and cur_raids >= req_raids:
        buttons.append([InlineKeyboardButton(text="✨ Улучшить!", callback_data="clan_upgrade_do")])
        
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="clan_my_info")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data == "clan_upgrade_do")
async def clan_upgrade_do(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    clan = get_clan(user.get('clan_id', 0))
    
    if not clan or clan['leader_id'] != user['user_id']:
        return await callback.answer("Ошибка доступа!", show_alert=True)
        
    cur_lvl = clan['level']
    req_gold = 9000 + (cur_lvl * 1000)
    req_gems = 90 + (cur_lvl * 10)
    req_raids = cur_lvl * 100
    
    vault_raw = clan.get('clan_vault', '{}')
    vault = json.loads(vault_raw) if isinstance(vault_raw, str) else vault_raw
    
    if clan['treasury'] < req_gold or vault.get('gems', 0) < req_gems or clan.get('total_raids', 0) < req_raids:
        return await callback.answer("Недостаточно ресурсов или рейдов!", show_alert=True)
        
    vault['gems'] -= req_gems
    new_treasury = clan['treasury'] - req_gold
    
    update_clan(clan['clan_id'], level=cur_lvl + 1, treasury=new_treasury, clan_vault=json.dumps(vault, ensure_ascii=False))
    
    await callback.answer(f"🎉 Клан достиг {cur_lvl + 1} уровня!", show_alert=True)
    await show_my_clan(callback, None)

# --- УПРАВЛЕНИЕ СОСТАВОМ (Повышения / Изгнания) ---
@router.callback_query(F.data == "clan_manage_list")
async def clan_manage_list(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    if user.get('clan_role') not in ['hedwing', 'lindeman']:
        return await callback.answer("У вас нет прав!", show_alert=True)
        
    members = get_clan_members(user['clan_id'])
    buttons = []
    for m in members:
        if m['user_id'] == user['user_id']: continue 
        role_icon = '👑' if m['clan_role'] == 'hedwing' else '⚔️' if m['clan_role'] == 'lindeman' else '🛡️'
        buttons.append([InlineKeyboardButton(text=f"{role_icon} {m['username']}", callback_data=f"clan_manage_u_{m['user_id']}")])
        
    buttons.append([InlineKeyboardButton(text="🔙 Назад в клан", callback_data="clan_my_info")])
    await callback.message.edit_text("👥 **Управление составом**\nВыберите участника для взаимодействия:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data.startswith("clan_manage_u_"))
async def clan_manage_user(callback: CallbackQuery):
    target_id = int(callback.data.replace("clan_manage_u_", ""))
    user = get_user(callback.from_user.id)
    target = get_user(target_id)
    
    if not target or target.get('clan_id') != user.get('clan_id'):
        return await callback.answer("Игрок не найден в клане!", show_alert=True)
        
    my_role = user.get('clan_role')
    tar_role = target.get('clan_role')
    
    if my_role == 'lindeman' and tar_role in ['hedwing', 'lindeman']:
        return await callback.answer("Офицер может управлять только рядовыми!", show_alert=True)
        
    role_titles = {'hedwing': 'Глава', 'lindeman': 'Офицер', 'thrall': 'Рядовой'}
    text = f"👤 **Участник: {target['username']}**\nТекущая должность: **{role_titles.get(tar_role, 'Рядовой')}**\n\nВыберите действие:"
    
    buttons = []
    if my_role == 'hedwing':
        if tar_role == 'thrall':
            buttons.append([InlineKeyboardButton(text="🔼 Сделать Офицером", callback_data=f"clan_setrole_{target_id}_lindeman")])
        elif tar_role == 'lindeman':
            buttons.append([InlineKeyboardButton(text="🔽 Понизить до Рядового", callback_data=f"clan_setrole_{target_id}_thrall")])
            
    buttons.append([InlineKeyboardButton(text="👢 Выгнать из клана", callback_data=f"clan_kick_{target_id}")])
    buttons.append([InlineKeyboardButton(text="🔙 Назад к списку", callback_data="clan_manage_list")])
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data.startswith("clan_setrole_"))
async def clan_setrole(callback: CallbackQuery):
    parts = callback.data.split("_")
    target_id, new_role = int(parts[2]), parts[3]
    user = get_user(callback.from_user.id)
    
    if user.get('clan_role') != 'hedwing':
        return await callback.answer("Только лидер может менять должности!", show_alert=True)
        
    update_user(target_id, clan_role=new_role)
    await callback.answer("Должность изменена!")
    await clan_manage_list(callback)

@router.callback_query(F.data.startswith("clan_kick_"))
async def clan_kick(callback: CallbackQuery):
    target_id = int(callback.data.replace("clan_kick_", ""))
    user = get_user(callback.from_user.id)
    target = get_user(target_id)
    
    my_role = user.get('clan_role')
    tar_role = target.get('clan_role') if target else 'thrall'
    
    if my_role == 'lindeman' and tar_role in ['hedwing', 'lindeman']:
        return await callback.answer("Недостаточно прав!", show_alert=True)
        
    update_user(target_id, clan_id=0, clan_role='thrall')
    await callback.answer("Игрок изгнан из клана!")
    await clan_manage_list(callback)

# --- КАЗНА И СКЛАД (ВКЛАДЫ И СНЯТИЯ) ---
@router.callback_query(F.data == "clan_vault_view")
async def show_clan_vault(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    user = get_user(callback.from_user.id)
    clan_id = user.get('clan_id', 0)
    if clan_id == 0:
        return await callback.answer("Вы не состоите в клане!", show_alert=True)
        
    clan = get_clan(clan_id)
    vault_raw = clan.get('clan_vault', '{}')
    if isinstance(vault_raw, str):
        try: vault = json.loads(vault_raw)
        except: vault = {"gems": 0, "items": {}}
    else:
        vault = vault_raw
        
    gems_in_vault = vault.get("gems", 0)
    gold_in_vault = clan.get("treasury", 0)
    items = vault.get("items", {})
    
    text = (
        f"📦 **Общак (Казна) клана {clan['name']}**\n\n"
        f"💰 Золото казны: **{gold_in_vault}** 🪙\n"
        f"💎 Кристаллы казны: **{gems_in_vault}** 💎\n\n"
        "**📦 Склад предметов:**\n"
    )
    if not items:
        text += "*(Склад пуст)*\n"
    else:
        for m_id, count in items.items():
            text += f"• {get_item_name(m_id)}: {count} шт.\n"
            
    buttons = [
        [InlineKeyboardButton(text="🪙 Внести золото", callback_data="clan_donate_gold_ask"),
         InlineKeyboardButton(text="💎 Внести кристаллы", callback_data="clan_donate_gems_ask")],
        [InlineKeyboardButton(text="📦 Внести ресурсы", callback_data="clan_donate_item_list")]
    ]
    
    if user.get('clan_role') in ['hedwing', 'lindeman']:
        buttons.append([
            InlineKeyboardButton(text="📤 Взять золото", callback_data="clan_withdraw_gold_ask"),
            InlineKeyboardButton(text="💠 Взять кристаллы", callback_data="clan_withdraw_gems_ask")
        ])
        buttons.append([InlineKeyboardButton(text="📥 Забрать ресурсы", callback_data="clan_withdraw_item_list")])
        
    buttons.append([InlineKeyboardButton(text="🔙 Назад в меню клана", callback_data="clan_my_info")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data == "clan_donate_gold_ask")
async def ask_donate_gold(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ClanStates.waiting_for_gold)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="clan_vault_view")]])
    await callback.message.edit_text("💰 **Введите сумму золота** для передачи в казну (одним числом):", reply_markup=kb, parse_mode="Markdown")

@router.message(ClanStates.waiting_for_gold)
async def process_donate_gold(message: Message, state: FSMContext):
    user = get_user(message.from_user.id)
    try: amount = int(message.text.strip())
    except ValueError: return await message.answer("⚠️ Пожалуйста, введите только число!")
        
    if amount <= 0: return await message.answer("⚠️ Сумма должна быть больше 0!")
    if user['gold'] < amount: return await message.answer(f"⚠️ У вас нет столько золота! (Ваш баланс: {user['gold']} 🪙)")
    
    user['gold'] -= amount
    update_user(user['user_id'], gold=user['gold'])
    
    clan = get_clan(user['clan_id'])
    update_clan(clan['clan_id'], treasury=clan.get('treasury', 0) + amount)
    
    await state.clear()
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 В казну", callback_data="clan_vault_view")]])
    await message.answer(f"✅ Вы успешно пожертвовали **{amount} 🪙** в казну клана!", reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data == "clan_donate_gems_ask")
async def ask_donate_gems(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ClanStates.waiting_for_gems)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="clan_vault_view")]])
    await callback.message.edit_text("💎 **Введите количество кристаллов** для передачи в казну (одним числом):", reply_markup=kb, parse_mode="Markdown")

@router.message(ClanStates.waiting_for_gems)
async def process_donate_gems(message: Message, state: FSMContext):
    user = get_user(message.from_user.id)
    try: amount = int(message.text.strip())
    except ValueError: return await message.answer("⚠️ Пожалуйста, введите только число!")
        
    if amount <= 0: return await message.answer("⚠️ Сумма должна быть больше 0!")
    if user.get('gems', 0) < amount: return await message.answer(f"⚠️ У вас нет столько кристаллов! (Ваш баланс: {user.get('gems', 0)} 💎)")
    
    user['gems'] -= amount
    update_user(user['user_id'], gems=user['gems'])
    
    clan = get_clan(user['clan_id'])
    vault_raw = clan.get('clan_vault', '{}')
    vault = json.loads(vault_raw) if isinstance(vault_raw, str) else vault_raw
    vault['gems'] = vault.get('gems', 0) + amount
    update_clan(clan['clan_id'], clan_vault=json.dumps(vault, ensure_ascii=False))
    
    await state.clear()
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 В казну", callback_data="clan_vault_view")]])
    await message.answer(f"✅ Вы успешно пожертвовали **{amount} 💎** в казну клана!", reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data == "clan_donate_item_list")
async def clan_donate_item_list(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    materials = user['inventory'].get('materials', {})
    if not materials:
        return await callback.answer("У вас нет ресурсов для вклада!", show_alert=True)
        
    buttons = []
    for m_id, count in list(materials.items())[:20]:
        if count > 0:
            buttons.append([InlineKeyboardButton(text=f"Внести: {get_item_name(m_id)} (1 шт)", callback_data=f"clan_don_item_{m_id}")])
            
    buttons.append([InlineKeyboardButton(text="🔙 Назад в казну", callback_data="clan_vault_view")])
    await callback.message.edit_text("📦 **Склад Клана**\nВыберите ресурс из вашего инвентаря для передачи на общий склад (передается по 1 шт):", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data.startswith("clan_don_item_"))
async def clan_donate_item_do(callback: CallbackQuery):
    m_id = callback.data.replace("clan_don_item_", "")
    user = get_user(callback.from_user.id)
    inv = user['inventory']
    materials = inv.get('materials', {})
    
    if materials.get(m_id, 0) < 1:
        return await callback.answer("У вас закончился этот предмет!", show_alert=True)
        
    materials[m_id] -= 1
    if materials[m_id] == 0: del materials[m_id]
    update_user(user['user_id'], inventory=inv)
    
    clan = get_clan(user['clan_id'])
    vault_raw = clan.get('clan_vault', '{}')
    vault = json.loads(vault_raw) if isinstance(vault_raw, str) else vault_raw
    items_vault = vault.setdefault('items', {})
    items_vault[m_id] = items_vault.get(m_id, 0) + 1
    
    update_clan(clan['clan_id'], clan_vault=json.dumps(vault, ensure_ascii=False))
    await callback.answer(f"Внесено на склад: {get_item_name(m_id)}!")
    await clan_donate_item_list(callback)

@router.callback_query(F.data == "clan_withdraw_gold_ask")
async def ask_withdraw_gold(callback: CallbackQuery, state: FSMContext):
    user = get_user(callback.from_user.id)
    if user.get('clan_role') not in ['hedwing', 'lindeman']:
        return await callback.answer("У вас нет прав!", show_alert=True)
        
    await state.set_state(ClanStates.waiting_for_withdraw_gold)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="clan_vault_view")]])
    await callback.message.edit_text("📤 **Введите сумму золота** для изъятия из казны:", reply_markup=kb, parse_mode="Markdown")

@router.message(ClanStates.waiting_for_withdraw_gold)
async def process_withdraw_gold(message: Message, state: FSMContext):
    user = get_user(message.from_user.id)
    if user.get('clan_role') not in ['hedwing', 'lindeman']:
        return await message.answer("У вас нет прав!")
        
    try: amount = int(message.text.strip())
    except ValueError: return await message.answer("⚠️ Введите число!")
    if amount <= 0: return await message.answer("⚠️ Сумма должна быть больше 0!")

    clan = get_clan(user['clan_id'])
    if clan.get('treasury', 0) < amount:
        return await message.answer(f"⚠️ В казне нет столько золота! (В казне: {clan.get('treasury', 0)} 🪙)")

    update_clan(clan['clan_id'], treasury=clan.get('treasury', 0) - amount)
    user['gold'] += amount
    update_user(user['user_id'], gold=user['gold'])

    await state.clear()
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 В казну", callback_data="clan_vault_view")]])
    await message.answer(f"✅ Вы забрали **{amount} 🪙** из казны!", reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data == "clan_withdraw_gems_ask")
async def ask_withdraw_gems(callback: CallbackQuery, state: FSMContext):
    user = get_user(callback.from_user.id)
    if user.get('clan_role') not in ['hedwing', 'lindeman']:
        return await callback.answer("У вас нет прав!", show_alert=True)
        
    await state.set_state(ClanStates.waiting_for_withdraw_gems)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="clan_vault_view")]])
    await callback.message.edit_text("💠 **Введите количество кристаллов** для изъятия из казны:", reply_markup=kb, parse_mode="Markdown")

@router.message(ClanStates.waiting_for_withdraw_gems)
async def process_withdraw_gems(message: Message, state: FSMContext):
    user = get_user(message.from_user.id)
    if user.get('clan_role') not in ['hedwing', 'lindeman']:
        return await message.answer("У вас нет прав!")
        
    try: amount = int(message.text.strip())
    except ValueError: return await message.answer("⚠️ Введите число!")
    if amount <= 0: return await message.answer("⚠️ Сумма должна быть больше 0!")

    clan = get_clan(user['clan_id'])
    vault_raw = clan.get('clan_vault', '{}')
    vault = json.loads(vault_raw) if isinstance(vault_raw, str) else vault_raw
    
    if vault.get('gems', 0) < amount:
        return await message.answer(f"⚠️ В казне нет столько кристаллов! (В казне: {vault.get('gems', 0)} 💎)")

    vault['gems'] -= amount
    update_clan(clan['clan_id'], clan_vault=json.dumps(vault, ensure_ascii=False))
    
    user['gems'] = user.get('gems', 0) + amount
    update_user(user['user_id'], gems=user['gems'])

    await state.clear()
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 В казну", callback_data="clan_vault_view")]])
    await message.answer(f"✅ Вы забрали **{amount} 💎** из казны!", reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data == "clan_withdraw_item_list")
async def clan_withdraw_item_list(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    if user.get('clan_role') not in ['hedwing', 'lindeman']:
        return await callback.answer("У вас нет прав!", show_alert=True)
        
    clan = get_clan(user['clan_id'])
    vault = json.loads(clan.get('clan_vault', '{}')) if isinstance(clan.get('clan_vault'), str) else clan.get('clan_vault', {})
    items = vault.get('items', {})

    if not items:
        return await callback.answer("Склад ресурсов пуст!", show_alert=True)

    buttons = []
    for m_id, count in list(items.items())[:20]:
        if count > 0:
            buttons.append([InlineKeyboardButton(text=f"Забрать: {get_item_name(m_id)} (1 шт)", callback_data=f"clan_take_item_{m_id}")])

    buttons.append([InlineKeyboardButton(text="🔙 Назад в казну", callback_data="clan_vault_view")])
    await callback.message.edit_text("📥 **Взять со Склада**\nВыберите ресурс (берется по 1 шт):", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data.startswith("clan_take_item_"))
async def clan_take_item_do(callback: CallbackQuery):
    m_id = callback.data.replace("clan_take_item_", "")
    user = get_user(callback.from_user.id)
    if user.get('clan_role') not in ['hedwing', 'lindeman']:
        return await callback.answer("У вас нет прав!", show_alert=True)

    clan = get_clan(user['clan_id'])
    vault_raw = clan.get('clan_vault', '{}')
    vault = json.loads(vault_raw) if isinstance(vault_raw, str) else vault_raw
    items_vault = vault.setdefault('items', {})

    if items_vault.get(m_id, 0) < 1:
        return await callback.answer("Этот предмет закончился на складе!", show_alert=True)

    items_vault[m_id] -= 1
    if items_vault[m_id] == 0: del items_vault[m_id]

    update_clan(clan['clan_id'], clan_vault=json.dumps(vault, ensure_ascii=False))

    inv = user['inventory']
    materials = inv.setdefault('materials', {})
    materials[m_id] = materials.get(m_id, 0) + 1
    update_user(user['user_id'], inventory=inv)

    await callback.answer(f"Взято со склада: {get_item_name(m_id)}!")
    await clan_withdraw_item_list(callback)

# --- ПОДМЕНЮ ПОИСКА КЛАНОВ ---
@router.callback_query(F.data == "clan_search_list")
async def show_clans_list(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    clans = get_all_clans_ranked()
    
    if not clans:
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="clan_main")]])
        return await callback.message.edit_text("🔍 **Поиск кланов**\n\nВ мире Kamaria пока нет зарегистрированных кланов.", reply_markup=kb, parse_mode="Markdown")
        
    text = "🔍 **Реестр Кланов**\nОтсортировано по активности в рейдах недели.\n\n"
    buttons = []
    for c in clans[:10]:
        rank_icon = "🥇" if c['rank'] == 1 else "🥈" if c['rank'] == 2 else "🥉" if c['rank'] == 3 else f"#{c['rank']}"
        banner = f"{c['banner']} " if c.get('banner') else ""
        text += (f"{rank_icon} **{banner}{c['name']}** (Ур. {c['level']})\n"
                 f"   └ 📊 Ср. ур.: **{c['avg_level']}** | Места: **{c['members_count']}/{c['max_members']}** (Свободно: {c['free_slots']})\n\n")
        buttons.append([InlineKeyboardButton(text=f"{rank_icon} {banner}{c['name']} (Свободно: {c['free_slots']})", callback_data=f"clan_view_{c['clan_id']}")])
        
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="clan_main")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data.startswith("clan_view_"))
async def view_clan_card(callback: CallbackQuery):
    clan_id = int(callback.data.replace("clan_view_", ""))
    user = get_user(callback.from_user.id)
    clans = get_all_clans_ranked()
    
    clan_info = next((c for c in clans if c['clan_id'] == clan_id), None)
    if not clan_info: return await callback.answer("Клан не найден!", show_alert=True)
        
    rank_icon = "🥇" if clan_info['rank'] == 1 else "🥈" if clan_info['rank'] == 2 else "🥉" if clan_info['rank'] == 3 else f"#{clan_info['rank']}"
    banner = f"{clan_info['banner']} " if clan_info.get('banner') else ""
    
    text = (
        f"🛡️ **Клан: {banner}{clan_info['name']}**\n\n"
        f"Позиция в рейтинге рейдов: **{rank_icon}**\n"
        f"Уровень клана: **{clan_info['level']}**\n"
        f"Средний уровень бойцов: **{clan_info['avg_level']}**\n"
        f"Вместимость: **{clan_info['members_count']} / {clan_info['max_members']}**\n"
        f"Свободных мест: **{clan_info['free_slots']}**\n"
    )
    
    buttons = []
    if user.get('clan_id', 0) == 0:
        if clan_info['free_slots'] > 0:
            if user['user_id'] in clan_info['join_requests']:
                buttons.append([InlineKeyboardButton(text="⏳ Заявка уже отправлена", callback_data="clan_noop")])
            else:
                buttons.append([InlineKeyboardButton(text="📨 Подать заявку", callback_data=f"clan_apply_{clan_id}")])
        else:
            buttons.append([InlineKeyboardButton(text="⛔ Нет свободных мест", callback_data="clan_noop")])
            
    buttons.append([InlineKeyboardButton(text="🔙 К списку кланов", callback_data="clan_search_list")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data == "clan_noop")
async def clan_noop(callback: CallbackQuery):
    await callback.answer()

@router.callback_query(F.data.startswith("clan_apply_"))
async def apply_to_clan(callback: CallbackQuery):
    clan_id = int(callback.data.replace("clan_apply_", ""))
    user = get_user(callback.from_user.id)
    
    if user.get('clan_id', 0) != 0: return await callback.answer("Вы уже состоите в клане!", show_alert=True)
    clan = get_clan(clan_id)
    if not clan: return await callback.answer("Клан не найден!", show_alert=True)
        
    reqs = clan.get('join_requests', [])
    if user['user_id'] not in reqs:
        reqs.append(user['user_id'])
        update_clan(clan_id, join_requests=reqs)
        await callback.answer("Заявка отправлена лидеру!", show_alert=True)
    else:
        await callback.answer("Вы уже отправляли заявку!", show_alert=True)
        
    await view_clan_card(callback)

@router.callback_query(F.data == "clan_requests_view")
async def view_clan_requests(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    clan = get_clan(user.get('clan_id', 0))
    if not clan or clan['leader_id'] != user['user_id']:
        return await callback.answer("Только лидер может управлять заявками!", show_alert=True)
        
    reqs = clan.get('join_requests', [])
    if not reqs:
        return await callback.message.edit_text("Заявок нет.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 В клан", callback_data="clan_my_info")]]))
        
    buttons = []
    text = "📬 **Входящие заявки на вступление:**\n\n"
    for applicant_id in reqs[:8]:
        app_user = get_user(applicant_id)
        if app_user:
            text += f"• **{app_user['username']}** (Ур. {app_user.get('level', 1)})\n"
            buttons.append([
                InlineKeyboardButton(text=f"✅ Принять {app_user['username']}", callback_data=f"clan_accept_{applicant_id}"),
                InlineKeyboardButton(text="❌", callback_data=f"clan_reject_{applicant_id}")
            ])
            
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="clan_my_info")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data.startswith("clan_accept_"))
async def accept_clan_request(callback: CallbackQuery):
    app_id = int(callback.data.replace("clan_accept_", ""))
    user = get_user(callback.from_user.id)
    clan_id = user.get('clan_id', 0)
    clan = get_clan(clan_id)
    
    if not clan or clan['leader_id'] != user['user_id']: return await callback.answer("Ошибка доступа!", show_alert=True)
    max_m = 5 + clan['level'] * 5
    members = get_clan_members(clan_id)
    if len(members) >= max_m: return await callback.answer("В клане больше нет мест!", show_alert=True)
        
    reqs = clan.get('join_requests', [])
    if app_id in reqs:
        reqs.remove(app_id)
        update_clan(clan_id, join_requests=reqs)
        
    update_user(app_id, clan_id=clan_id, clan_role='thrall')
    await callback.answer("Игрок принят в клан!")
    await view_clan_requests(callback)

@router.callback_query(F.data.startswith("clan_reject_"))
async def reject_clan_request(callback: CallbackQuery):
    app_id = int(callback.data.replace("clan_reject_", ""))
    user = get_user(callback.from_user.id)
    clan_id = user.get('clan_id', 0)
    clan = get_clan(clan_id)
    
    if clan and clan['leader_id'] == user['user_id']:
        reqs = clan.get('join_requests', [])
        if app_id in reqs:
            reqs.remove(app_id)
            update_clan(clan_id, join_requests=reqs)
    await callback.answer("Заявка отклонена.")
    await view_clan_requests(callback)

@router.callback_query(F.data == "clan_leave_confirm")
async def clan_leave_confirm(callback: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚪 Да, выйти", callback_data="clan_leave_do")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="clan_my_info")]
    ])
    await callback.message.edit_text("⚠️ **Вы действительно хотите покинуть клан?**", reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data == "clan_leave_do")
async def clan_leave_do(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    clan_id = user.get('clan_id', 0)
    clan = get_clan(clan_id)
    
    if clan and clan['leader_id'] == user['user_id']:
        return await callback.answer("Лидер не может просто выйти! Сначала передайте лидерство или распустите клан.", show_alert=True)
        
    update_user(user['user_id'], clan_id=0, clan_role='thrall')
    await callback.answer("Вы покинули клан.", show_alert=True)
    await clan_main_menu(callback, None)

