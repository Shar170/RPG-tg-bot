import random
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database import (
    get_user, update_user, consume_energy, get_today_dungeon,
    get_all_war_regions, get_scaled_mob, track_stat, get_energy_settings
)
from utils.generators import generate_dungeon_graph

router = Router()

def get_navigation_kb(dungeon_data: dict):
    curr = dungeon_data.get("current_node")
    next_nodes = dungeon_data.get("nodes", {}).get(curr, {}).get("next", [])
    buttons = []

    type_labels = {
        "combat": "⚔️ Враг",
        "boss": "💀 БОСС",
        "campfire": "🏕️ Костёр (Привал)",
        "puzzle": "🧩 Загадка",
        "treasure": "📦 Сундук",
        "empty": "💨 Пустой зал"
    }

    for nxt in next_nodes:
        n_info = dungeon_data["nodes"].get(nxt, {})
        n_type = n_info.get("type", "empty")
        label = type_labels.get(n_type, "🚪 Проход")
        buttons.append([InlineKeyboardButton(text=f"Вперёд: {label}", callback_data=f"dungeon_go_{nxt}")])

    # ВОЗВРАЩАЕМ КНОПКУ ПОБЕГА НА РАЗВИЛКАХ!
    if next_nodes:
        buttons.append([InlineKeyboardButton(text="🏃‍♂️ Сбежать с добычей", callback_data="combat_act_flee")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

@router.callback_query(F.data == "town_dungeon_menu")
async def select_dungeon_mode(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    e_cfg = get_energy_settings(user.get('level', 1))

    solo_badge = f" ({e_cfg['cost_solo']} ⚡)" if e_cfg['cost_solo'] > 0 else ""
    event_badge = f" ({e_cfg['cost_event']} ⚡)" if e_cfg['cost_event'] > 0 else ""
    war_badge = f" ({e_cfg['cost_war']} ⚡)" if e_cfg['cost_war'] > 0 else ""

    text = (
        "⚔️ **Экспедиции и Военный Совет**\n\n"
        "Выберите направление вылазки:\n\n"
        "🏛️ **Одиночный рейд** — исследование руин, привалы у костра, добыча руды.\n"
        "📅 **Ежедневный данж** — опасный поход к боссу дня за уникальным лутом.\n"
        "🌍 **Война за Камарию** — совместное освобождение 7 регионов от демонов!"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🏛️ Одиночный рейд{solo_badge}", callback_data="dungeon_start_solo")],
        [InlineKeyboardButton(text=f"📅 Ежедневный данж{event_badge}", callback_data="dungeon_start_event")],
        [InlineKeyboardButton(text=f"🌍 Война за Камарию{war_badge}", callback_data="war_hub")],
        [InlineKeyboardButton(text="🔙 В лагерь", callback_data="town_back")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data == "dungeon_start_solo")
async def start_solo_dungeon(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    e_cfg = get_energy_settings(user.get('level', 1))
    cost = e_cfg["cost_solo"]

    if not consume_energy(user['user_id'], cost):
        return await callback.answer(f"Недостаточно энергии (нужно {cost} ⚡)!", show_alert=True)

    mobs = ["temple_guard", "living_idol", "khmer_priest", "poison_slime"]
    d_data = generate_dungeon_graph(dungeon_type="solo", mobs_pool=mobs, boss_id="temple_guard")
    update_user(user['user_id'], state='STATE_DUNGEON', dungeon_data=d_data)
    await enter_node(callback, user, d_data, d_data["current_node"])

@router.callback_query(F.data == "dungeon_start_event")
async def start_event_dungeon(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    today = get_today_dungeon()
    if not today:
        return await callback.answer("Сегодня подземелье закрыто!", show_alert=True)

    e_cfg = get_energy_settings(user.get('level', 1))
    cost = e_cfg["cost_event"]

    if not consume_energy(user['user_id'], cost):
        return await callback.answer(f"Недостаточно энергии (нужно {cost} ⚡)!", show_alert=True)

    d_data = generate_dungeon_graph(dungeon_type="event", mobs_pool=today["mobs"], boss_id=today["boss_id"])
    update_user(user['user_id'], state='STATE_DUNGEON', dungeon_data=d_data)
    await enter_node(callback, user, d_data, d_data["current_node"])

@router.callback_query(F.data == "war_hub")
async def show_war_fronts(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    regions = get_all_war_regions()
    e_cfg = get_energy_settings(user.get('level', 1))
    cost_badge = f" ({e_cfg['cost_war']} ⚡)" if e_cfg['cost_war'] > 0 else ""

    text = (
        "🌍 **Фронты Освобождения Камарии**\n"
        "Каждая победа приближает регион к полной свободе!\n\n"
    )
    buttons = []
    for r in regions:
        filled = int(r['pct'] // 10)
        bar = "█" * filled + "░" * (10 - filled)
        status = "✨ ОСВОБОЖДЕН" if r['is_liberated'] else f"[{bar}] {r['pct']}%"
        text += f"**{r['name']}**\n└ {status} ({r['current']:,} / {r['target']:,})\n"
        btn_label = f"⚔️ В бой: {r['name']}{cost_badge}" if not r['is_liberated'] else f"🛡️ Зачищен: {r['name']}"
        buttons.append([InlineKeyboardButton(text=btn_label, callback_data=f"war_enter:{r['id']}")])

    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="town_dungeon_menu")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data.startswith("war_enter:"))
async def enter_war_region(callback: CallbackQuery):
    reg_id = int(callback.data.split(":")[1])
    user = get_user(callback.from_user.id)
    e_cfg = get_energy_settings(user.get('level', 1))
    cost = e_cfg["cost_war"]

    if not consume_energy(user['user_id'], cost):
        return await callback.answer(f"Недостаточно энергии (нужно {cost} ⚡)!", show_alert=True)

    regions = get_all_war_regions()
    region = next((r for r in regions if r['id'] == reg_id), None)

    d_data = generate_dungeon_graph(dungeon_type="war", mobs_pool=region['mobs'], boss_id=region['boss_id'])
    d_data['war_region_id'] = reg_id
    update_user(user['user_id'], state='STATE_DUNGEON', dungeon_data=d_data)
    await enter_node(callback, user, d_data, d_data["current_node"])

@router.callback_query(F.data.startswith("dungeon_go_"))
async def go_to_node(callback: CallbackQuery):
    target_node = callback.data.replace("dungeon_go_", "")
    user = get_user(callback.from_user.id)
    d_data = user.get('dungeon_data', {})
    d_data["current_node"] = target_node
    update_user(user['user_id'], dungeon_data=d_data)
    await enter_node(callback, user, d_data, target_node)

async def enter_node(callback: CallbackQuery, user: dict, d_data: dict, node_id: str):
    node = d_data["nodes"][node_id]
    n_type = node["type"]

    if n_type == "empty" and not d_data.get("nodes", {}).get(node_id, {}).get("next"):
        text = "🚪 **Вы перешагнули порог подземелья.** Впереди развилка. Выберите дальнейший путь:"
        await callback.message.edit_text(text, reply_markup=get_navigation_kb(d_data), parse_mode="Markdown")

    elif n_type in ["combat", "boss"]:
        mob_id = node.get("mob_id", "temple_guard")
        player_lvl = user.get('level', 1)
        mob = get_scaled_mob(mob_id, player_lvl=player_lvl)
        m_hp = random.randint(mob['hp_min'], mob['hp_max'])

        combat_data = {
            "enemy_id": mob['mob_id'],
            "enemy_name": mob['name'],
            "enemy_hp": m_hp,
            "enemy_max_hp": m_hp,
            "dmg_min": mob['dmg_min'],
            "dmg_max": mob['dmg_max'],
            "mob_pref": mob['row_pref'],
            "mob_skills": mob['skills'],
            "gold_min": mob.get('gold_min', 5),
            "gold_max": mob.get('gold_max', 15),
            "xp_reward": mob.get('xp_reward', 10),
            "ap": 3,
            "distance": "close",
            "buff_armor": 0, "buff_armor_t": 0,
            "buff_str": 0, "buff_str_t": 0,
            "buff_dodge": 0.0, "buff_dodge_t": 0,
            "dot_burn": 0, "dot_poison": 0, "dot_bleed": 0, "enemy_stun": 0
        }
        update_user(user['user_id'], state='STATE_COMBAT', combat_data=combat_data)
        from handlers.combat import render_combat
        boss_prefix = "💀 **БОСС ЭТОЙ ЗЕМЛИ!** " if n_type == "boss" else ""
        await render_combat(callback, user, combat_data, f"{boss_prefix}{mob['name']} готовится к атаке!")

    elif n_type == "campfire":
        heal_amt = int(user['max_hp'] * 0.4)
        user['hp'] = min(user['max_hp'], user['hp'] + heal_amt)
        update_user(user['user_id'], hp=user['hp'])
        text = (
            f"🏕️ **Тёплый Костёр (Привал)**\n\n"
            f"Вы перевели дух у потрескивающего пламени и перевязали раны.\n"
            f"❤️ Восстановлено **+{heal_amt} ХП** (Здоровье: {user['hp']}/{user['max_hp']}).\n\n"
            "Впереди решающая битва. Куда направитесь дальше?"
        )
        await callback.message.edit_text(text, reply_markup=get_navigation_kb(d_data), parse_mode="Markdown")

    elif n_type == "treasure":
        gold_find = random.randint(35, 80)
        user['gold'] += gold_find
        d_data.setdefault('gathered_gold', 0)
        d_data['gathered_gold'] += gold_find
        update_user(user['user_id'], gold=user['gold'], dungeon_data=d_data)
        text = (
            f"📦 **Тайник в каменной нише!**\n\n"
            f"Вы сорвали печать и забрали **+{gold_find} 🪙** золота!\n\n"
            "Выберите следующий поворот:"
        )
        await callback.message.edit_text(text, reply_markup=get_navigation_kb(d_data), parse_mode="Markdown")

    elif n_type == "empty":
        track_stat(user['user_id'], 'empty_rooms', 1)
        text = "💨 **Заброшенный зал.** Здесь тишина, вековая пыль и каменные обломки.\n\nПродолжайте исследовать:"
        await callback.message.edit_text(text, reply_markup=get_navigation_kb(d_data), parse_mode="Markdown")

    elif n_type == "puzzle":
        p_data = node.get("puzzle")
        if not p_data:
            from utils.generators import generate_emoji_puzzle
            p_data = generate_emoji_puzzle()
            node["puzzle"] = p_data
            update_user(user['user_id'], dungeon_data=d_data)

        buttons = []
        row = []
        for opt in p_data["options"]:
            is_correct = (str(opt) == str(p_data["correct"]))
            cb = "riddle_ans_correct" if is_correct else "riddle_ans_wrong"
            row.append(InlineKeyboardButton(text=str(opt), callback_data=cb))
            if len(row) == 2:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)

        await callback.message.edit_text(p_data["text"], reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data == "riddle_ans_correct")
async def riddle_correct(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    track_stat(user['user_id'], 'riddles_solved', 1)
    d_data = user.get('dungeon_data', {})
    reward = random.randint(35, 75)
    user['gold'] += reward
    d_data.setdefault('gathered_gold', 0)
    d_data['gathered_gold'] += reward
    update_user(user['user_id'], gold=user['gold'], dungeon_data=d_data)
    text = f"✨ **Загадка решена верно! Стела сдвинулась!**\nВы открыли скрытый тайник и получили **+{reward} 🪙** золота."
    await callback.message.edit_text(text, reply_markup=get_navigation_kb(d_data), parse_mode="Markdown")

@router.callback_query(F.data == "riddle_ans_wrong")
async def riddle_wrong(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    track_stat(user['user_id'], 'riddles_failed', 1)
    d_data = user.get('dungeon_data', {})
    trap_dmg = 15
    user['hp'] = max(1, user['hp'] - trap_dmg)
    update_user(user['user_id'], hp=user['hp'])
    text = f"⚡ **Неверный ответ! Сработала руна защиты!**\nЛовушка нанесла **-{trap_dmg} ХП** урона."
    await callback.message.edit_text(text, reply_markup=get_navigation_kb(d_data), parse_mode="Markdown")
