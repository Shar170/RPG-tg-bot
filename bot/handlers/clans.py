import json
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from database import (
    get_user, update_user, get_clan, update_clan, 
    get_clan_by_name, get_all_clans_ranked, get_clan_members,
    get_connection, get_clan_creation_requirements
)

router = Router()

class ClanCreateStates(StatesGroup):
    waiting_for_name = State()

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
    await state.clear()
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
        c_name = clan['name'] if clan else "Неизвестно"
        text += f"Вы состоите в клане: **{c_name}**"
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
    
    # Проверки по динамическим требованиям
    if reqs["min_level"] > 0 and user_lvl < reqs["min_level"]:
        return await callback.answer(f"⛔ Недостаточный уровень! Требуется {reqs['min_level']} ур. (у вас {user_lvl}).", show_alert=True)
        
    if reqs["cost_gems"] > 0 and user_gems < reqs["cost_gems"]:
        return await callback.answer(f"⛔ Недостаточно кристаллов! Требуется {reqs['cost_gems']} 💎 (у вас {user_gems} 💎).", show_alert=True)
        
    if reqs["cost_gold"] > 0 and user_gold < reqs["cost_gold"]:
        return await callback.answer(f"⛔ Недостаточно золота! Требуется {reqs['cost_gold']} 🪙 (у вас {user_gold} 🪙).", show_alert=True)
        
    req_lines = []
    if reqs["min_level"] > 0:
        req_lines.append(f"• Уровень: **{reqs['min_level']}** ✅")
    if reqs["cost_gems"] > 0:
        req_lines.append(f"• Стоимость: **{reqs['cost_gems']} 💎**")
    if reqs["cost_gold"] > 0:
        req_lines.append(f"• Стоимость: **{reqs['cost_gold']} 🪙**")
        
    req_display = "\n".join(req_lines) if req_lines else "• Без особых требований"

    await state.set_state(ClanCreateStates.waiting_for_name)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="clan_main")]])
    await callback.message.edit_text(
        f"🏰 **Основание нового Клана**\n\n"
        f"{req_display}\n\n"
        f"Введите название для вашего клана (от 3 до 20 символов):", 
        reply_markup=kb, 
        parse_mode="Markdown"
    )

@router.message(ClanCreateStates.waiting_for_name)
async def clan_create_name_input(message: Message, state: FSMContext):
    name = message.text.strip()
    user = get_user(message.from_user.id)
    reqs = get_clan_creation_requirements()
    
    if len(name) < 3 or len(name) > 20:
        return await message.answer("⚠️ Название должно быть от 3 до 20 символов! Попробуйте снова:")
        
    if get_clan_by_name(name):
        return await message.answer("⚠️ Клан с таким названием уже существует! Придумайте другое:")
        
    if reqs["min_level"] > 0 and user.get('level', 1) < reqs["min_level"]:
        await state.clear()
        return await message.answer(f"⛔ Недостаточный уровень (нужен {reqs['min_level']} ур.)!")
        
    if reqs["cost_gems"] > 0 and user.get('gems', 0) < reqs["cost_gems"]:
        await state.clear()
        return await message.answer(f"⛔ Не хватает кристаллов (нужно {reqs['cost_gems']} 💎)!")
        
    if reqs["cost_gold"] > 0 and user.get('gold', 0) < reqs["cost_gold"]:
        await state.clear()
        return await message.answer(f"⛔ Не хватает золота (нужно {reqs['cost_gold']} 🪙)!")
        
    # Создание клана
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO clans (name, leader_id, level, treasury, weekly_raids, join_requests, clan_vault) VALUES (?, ?, 1, 0, 0, '[]', '{\"gems\": 0}')",
            (name, user['user_id'])
        )
        new_clan_id = cur.lastrowid
        conn.commit()
        
    # Списание ресурсов согласно настройкам
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
async def show_my_clan(callback: CallbackQuery):
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
    
    text = (
        f"🏰 **Клан: {clan['name']}**\n\n"
        f"Уровень: **{clan['level']}**\n"
        f"Бойцов: **{len(members)} / {max_m}**\n\n"
        f"👥 **Состав клана:**\n{members_text}\n"
    )
    if is_leader and reqs_count > 0:
        text += f"📬 **Входящие заявки:** {reqs_count} шт.\n"
        
    buttons = []
    if is_leader and reqs_count > 0:
        buttons.append([InlineKeyboardButton(text=f"📬 Заявки ({reqs_count})", callback_data="clan_requests_view")])
    buttons.append([InlineKeyboardButton(text="📦 Казна и Склад", callback_data="clan_vault_view")])
    buttons.append([InlineKeyboardButton(text="🚪 Покинуть клан", callback_data="clan_leave_confirm")])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="clan_main")])
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

# --- ПОДМЕНЮ ПОИСКА КЛАНОВ ---
@router.callback_query(F.data == "clan_search_list")
async def show_clans_list(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    clans = get_all_clans_ranked()
    
    if not clans:
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="clan_main")]])
        return await callback.message.edit_text("🔍 **Поиск кланов**\n\nВ мире Kamaria пока нет зарегистрированных кланов.", reply_markup=kb, parse_mode="Markdown")
        
    text = (
        "🔍 **Реестр Кланов**\n"
        "Отсортировано по активности в рейдах недели.\n\n"
    )
    
    buttons = []
    for c in clans[:10]:
        rank_icon = "🥇" if c['rank'] == 1 else "🥈" if c['rank'] == 2 else "🥉" if c['rank'] == 3 else f"#{c['rank']}"
        text += (
            f"{rank_icon} **{c['name']}** (Ур. {c['level']})\n"
            f"   └ 📊 Ср. ур.: **{c['avg_level']}** | Места: **{c['members_count']}/{c['max_members']}** (Свободно: {c['free_slots']})\n\n"
        )
        buttons.append([InlineKeyboardButton(text=f"{rank_icon} {c['name']} (Свободно: {c['free_slots']})", callback_data=f"clan_view_{c['clan_id']}")])
        
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="clan_main")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

# --- КАРТОЧКА КЛАНА И ПОДАЧА ЗАЯВКИ ---
@router.callback_query(F.data.startswith("clan_view_"))
async def view_clan_card(callback: CallbackQuery):
    clan_id = int(callback.data.replace("clan_view_", ""))
    user = get_user(callback.from_user.id)
    clans = get_all_clans_ranked()
    
    clan_info = next((c for c in clans if c['clan_id'] == clan_id), None)
    if not clan_info:
        return await callback.answer("Клан не найден!", show_alert=True)
        
    rank_icon = "🥇" if clan_info['rank'] == 1 else "🥈" if clan_info['rank'] == 2 else "🥉" if clan_info['rank'] == 3 else f"#{clan_info['rank']}"
    
    text = (
        f"🛡️ **Клан: {clan_info['name']}**\n\n"
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
    
    if user.get('clan_id', 0) != 0:
        return await callback.answer("Вы уже состоите в клане!", show_alert=True)
        
    clan = get_clan(clan_id)
    if not clan:
        return await callback.answer("Клан не найден!", show_alert=True)
        
    reqs = clan.get('join_requests', [])
    if user['user_id'] not in reqs:
        reqs.append(user['user_id'])
        update_clan(clan_id, join_requests=reqs)
        await callback.answer("Заявка отправлена лидеру!", show_alert=True)
    else:
        await callback.answer("Вы уже отправляли заявку!", show_alert=True)
        
    await view_clan_card(callback)

# --- УПРАВЛЕНИЕ ЗАЯВКАМИ (ЛИДЕР) ---
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
    
    if not clan or clan['leader_id'] != user['user_id']:
        return await callback.answer("Ошибка доступа!", show_alert=True)
        
    max_m = 5 + clan['level'] * 5
    members = get_clan_members(clan_id)
    if len(members) >= max_m:
        return await callback.answer("В клане больше нет мест!", show_alert=True)
        
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

# --- КАЗНА И СКЛАД (ПРИЗЫ ЗА ТОП) ---
@router.callback_query(F.data == "clan_vault_view")
async def show_clan_vault(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    clan_id = user.get('clan_id', 0)
    if clan_id == 0:
        return await callback.answer("Вы не состоите в клане!", show_alert=True)
        
    clan = get_clan(clan_id)
    vault = clan.get('clan_vault', {})
    if isinstance(vault, str):
        try: vault = json.loads(vault)
        except: vault = {}
        
    gems_in_vault = vault.get("gems", 0)
    gold_in_vault = clan.get("treasury", 0)
    
    text = (
        f"📦 **Общак (Казна) клана {clan['name']}**\n\n"
        f"💰 Золото казны: **{gold_in_vault}** 🪙\n"
        f"💎 Кристаллы казны: **{gems_in_vault}** 💎\n\n"
        "*(Кристаллы начисляются каждый понедельник призерам Топ-3 рейтинга рейдов)*"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="clan_my_info")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

# --- ВЫХОД ИЗ КЛАНА ---
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
