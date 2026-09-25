import json
import random
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from database import get_connection, get_user, update_user, check_and_generate_quests, get_unlocked_titles, get_top_clans, get_recent_global_events, simulate_bot_activity, get_clan, get_all_home_skins

router = Router()

def ensure_user(user_id: int, username: str):
    user = get_user(user_id)
    if not user:
        with get_connection() as conn:
            conn.cursor().execute(
                "INSERT INTO users (user_id, username, state, hp, max_hp, gold) VALUES (?, ?, 'STATE_TOWN', 100, 100, 50)",
                (user_id, username)
            )
            conn.commit()
        user = get_user(user_id)
    return user

def get_town_kb(user: dict) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚔️ Экспедиции", callback_data="town_dungeon_menu"),
         InlineKeyboardButton(text="🏟️ Арена (PvP)", callback_data="town_arena")],
        [InlineKeyboardButton(text="🎒 Инвентарь", callback_data="inv_open"),
         InlineKeyboardButton(text="🏰 Кланы", callback_data="clan_main")],
        [InlineKeyboardButton(text="🔨 Мастерская", callback_data="town_craft"),
         InlineKeyboardButton(text="🧪 Алхимия", callback_data="town_alchemy")],
        [InlineKeyboardButton(text="⚖️ Торговец", callback_data="town_market"),
         InlineKeyboardButton(text="🎲 Таверна", callback_data="town_tavern")],
        [InlineKeyboardButton(text="🏡 Мой Дом", callback_data="town_home")]
    ])
    return kb

def generate_town_text(user: dict) -> str:
    simulate_bot_activity() 
    
    xp = user.get('xp', 0)
    lvl = user.get('level', 1)
    max_xp = lvl * 100
    
    filled = min(10, int((xp / max_xp) * 10))
    xp_bar = "█" * filled + "░" * (10 - filled)
    
    top_clans = get_top_clans(limit=3)
    clans_text = ""
    if top_clans:
        clans_text = "\n\n🏆 **Топ-3 кланов недели:**\n"
        medals = ["🥇", "🥈", "🥉"]
        for i, clan in enumerate(top_clans):
            icon = medals[i] if i < len(medals) else "🏅"
            banner_str = f"{clan.get('banner', '')} " if clan.get('banner') else ""
            clans_text += f"{icon} {banner_str}{clan['name']} (Рейды: {clan['weekly_raids']})\n"
    else:
        clans_text = "\n\n🏆 **Топ-3 кланов недели:**\nПока нет активных кланов."
        
    events = get_recent_global_events(5)
    log_text = "\n\n📰 **Вестник Камарии:**\n"
    if events:
        for e in events: log_text += f"• {e}\n"
    else:
        log_text += "• В мире всё спокойно...\n"
        
    clan_str = ""
    clan_id = user.get('clan_id', 0)
    if clan_id != 0:
        clan = get_clan(clan_id)
        if clan:
            banner = clan.get('banner', '')
            b_text = f"{banner} " if banner else ""
            clan_str = f"\n🛡️ Клан: **{b_text}{clan['name']}** (Ур. {clan['level']})"
    
    return (
        f"🏕️ **Лагерь Искателей (Камария)**\n\n"
        f"👤 **{user['username']}** | Ур. {lvl}{clan_str}\n"
        f"🌟 Опыт: `{xp_bar}` {xp}/{max_xp} XP\n"
        f"❤️ ХП: {user['hp']}/{user['max_hp']} | ⚡ ОД: {user.get('energy', 5)}/{user.get('max_energy', 5)}\n"
        f"💰 Золото: {user.get('gold', 0)} 🪙 | 💎 Кристаллы: {user.get('gems', 0)} 💎"
        f"{clans_text}"
        f"{log_text}\n"
        "Куда отправимся?"
    )

@router.message(Command("start", "town"))
async def cmd_start(message: Message):
    user = ensure_user(message.from_user.id, message.from_user.username or "Игрок")
    text = generate_town_text(user)
    msg = await message.answer(text, reply_markup=get_town_kb(user), parse_mode="Markdown")
    update_user(user['user_id'], state='STATE_TOWN', last_msg_id=msg.message_id)

@router.callback_query(F.data == "town_back")
async def cb_town_back(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    text = generate_town_text(user)
    try:
        msg = await callback.message.edit_text(text, reply_markup=get_town_kb(user), parse_mode="Markdown")
        update_user(user['user_id'], state='STATE_TOWN', last_msg_id=callback.message.message_id)
    except Exception:
        update_user(user['user_id'], state='STATE_TOWN')
    await callback.answer()

@router.callback_query(F.data == "town_home")
async def cb_town_home(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    home_data = user.get('home_data', {})
    stats = home_data.get('stats', {})
    
    skins = get_all_home_skins()
    skin_id = home_data.get("skin", "base")
    skin_info = skins.get(skin_id, {})
    skin_name = skin_info.get("name", "Базовый шатер")
    
    skin_desc = skin_info.get("desc", "")
    if not skin_desc or skin_desc.startswith("Убить") or skin_desc.startswith("Титул"):
        skin_desc = "Ветер колышет полог, а в котелке булькает сытная похлебка."
        
    active_title = home_data.get('active_title', 'Новичок')
    active_medal = home_data.get('active_medal', 'Нет медалей')

    quests = check_and_generate_quests(user['user_id'])
    q_text = ""
    for q in quests.get("quests", []):
        status = "✅" if q["completed"] else f"{q['progress']}/{q['target']}"
        q_text += f"• {q['desc']} [{status}]\n"
        
    clan_id = user.get('clan_id', 0)
    clan_tag = ""
    if clan_id != 0:
        clan = get_clan(clan_id)
        if clan and clan.get('banner'):
            clan_tag = f"[{clan['banner']}] "
            
    text = (
        f"🏡 **Ваш Дом** *(Оформление: {skin_name})*\n"
        f"_{skin_desc}_\n\n"
        f"Титул {clan_tag}{user['username']}: **{active_title}**\n"
        f"Известный как обладатель медали: **{active_medal}**\n\n"
        f"📅 **Задания на сегодня:**\n{q_text}\n"
        f"📊 **Статистика:**\n"
        f"└ Убито монстров: {stats.get('mobs_killed', 0)}\n"
        f"└ Повержено боссов: {stats.get('bosses_killed', 0)}\n"
        f"└ Побед в PvP: {stats.get('pvp_wins', 0)}\n"
        f"└ Смертей: {stats.get('deaths_count', 0)}"
    )
    
    all_quests_completed = len(quests.get("quests", [])) > 0 and all(q.get("completed") for q in quests.get("quests", []))
    already_claimed = quests.get("claimed", False)
    
    buttons = []
    if all_quests_completed and not already_claimed:
        buttons.append([InlineKeyboardButton(text="🎁 Забрать награду за дейлики", callback_data="town_claim_daily")])
        
    buttons.append([
        InlineKeyboardButton(text="📜 Выбрать титул", callback_data="town_home_titles"),
        InlineKeyboardButton(text="🎖 Выбрать медаль", callback_data="town_home_medals")
    ])
    buttons.append([InlineKeyboardButton(text="🎨 Настройки дома (Скины)", callback_data="town_home_settings")])
    buttons.append([InlineKeyboardButton(text="🔙 В лагерь", callback_data="town_back")])
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data == "town_home_titles")
async def cb_town_home_titles(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    home_data = user.get('home_data', {})
    titles = get_unlocked_titles(home_data)
    
    text = "📜 **Ваши разблокированные титулы:**\nВыберите один для отображения в профиле."
    buttons = []
    
    for t in titles:
        btn_text = f"✅ {t}" if t == home_data.get('active_title') else t
        buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"home_set_title:{t}")])
        
    buttons.append([InlineKeyboardButton(text="🔙 Назад в Дом", callback_data="town_home")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data.startswith("home_set_title:"))
async def cb_home_set_title(callback: CallbackQuery):
    title = callback.data.split(":")[1]
    user = get_user(callback.from_user.id)
    home_data = user.get('home_data', {})
    
    if title in get_unlocked_titles(home_data):
        home_data['active_title'] = title
        update_user(user['user_id'], home_data=home_data)
        await callback.answer(f"Титул '{title}' установлен!")
        
    await cb_town_home_titles(callback)

@router.callback_query(F.data == "town_home_medals")
async def cb_town_home_medals(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    home_data = user.get('home_data', {})
    medals = home_data.get('medals', [])
    
    text = "🎖 **Ваши боевые медали:**\n"
    buttons = []
    
    if not medals:
        text += "У вас пока нет медалей. Участвуйте в Войне за Камарию, чтобы получать их!"
    else:
        text += "Выберите одну для отображения в профиле."
        for idx, m in enumerate(medals):
            btn_text = f"✅ {m}" if m == home_data.get('active_medal') else m
            buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"home_set_medal:{idx}")])
            
    buttons.append([InlineKeyboardButton(text="🔙 Назад в Дом", callback_data="town_home")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data.startswith("home_set_medal:"))
async def cb_home_set_medal(callback: CallbackQuery):
    idx = int(callback.data.split(":")[1])
    user = get_user(callback.from_user.id)
    home_data = user.get('home_data', {})
    medals = home_data.get('medals', [])
    
    if 0 <= idx < len(medals):
        home_data['active_medal'] = medals[idx]
        update_user(user['user_id'], home_data=home_data)
        await callback.answer(f"Медаль установлена!")
        
    await cb_town_home_medals(callback)

@router.callback_query(F.data == "town_claim_daily")
async def cb_town_claim_daily(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    quests = check_and_generate_quests(user['user_id'])
    
    if quests.get("claimed"):
        return await callback.answer("Вы уже забрали награду сегодня!", show_alert=True)
        
    quests["claimed"] = True
    reward_gold = 150
    reward_gems = 5
    
    user['gold'] += reward_gold
    user['gems'] = user.get('gems', 0) + reward_gems
    
    update_user(user['user_id'], gold=user['gold'], gems=user['gems'], quests_data=quests)
    await callback.answer(f"🎁 Получено {reward_gold} 🪙 и {reward_gems} 💎!", show_alert=True)
    await cb_town_home(callback)

@router.callback_query(F.data == "town_home_settings")
async def cb_town_home_settings(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    home_data = user.get('home_data', {})
    
    unlocked = home_data.get("unlocked_skins", ["base"])
    current_skin = home_data.get("skin", "base")
    skins = get_all_home_skins()
    text = "🎨 **Архитектура и оформление**\n\nВыберите внешний вид вашего жилища.\n\n"
    buttons = []
    
    for skin_id, skin_info in skins.items():
        name = skin_info["name"]
        
        if skin_id == current_skin:
            status_text = "✅ Экипировано"
            cb_data = "ignore"
        elif skin_id in unlocked:
            status_text = "🔓 Доступно"
            cb_data = f"home_skin_equip:{skin_id}"
        else:
            if skin_info["type"] == "gold":
                status_text = f"💰 {skin_info['price']} 🪙"
                cb_data = f"home_skin_buy:{skin_id}"
            elif skin_info["type"] == "gems":
                status_text = f"💎 {skin_info['price']} 💎"
                cb_data = f"home_skin_buy:{skin_id}"
            elif skin_info["type"] == "achievement":
                status_text = f"🔒 {skin_info['desc']}"
                cb_data = f"home_skin_unlock:{skin_id}"
        
        text += f"• **{name}** — {status_text}\n"
        if cb_data != "ignore":
            btn_text = f"{name} ({status_text.split(' ')[0]})" if "🔒" not in status_text else f"Разблокировать {name}"
            buttons.append([InlineKeyboardButton(text=btn_text, callback_data=cb_data)])

    buttons.append([InlineKeyboardButton(text="🔙 Назад в Дом", callback_data="town_home")])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data.startswith("home_skin_"))
async def cb_town_skin_action(callback: CallbackQuery):
    prefix, skin_id = callback.data.split(":")
    action = prefix.split("_")[-1]
    
    skins = get_all_home_skins()
    skin_info = skins.get(skin_id)
    
    if not skin_info:
        return await callback.answer("Скин не найден!", show_alert=True)
        
    user = get_user(callback.from_user.id)
    home_data = user.get('home_data', {})
    unlocked = home_data.setdefault("unlocked_skins", ["base"])
    
    if action == "equip":
        if skin_id in unlocked:
            home_data["skin"] = skin_id
            update_user(user['user_id'], home_data=home_data)
            await callback.answer(f"Скин '{skin_info['name']}' установлен!")
        else:
            await callback.answer("Этот скин вам недоступен.", show_alert=True)
            
    elif action == "buy":
        price = skin_info.get("price", 0)
        currency = skin_info["type"]
        
        if currency == "gold" and user.get("gold", 0) >= price:
            user["gold"] -= price
            unlocked.append(skin_id)
            update_user(user['user_id'], gold=user["gold"], home_data=home_data)
            await callback.answer(f"Вы купили '{skin_info['name']}'!")
        elif currency == "gems" and user.get("gems", 0) >= price:
            user["gems"] -= price
            unlocked.append(skin_id)
            update_user(user['user_id'], gems=user["gems"], home_data=home_data)
            await callback.answer(f"Вы купили '{skin_info['name']}'!")
        else:
            return await callback.answer("Недостаточно средств!", show_alert=True)
            
    elif action == "unlock":
        stats = home_data.get('stats', {})
        titles = get_unlocked_titles(home_data)
        clan_id = user.get('clan_id', 0)
        can_unlock, error_msg = True, "Условия не выполнены."
        
        if "req_level" in skin_info and user.get("level", 1) < skin_info["req_level"]:
            can_unlock, error_msg = False, f"Требуется уровень: {skin_info['req_level']}"
        elif "req_mobs" in skin_info and stats.get("mobs_killed", 0) < skin_info["req_mobs"]:
            can_unlock, error_msg = False, f"Нужно убить монстров: {skin_info['req_mobs']}"
        elif "req_bosses" in skin_info and stats.get("bosses_killed", 0) < skin_info["req_bosses"]:
            can_unlock, error_msg = False, f"Нужно убить боссов: {skin_info['req_bosses']}"
        elif "req_pvp_wins" in skin_info and stats.get("pvp_wins", 0) < skin_info["req_pvp_wins"]:
            can_unlock, error_msg = False, f"Побед на Арене: {skin_info['req_pvp_wins']}"
        elif "req_war_clears" in skin_info and stats.get("war_clears", 0) < skin_info["req_war_clears"]:
            can_unlock, error_msg = False, f"Зачисток в войне: {skin_info['req_war_clears']}"
        elif "req_deaths" in skin_info and stats.get("deaths_count", 0) < skin_info["req_deaths"]:
            can_unlock, error_msg = False, f"Смертей: {skin_info['req_deaths']}"
        elif "req_title" in skin_info and skin_info["req_title"] not in titles:
            can_unlock, error_msg = False, f"Требуется титул: {skin_info['req_title']}"
        elif "req_clan_lvl" in skin_info:
            if clan_id == 0: can_unlock, error_msg = False, "Вы не состоите в клане!"
            else:
                clan = get_clan(clan_id)
                if not clan or clan.get("level", 1) < skin_info["req_clan_lvl"]:
                    can_unlock, error_msg = False, f"Требуется Клан {skin_info['req_clan_lvl']} уровня"

        if can_unlock:
            unlocked.append(skin_id)
            update_user(user['user_id'], home_data=home_data)
            await callback.answer(f"Скин '{skin_info['name']}' разблокирован!", show_alert=True)
        else:
            return await callback.answer(error_msg, show_alert=True)

    await cb_town_home_settings(callback)

