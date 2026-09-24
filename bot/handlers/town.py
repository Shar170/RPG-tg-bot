import json
import random
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from database import get_connection, get_user, update_user, check_and_generate_quests, get_unlocked_titles, get_top_clans, get_recent_global_events, simulate_bot_activity

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
    simulate_bot_activity() # Дергаем симуляцию жизни при загрузке города
    
    xp = user.get('xp', 0)
    lvl = user.get('level', 1)
    max_xp = lvl * 100
    
    # Генерация визуальной полоски опыта
    filled = min(10, int((xp / max_xp) * 10))
    xp_bar = "█" * filled + "░" * (10 - filled)
    
    # Генерация Топ-3 кланов
    top_clans = get_top_clans(limit=3)
    clans_text = ""
    if top_clans:
        clans_text = "\n\n🏆 **Топ-3 кланов недели:**\n"
        medals = ["🥇", "🥈", "🥉"]
        for i, clan in enumerate(top_clans):
            icon = medals[i] if i < len(medals) else "🏅"
            clans_text += f"{icon} {clan['name']} (Рейды: {clan['weekly_raids']})\n"
    else:
        clans_text = "\n\n🏆 **Топ-3 кланов недели:**\nПока нет активных кланов."
        
    # Вестник Камарии
    events = get_recent_global_events(5)
    log_text = "\n\n📰 **Вестник Камарии:**\n"
    if events:
        for e in events:
            log_text += f"• {e}\n"
    else:
        log_text += "• В мире всё спокойно...\n"
    
    return (
        f"🏕️ **Лагерь Искателей (Камария)**\n\n"
        f"👤 **{user['username']}** | Ур. {lvl}\n"
        f"🌟 Опыт: `{xp_bar}` {xp}/{max_xp} XP\n"
        f"❤️ ХП: {user['hp']}/{user['max_hp']} | ⚡ ОД: {user.get('energy', 5)}/{user.get('max_energy', 5)}\n"
        f"💰 Золото: {user.get('gold', 0)} 🪙 | 💎 Кристаллы: {user.get('gems', 0)} 💎"
        f"{clans_text}"
        f"{log_text}\n"
        "Куда отправимся?"
    )

# --- ВХОД В ИГРУ / ЛАГЕРЬ ---
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


# --- ДОМ И ДОСТИЖЕНИЯ ---
@router.callback_query(F.data == "town_home")
async def cb_town_home(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    home_data = user.get('home_data', {})
    medals = home_data.get('medals', [])
    stats = home_data.get('stats', {})
    titles = get_unlocked_titles(home_data)
    
    quests = check_and_generate_quests(user['user_id'])
    q_text = ""
    for q in quests.get("quests", []):
        status = "✅" if q["completed"] else f"{q['progress']}/{q['target']}"
        q_text += f"• {q['desc']} [{status}]\n"
        
    medals_str = "\n".join(medals) if medals else "Пусто"
    skin = home_data.get("skin", "Базовый шатер")
    
    text = (
        f"🏡 **Ваш Дом** *(Оформление: {skin})*\n\n"
        f"📜 **Открытые Титулы:**\n{', '.join(titles)}\n\n"
        f"🎖 **Стенд Славы:**\n{medals_str}\n\n"
        f"📅 **Задания на сегодня:**\n{q_text}\n"
        f"📊 **Статистика:**\n"
        f"└ Убито монстров: {stats.get('mobs_killed', 0)}\n"
        f"└ Повержено боссов: {stats.get('bosses_killed', 0)}\n"
        f"└ Побед в PvP: {stats.get('pvp_wins', 0)}\n"
        f"└ Смертей в рейдах: {stats.get('deaths_count', 0)}"
    )
    
    all_quests_completed = len(quests.get("quests", [])) > 0 and all(q.get("completed") for q in quests.get("quests", []))
    already_claimed = quests.get("claimed", False)
    
    buttons = []
    if all_quests_completed and not already_claimed:
        buttons.append([InlineKeyboardButton(text="🎁 Забрать награду за дейлики", callback_data="town_claim_daily")])
        
    buttons.append([InlineKeyboardButton(text="🎨 Настройки дома (Скины)", callback_data="town_home_settings")])
    buttons.append([InlineKeyboardButton(text="🔙 В лагерь", callback_data="town_back")])
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

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
    text = (
        "🎨 **Настройки уюта**\n\n"
        "Здесь вы можете изменить внешний вид вашего жилища в Камарии. Некоторые скины даются за особые заслуги.\n\n"
        "*(Раздел кастомизации находится в разработке, скоро вы сможете обставить дом трофеями!)*"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад в Дом", callback_data="town_home")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

# --- ТАВЕРНА (ХАБ МИНИ-ИГР) ---
@router.callback_query(F.data == "town_tavern")
async def cb_town_tavern(callback: CallbackQuery):
    text = (
        "🎲 **Таверна «Хмельной Дракон»**\n\n"
        "В нос бьет запах жареного мяса и дешевого эля. За дальним столом кто-то ругается из-за ставок.\n"
        "Трактирщик протирает стакан: *«Сыграем в кости? Или хочешь спуститься в подвал, там какие-то темные шахты...»*"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⛏️ Шахта 3х3", callback_data="minigame_mine")],
        [InlineKeyboardButton(text="🔐 Взлом замка", callback_data="minigame_lockpick")],
        [InlineKeyboardButton(text="🎲 Кости с трактирщиком", callback_data="minigame_dice")],
        [InlineKeyboardButton(text="🔙 В лагерь", callback_data="town_back")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

