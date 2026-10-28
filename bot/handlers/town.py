import json
import random
import time
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from database import (
    get_connection, get_user, update_user, check_and_generate_quests, 
    get_unlocked_titles, get_top_clans, get_recent_global_events, 
    simulate_bot_activity, get_clan, get_all_home_skins, get_online_users,
    get_player_max_energy, get_medal_display, track_daily_visit
)
from i18n import t, t_plural
from utils.titles import TITLE_NOVICE, get_title_display, get_medal_category, normalize_title

router = Router()

# Лёгкий TTL-кэш для «Вестника» и топ-кланов: город перерисовывается очень часто
_TOWN_CACHE = {}
_TOWN_CACHE_TTL = 30

def _cached(key: str, loader):
    now = time.time()
    ts, value = _TOWN_CACHE.get(key, (0, None))
    if now - ts < _TOWN_CACHE_TTL:
        return value
    value = loader()
    _TOWN_CACHE[key] = (now, value)
    return value

def ensure_user(user_id: int, username: str):
    user = get_user(user_id)
    if not user:
        with get_connection() as conn:
            conn.cursor().execute(
                "INSERT INTO users (user_id, username, state, hp, max_hp, gold, language) VALUES (?, ?, 'STATE_TOWN', 100, 100, 50, 'ru')",
                (user_id, username)
            )
            conn.commit()
        user = get_user(user_id)
    elif not user.get("language"):
        # Старые аккаунты без языка: базовый язык — русский, дальше только /language.
        user["language"] = "ru"
        update_user(user_id, language="ru")
    return user

def get_town_kb(user: dict) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("town.btn.story"), callback_data="town_story_enter")],
        [InlineKeyboardButton(text=t("town.btn.expeditions"), callback_data="town_dungeon_menu"),
         InlineKeyboardButton(text=t("town.btn.arena"), callback_data="town_arena")],
        [InlineKeyboardButton(text=t("town.btn.inventory"), callback_data="inv_open"),
         InlineKeyboardButton(text=t("town.btn.clans"), callback_data="clan_main")],
        [InlineKeyboardButton(text=t("town.btn.craft"), callback_data="town_craft"),
         InlineKeyboardButton(text=t("town.btn.alchemy"), callback_data="town_alchemy")],
        [InlineKeyboardButton(text=t("town.btn.market"), callback_data="town_market"),
         InlineKeyboardButton(text=t("town.btn.tavern"), callback_data="town_tavern")],
        [InlineKeyboardButton(text=t("town.btn.home"), callback_data="town_home")]
    ])
    return kb

def generate_town_text(user: dict) -> str:
    simulate_bot_activity() 
    
    xp = user.get('xp', 0)
    lvl = user.get('level', 1)
    max_xp = lvl * 100
    
    filled = min(10, int((xp / max_xp) * 10))
    xp_bar = "█" * filled + "░" * (10 - filled)
    
    top_clans = _cached("top_clans", lambda: get_top_clans(limit=3))
    clans_text = ""
    if top_clans:
        clans_text = t("town.top.title")
        medals = ["🥇", "🥈", "🥉"]
        for i, clan in enumerate(top_clans):
            icon = medals[i] if i < len(medals) else "🏅"
            banner_str = f"{clan.get('banner', '')} " if clan.get('banner') else ""
            clans_text += t("town.top.line", icon=icon, banner=banner_str, name=clan['name'], raids=clan['weekly_raids'])
    else:
        clans_text = t("town.top.title") + t("town.top.empty")
        
    events = _cached("events", lambda: get_recent_global_events(5))
    log_text = t("town.news.title")
    if events:
        for e in events: log_text += t("town.news.line", event=e)
    else:
        log_text += t("town.news.empty")
        
    clan_str = ""
    clan_id = user.get('clan_id', 0)
    if clan_id != 0:
        clan = get_clan(clan_id)
        if clan:
            banner = clan.get('banner', '')
            b_text = f"{banner} " if banner else ""
            clan_str = t("town.clan", banner=b_text, name=clan['name'], level=clan['level'])
            
    # Получаем правильную максимальную энергию на основе уровня игрока
    max_energy = get_player_max_energy(lvl)
    
    return (
        t("town.title")
        + t(
            "town.profile",
            name=user['username'],
            level=lvl,
            xp_bar=xp_bar,
            xp=xp,
            max_xp=max_xp,
            hp=user['hp'],
            max_hp=user['max_hp'],
            energy=user.get('energy', 5),
            max_energy=max_energy,
            gold=user.get('gold', 0),
            gems=user.get('gems', 0),
        )
        + clan_str
        + clans_text
        + log_text
        + t("town.prompt")
    )

# --- КОМАНДА ПРОСМОТРА ОНЛАЙНА ---
@router.message(Command("online"))
async def cmd_online(message: Message):
    count, names = get_online_users(15) # Онлайн за последние 15 минут
    if count == 0:
        text = t("online.none")
    else:
        text = t_plural("online.title", count, count=count, names=", ".join(names))
    await message.answer(text, parse_mode="Markdown")

@router.message(Command("start", "town"))
async def cmd_start(message: Message):
    user = ensure_user(
        message.from_user.id,
        message.from_user.username or "Игрок",
    )
    # Для нового аккаунта middleware ещё не видел записи в users.
    track_daily_visit(user['user_id'])
    user = get_user(user['user_id']) or user
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
        
    active_title = home_data.get('active_title') or TITLE_NOVICE
    active_medal_id = home_data.get('active_medal')
    active_medal = get_medal_display(active_medal_id) if active_medal_id else t("home.no_medal")

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
        t("home.title", skin=skin_name) + "\n"
        + t("home.desc", desc=skin_desc) + "\n\n"
        + t("home.title_line", clan_tag=clan_tag, name=user['username'], title=get_title_display(active_title)) + "\n"
        + t("home.medal_line", medal=active_medal) + "\n\n"
        + t("home.quests", quests=q_text) + "\n"
        + t(
            "home.stats",
            mobs=stats.get('mobs_killed', 0),
            bosses=stats.get('bosses_killed', 0),
            pvp=stats.get('pvp_wins', 0),
            deaths=stats.get('deaths_count', 0),
        )
        + t(
            "home.streak_line",
            streak=user.get('visit_streak', 0),
            best=user.get('best_visit_streak', 0),
        )
    )
    
    all_quests_completed = len(quests.get("quests", [])) > 0 and all(q.get("completed") for q in quests.get("quests", []))
    already_claimed = quests.get("claimed", False)
    
    buttons = []
    if all_quests_completed and not already_claimed:
        buttons.append([InlineKeyboardButton(text=t("home.claim"), callback_data="town_claim_daily")])
        
    buttons.append([
        InlineKeyboardButton(text=t("home.btn.titles"), callback_data="town_home_titles"),
        InlineKeyboardButton(text=t("home.btn.medals"), callback_data="town_home_medals")
    ])
    buttons.append([InlineKeyboardButton(text=t("home.btn.collection"), callback_data="collection_main")])
    buttons.append([InlineKeyboardButton(text=t("home.btn.skins"), callback_data="town_home_settings")])
    buttons.append([InlineKeyboardButton(text=t("home.btn.back"), callback_data="town_back")])
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data == "town_home_titles")
async def cb_town_home_titles(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    home_data = user.get('home_data', {})
    titles = get_unlocked_titles(home_data)
    active_title = normalize_title(home_data.get('active_title'))
    
    text = t("home.titles_text")
    buttons = []
    
    for title_id in titles:
        label = get_title_display(title_id)
        btn_text = f"✅ {label}" if title_id == active_title else label
        buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"home_set_title:{title_id}")])
        
    buttons.append([InlineKeyboardButton(text=t("home.titles_back"), callback_data="town_home")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data.startswith("home_set_title:"))
async def cb_home_set_title(callback: CallbackQuery):
    title_id = callback.data.split(":", 1)[1]
    user = get_user(callback.from_user.id)
    home_data = user.get('home_data', {})
    
    if title_id in get_unlocked_titles(home_data):
        home_data['active_title'] = title_id
        update_user(user['user_id'], home_data=home_data)
        await callback.answer(t("home.title_set", title=get_title_display(title_id)))
        
    await cb_town_home_titles(callback)

@router.callback_query(F.data == "town_home_medals")
async def cb_town_home_medals(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    home_data = user.get('home_data', {})
    medals = home_data.get('medals', [])
    
    text = t("home.medals_text", count=len(medals))
    buttons = []
    
    if not medals:
        text += t("home.medals_empty")
    else:
        text += t("home.medals_choose")
        ordered_medals = sorted(medals, key=lambda medal: (get_medal_category(medal), medal))
        for medal in ordered_medals:
            idx = medals.index(medal)
            label = get_medal_display(medal)
            btn_text = f"✅ {label}" if medal == home_data.get('active_medal') else label
            buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"home_set_medal:{idx}")])
            
    buttons.append([InlineKeyboardButton(text=t("home.titles_back"), callback_data="town_home")])
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
        await callback.answer(t("home.medal_set"))
        
    await cb_town_home_medals(callback)

@router.callback_query(F.data == "town_claim_daily")
async def cb_town_claim_daily(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    quests = check_and_generate_quests(user['user_id'])
    
    if quests.get("claimed"):
        return await callback.answer(t("home.claim_already"), show_alert=True)
        
    quests["claimed"] = True
    reward_gold = 150
    reward_gems = 5
    
    user['gold'] += reward_gold
    user['gems'] = user.get('gems', 0) + reward_gems
    
    update_user(user['user_id'], gold=user['gold'], gems=user['gems'], quests_data=quests)
    await callback.answer(t("home.claim_reward", gold=reward_gold, gems=reward_gems), show_alert=True)
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
        elif "req_title" in skin_info and normalize_title(skin_info["req_title"]) not in titles:
            can_unlock, error_msg = False, t("home.require_title", title=get_title_display(skin_info["req_title"]))
        elif "req_clan_lvl" in skin_info:
            if clan_id == 0: can_unlock, error_msg = False, t("home.require_clan")
            else:
                clan = get_clan(clan_id)
                if not clan or clan.get("level", 1) < skin_info["req_clan_lvl"]:
                    can_unlock, error_msg = False, t("home.require_clan_level", level=skin_info['req_clan_lvl'])

        if can_unlock:
            unlocked.append(skin_id)
            update_user(user['user_id'], home_data=home_data)
            await callback.answer(t("home.skin_unlocked", name=skin_info['name']), show_alert=True)
        else:
            return await callback.answer(error_msg, show_alert=True)

    await cb_town_home_settings(callback)


