import json
import sqlite3
from collections import Counter
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command, CommandObject
from database import get_user, update_user, get_connection, get_item_price, get_item_name, check_and_generate_quests, get_top_clans
from config import DB_PATH

router = Router()

# Найти функцию get_town_kb() и заменить ее:
def get_town_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚔️ Доска Рейдов", callback_data="town_raids"),
         InlineKeyboardButton(text="📜 Дейлики", callback_data="town_quests")],
        [InlineKeyboardButton(text="🎒 Инвентарь", callback_data="inv_open"),
         InlineKeyboardButton(text="🧪 Алхимия", callback_data="town_alchemy")],
        [InlineKeyboardButton(text="🔨 Мастерская", callback_data="craft_open"),
         InlineKeyboardButton(text="🏪 Торговец", callback_data="town_market")],
        [InlineKeyboardButton(text="🍻 Таверна (Мини-игры)", callback_data="town_tavern")], # НОВОЕ
        [InlineKeyboardButton(text="🏡 Мой Дом", callback_data="town_home"),
         InlineKeyboardButton(text="🛡️ Клан", callback_data="clan_main")]
    ])


def render_town_text():
    text = "🏰 **Центральный Лагерь**\n\nЗдесь безопасно. Вы можете торговать, крафтить или отправиться в рейд.\n\n"
    top_clans = get_top_clans(3)
    if top_clans:
        text += "🏆 **Доска Славы (Топ Кланов Недели)**\n"
        for i, c in enumerate(top_clans, 1):
            text += f"{i}. 🛡️ **{c['name']}** — {c['weekly_raids']} рейдов\n"
    else:
        text += "🏆 **Доска Славы** пока пустует.\n"
    return text

@router.message(Command("start"))
async def start_game(message: Message, command: CommandObject):
    user = get_user(message.from_user.id)
    ref_id = command.args
    if not user:
        with get_connection() as conn:
            cursor = conn.cursor()
            inv = json.dumps({"potions": [], "materials": {}, "artifacts": [], "equipment": {"weapon": "wood_sword", "armor": "leather_armor"}, "backpack": []}, ensure_ascii=False)
            home = json.dumps({"cosmetics": "Котелок с рагу", "referred_by": ref_id, "ref_count": 0}, ensure_ascii=False)
            cursor.execute("INSERT INTO users (user_id, username, state, hp, max_hp, gold, inventory, home_data) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (message.from_user.id, message.from_user.username, 'STATE_TOWN', 100, 100, 50, inv, home))
            conn.commit()
    else: update_user(message.from_user.id, state='STATE_TOWN')
    await message.answer(render_town_text(), reply_markup=get_town_kb(), parse_mode="Markdown")

@router.callback_query(F.data == "town_back")
async def back_to_town(callback: CallbackQuery):
    await callback.message.edit_text(render_town_text(), reply_markup=get_town_kb(), parse_mode="Markdown")

@router.callback_query(F.data == "town_quests")
async def open_quests(callback: CallbackQuery):
    quests_data = check_and_generate_quests(callback.from_user.id)
    quests = quests_data.get("quests", [])
    
    text = ("📜 **Ежедневные задания**\n"
            "Выполните все 3 задания, чтобы получить награду: **500 🪙 и 10 💎**\n"
            "Обновляются каждую полночь.\n\n")
            
    all_completed = True
    for idx, q in enumerate(quests, 1):
        status = "✅ Выполнено" if q["completed"] else f"В процессе: {q['progress']}/{q['target']}"
        icon = "🟢" if q["completed"] else "⚪"
        text += f"{icon} **Задание {idx}:** {q['desc']}\n   └ {status}\n\n"
        if not q["completed"]: all_completed = False

    buttons = []
    if all_completed and not quests_data.get("claimed"):
        text += "🎁 **Все задания выполнены! Награда ждет вас.**"
        buttons.append([InlineKeyboardButton(text="💎 Забрать Награду", callback_data="quests_claim")])
    elif quests_data.get("claimed"):
        text += "🎉 Награда за сегодня уже получена. Возвращайтесь завтра!"
        
    buttons.append([InlineKeyboardButton(text="🔙 В лагерь", callback_data="town_back")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data == "quests_claim")
async def claim_quests_reward(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    quests_data = user.get("quests_data", {})
    if quests_data.get("claimed"): return await callback.answer("Уже получено!", show_alert=True)
    user['gold'] += 500
    user['gems'] += 10
    quests_data["claimed"] = True
    update_user(user['user_id'], gold=user['gold'], gems=user['gems'], quests_data=quests_data)
    await callback.answer("Получено: 500 Золота и 10 Алмазов!", show_alert=True)
    await open_quests(callback)

@router.callback_query(F.data == "town_market")
async def open_market(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🍲 Еда и Зелья", callback_data="market_cat_consumables")],
        [InlineKeyboardButton(text="🗡 Оружейня", callback_data="market_cat_weapons"), InlineKeyboardButton(text="🛡 Бронник", callback_data="market_cat_armors")],
        [InlineKeyboardButton(text="📦 Скупка (Продажа)", callback_data="market_cat_sell")],
        [InlineKeyboardButton(text="🔙 В лагерь", callback_data="town_back")]
    ])
    await callback.message.edit_text(f"🏪 **Торговец**\n💰 Золото: **{user['gold']}** | 💎 Алмазы: **{user['gems']}**", reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data == "market_cat_consumables")
async def market_consumables(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🍲 Рагу ({get_item_price('ragout')} 🪙)", callback_data="market_buy_ragout")],
        [InlineKeyboardButton(text=f"🧪 Зелье ХП ({get_item_price('health_potion')} 🪙)", callback_data="market_buy_health_potion")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="town_market")]
    ])
    await callback.message.edit_text(f"🏪 **Провизия**\n💰 Доступно: **{user['gold']}** 🪙", reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data == "market_cat_weapons")
async def market_weapons(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    buttons = []
    with sqlite3.connect(DB_PATH) as conn:
        for w_id, w_name, price in conn.execute("SELECT item_id, name, base_price FROM items WHERE type='weapon' ORDER BY base_price").fetchall():
            buttons.append([InlineKeyboardButton(text=f"🗡 {w_name} ({price} 🪙)", callback_data=f"market_buye_{w_id}")])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="town_market")])
    await callback.message.edit_text(f"🏪 **Оружейня**\n💰 Ваше золото: **{user['gold']}** 🪙", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data == "market_cat_armors")
async def market_armors(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    buttons = []
    with sqlite3.connect(DB_PATH) as conn:
        for a_id, a_name, price in conn.execute("SELECT item_id, name, base_price FROM items WHERE type='armor' ORDER BY base_price").fetchall():
            buttons.append([InlineKeyboardButton(text=f"🛡 {a_name} ({price} 🪙)", callback_data=f"market_buye_{a_id}")])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="town_market")])
    await callback.message.edit_text(f"🏪 **Бронник**\n💰 Ваше золото: **{user['gold']}** 🪙", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data.startswith("market_buy_"))
async def market_buy_cons(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    item_id = callback.data.replace("market_buy_", "")
    cost = get_item_price(item_id)
    if user['gold'] < cost: return await callback.answer("Недостаточно золота!", show_alert=True)
    user['gold'] -= cost
    inv = user['inventory']
    inv.setdefault("potions", []).append(get_item_name(item_id))
    update_user(user['user_id'], gold=user['gold'], inventory=inv)
    await callback.answer(f"Куплено: {get_item_name(item_id)}!")
    await market_consumables(callback)

@router.callback_query(F.data.startswith("market_buye_"))
async def market_buy_equip(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    item_id = callback.data.replace("market_buye_", "")
    cost = get_item_price(item_id)
    if user['gold'] < cost: return await callback.answer("Недостаточно золота!", show_alert=True)
    user['gold'] -= cost
    inv = user['inventory']
    inv.setdefault("backpack", []).append(item_id)
    update_user(user['user_id'], gold=user['gold'], inventory=inv)
    await callback.answer(f"Экипировка куплена в рюкзак!", show_alert=True)

@router.callback_query(F.data == "market_cat_sell")
async def market_sell_menu(callback: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 Продать материалы", callback_data="market_sell_mats")],
        [InlineKeyboardButton(text="🗡 Продать экипировку", callback_data="market_sell_equip")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="town_market")]
    ])
    await callback.message.edit_text("🏪 **Скупщик**\n(Экипировка скупается за 50%)", reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data == "market_sell_mats")
async def market_sell_mats(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    materials = user['inventory'].get("materials", {})
    buttons = []
    for m_id, count in materials.items():
        if count > 0:
            price = get_item_price(m_id)
            buttons.append([InlineKeyboardButton(text=f"Продать 1x {get_item_name(m_id)} (+{price}🪙)", callback_data=f"market_sm1_{m_id}")])
    buttons.append([InlineKeyboardButton(text="📦 Продать ВСЁ разом", callback_data="market_sell_all")])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="market_cat_sell")])
    await callback.message.edit_text("🏪 **Скупщик ресурсов**", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data.startswith("market_sm1_"))
async def market_sell_one_mat(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    m_id = callback.data.replace("market_sm1_", "")
    inv = user['inventory']
    if inv.get("materials", {}).get(m_id, 0) > 0:
        price = get_item_price(m_id)
        user['gold'] += price
        inv["materials"][m_id] -= 1
        if inv["materials"][m_id] == 0: del inv["materials"][m_id]
        update_user(user['user_id'], gold=user['gold'], inventory=inv)
        await callback.answer(f"Продано! +{price} 🪙")
    await market_sell_mats(callback)

@router.callback_query(F.data == "market_sell_all")
async def market_sell_all(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    inv = user['inventory']
    materials = inv.get("materials", {})
    if not materials: return await callback.answer("Нет материалов для продажи!", show_alert=True)
    profit = sum(get_item_price(m) * c for m, c in materials.items())
    inv["materials"] = {}
    update_user(user['user_id'], gold=user['gold'] + profit, inventory=inv)
    await callback.answer(f"Все материалы проданы за {profit} золота!", show_alert=True)
    await open_market(callback)

@router.callback_query(F.data == "market_sell_equip")
async def market_sell_equip(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    backpack = user['inventory'].get("backpack", [])
    buttons = []
    for e_id, count in Counter(backpack).items():
        price = int(get_item_price(e_id) * 0.5)
        buttons.append([InlineKeyboardButton(text=f"Продать {get_item_name(e_id)} (+{price}🪙) [В рюкзаке: {count}]", callback_data=f"market_se1_{e_id}")])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="market_cat_sell")])
    await callback.message.edit_text("🏪 **Скупщик экипировки**", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data.startswith("market_se1_"))
async def market_sell_one_eq(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    e_id = callback.data.replace("market_se1_", "")
    inv = user['inventory']
    if e_id in inv.get("backpack", []):
        price = int(get_item_price(e_id) * 0.5)
        user['gold'] += price
        inv["backpack"].remove(e_id)
        update_user(user['user_id'], gold=user['gold'], inventory=inv)
        await callback.answer(f"Продано за {price} 🪙!")
    await market_sell_equip(callback)

@router.callback_query(F.data == "town_home")
async def show_home(callback: CallbackQuery):
    await callback.message.edit_text("🏡 **Мой Дом**", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="town_back")]]), parse_mode="Markdown")
