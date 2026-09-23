import json
import random
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database import (
    get_user, update_user, get_unlocked_titles, check_and_generate_quests,
    consume_energy, get_energy_settings, track_stat, get_top_clans
)

router = Router()

COZY_SKINS = {
    "tent": {"name": "⛺ Палатка бродяги", "price": 0, "desc": "Простая парусиновая палатка у костра. Пахнет дымом и сыростью."},
    "cabin": {"name": "🪵 Охотничья изба", "price": 25, "desc": "Бревенчатый домик с оленьими рогами и теплым очагом."},
    "manor": {"name": "🏰 Каминный Зал", "price": 75, "desc": "Каменный особняк с персидскими коврами, библиотекой и винным погребом."},
    "abyss_throne": {"name": "🌑 Трон Бездны", "price": 200, "desc": "Величественный зал из черного обсидиана, парящий над пустотой."}
}

def get_town_kb(user: dict):
    player_lvl = user.get('level', 1)
    e_cfg = get_energy_settings(player_lvl)
    mg_badge = f" ({e_cfg['cost_minigame']} ⚡)" if e_cfg.get('cost_minigame', 0) > 0 else ""
    
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚔️ В Поход (Рейды)", callback_data="town_dungeon_menu")],
        [InlineKeyboardButton(text="🏡 Мой Дом", callback_data="town_home"), InlineKeyboardButton(text="🎒 Инвентарь", callback_data="inv_open")],
        [InlineKeyboardButton(text="🧪 Алхимия", callback_data="town_alchemy"), InlineKeyboardButton(text="🔨 Мастерская", callback_data="town_craft")],
        [InlineKeyboardButton(text=f"🎮 Активности{mg_badge}", callback_data="tavern_games_menu"), InlineKeyboardButton(text="🛒 Торговец", callback_data="town_market")],
        [InlineKeyboardButton(text="🛡️ Клан", callback_data="clan_main"), InlineKeyboardButton(text="📜 Задания", callback_data="town_quests")]
    ])

@router.callback_query(F.data == "town_back")
async def back_to_town(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    player_lvl = user.get('level', 1)
    max_en = user.get('max_energy', 5)
    
    # Формируем вывеску Топ-3 кланов
    top_clans = get_top_clans(3)
    clans_text = "\n🏆 **Доска Почёта (Топ-3 Клана):**\n"
    if top_clans:
        medals = ["🥇", "🥈", "🥉"]
        for i, clan in enumerate(top_clans):
            clans_text += f"{medals[i]} **{clan['name']}** — {clan['weekly_raids']} рейдов\n"
    else:
        clans_text += "Пока нет активных кланов. Станьте первыми!\n"
    
    text = (
        f"🏕️ **Центральный Лагерь**\n"
        f"Герой: **{user['username']}** | Ур: **{player_lvl}**\n"
        f"Здоровье: **{user['hp']}/{user['max_hp']}** | Энергия: **{user.get('energy', max_en)}/{max_en}** ⚡\n"
        f"Золото: **{user['gold']}** 🪙 | Алмазы: **{user.get('gems', 0)}** 💎\n"
        f"{clans_text}"
    )
    await callback.message.edit_text(text, reply_markup=get_town_kb(user), parse_mode="Markdown")

# =========================================================
# 🎮 РАЗДЕЛ: МИНИ-ИГРЫ (ШАХТА 3х3, БЫКИ И КОРОВЫ, КОСТИ)
# =========================================================
@router.callback_query(F.data == "tavern_games_menu")
async def show_tavern_games(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    player_lvl = user.get('level', 1)
    max_en = user.get('max_energy', 5)
    e_cfg = get_energy_settings(player_lvl)
    cost = e_cfg.get('cost_minigame', 1)
    
    curr_energy = user.get('energy', max_en)
    next_sec = user.get('next_energy_in', 0)
    
    if curr_energy >= max_en:
        timer_text = "✨ Полный запас энергии"
    elif next_sec > 0:
        mins = next_sec // 60
        secs = next_sec % 60
        timer_text = f"⏳ След. ед. через: **{mins:02d}:{secs:02d}**"
    else:
        timer_text = "⏳ Восстановление..."

    cost_badge = f"{cost} ⚡" if cost > 0 else "Бесплатно"

    text = (
        f"🎪 **Городские Активности и Развлечения**\n\n"
        f"⚡ Энергия: **{curr_energy} / {max_en}** | {timer_text}\n"
        f"Расход на активность: **{cost_badge}**\n\n"
        "⛏️ **Заброшенная Шахта** — интерактивное поле 3х3 камней для добычи руды.\n"
        "🔓 **Взлом Замка** — взлом сейфа по правилам «Быки и Коровы».\n"
        "🎲 **Кости в Таверне** — игра в кости против трактирщика (ставка 50 🪙)."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⛏️ Заброшенная Шахта (3х3)", callback_data="game_mine_field")],
        [InlineKeyboardButton(text="🔓 Взлом Замка (Быки и Коровы)", callback_data="game_lock_field")],
        [InlineKeyboardButton(text="🎲 Кости с Трактирщиком", callback_data="game_dice_intro")],
        [InlineKeyboardButton(text="🔙 В лагерь", callback_data="town_back")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

# --- 1. ШАХТА: ИНТЕРАКТИВНОЕ ПОЛЕ 3х3 ---
@router.callback_query(F.data == "game_mine_field")
async def game_mine_field(callback: CallbackQuery):
    grid = ["ore"] * 4 + ["gem"] * 2 + ["empty"] * 2 + ["cavein"] * 1
    random.shuffle(grid)
    grid_str = ",".join(grid)

    text = (
        "⛏️ **Заброшенная Шахта (Сетка 3х3)**\n\n"
        "Перед вами скальная стена из 9 камней. "
        "В некоторых спрятаны руда и самоцветы, но один из камней вызовет обвал породы!\n\n"
        "Выберите, какой камень расколоть киркой:"
    )
    buttons = []
    for r in range(3):
        row = []
        for c in range(3):
            idx = r * 3 + c
            row.append(InlineKeyboardButton(text="🪨", callback_data=f"mine_hit:{idx}:{grid_str}"))
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="🔙 К активностям", callback_data="tavern_games_menu")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data.startswith("mine_hit:"))
async def mine_hit_exec(callback: CallbackQuery):
    parts = callback.data.split(":")
    idx = int(parts[1])
    grid = parts[2].split(",")

    user = get_user(callback.from_user.id)
    e_cfg = get_energy_settings(user.get('level', 1))
    cost = e_cfg.get('cost_minigame', 1)

    if not consume_energy(user['user_id'], cost):
        return await callback.answer(f"Недостаточно энергии (нужно {cost} ⚡)!", show_alert=True)

    cell_type = grid[idx]
    inv = user['inventory']
    mats = inv.setdefault('materials', {})

    if cell_type == "cavein":
        dmg = random.randint(12, 20)
        user['hp'] = max(1, user['hp'] - dmg)
        track_stat(user['user_id'], 'mines_failed', 1)
        update_user(user['user_id'], hp=user['hp'])
        res_msg = f"💥 **ОБВАЛ!** Вы задели несущий камень! Нанесено **-{dmg} ХП** урона."
    elif cell_type == "gem":
        gems = random.randint(1, 2)
        gold = random.randint(30, 60)
        user['gold'] += gold
        new_gems = user.get('gems', 0) + gems
        track_stat(user['user_id'], 'mines_cleared', 1)
        update_user(user['user_id'], gold=user['gold'], gems=new_gems)
        res_msg = f"💎 **САМОЦВЕТЫ!** Вы откололи драгоценность: **+{gems} 💎** и **+{gold} 🪙**!"
    elif cell_type == "ore":
        ingots = random.randint(2, 4)
        gold = random.randint(20, 40)
        mats['iron_ingot'] = mats.get('iron_ingot', 0) + ingots
        user['gold'] += gold
        track_stat(user['user_id'], 'mines_cleared', 1)
        update_user(user['user_id'], gold=user['gold'], inventory=inv)
        res_msg = f"⛏️ **ЖЕЛЕЗНАЯ РУДА!** Найдено **+{ingots} слитков** и **+{gold} 🪙**!"
    else:
        track_stat(user['user_id'], 'mines_cleared', 1)
        res_msg = "💨 Пустая порода. Под камнем лишь пыль и щебень."

    icons_map = {"cavein": "💥", "gem": "💎", "ore": "⛏️", "empty": "💨"}
    buttons = []
    for r in range(3):
        row = []
        for c in range(3):
            c_idx = r * 3 + c
            icon = icons_map[grid[c_idx]] if c_idx == idx else "🪨"
            row.append(InlineKeyboardButton(text=icon, callback_data="mine_done_noop"))
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="⛏️ Новая жила", callback_data="game_mine_field")])
    buttons.append([InlineKeyboardButton(text="🔙 К активностям", callback_data="tavern_games_menu")])

    await callback.message.edit_text(f"⛏️ **Результат удара:**\n\n{res_msg}", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data == "mine_done_noop")
async def mine_noop(callback: CallbackQuery):
    await callback.answer("Эта жила уже выработана!")

# --- 2. ВЗЛОМ ЗАМКА: БЫКИ И КОРОВЫ ---
@router.callback_query(F.data == "game_lock_field")
async def start_lockpick_cows(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    e_cfg = get_energy_settings(user.get('level', 1))
    cost = e_cfg.get('cost_minigame', 1)

    if not consume_energy(user['user_id'], cost):
        return await callback.answer(f"Недостаточно энергии (нужно {cost} ⚡)!", show_alert=True)

    digits = list(range(1, 7))
    random.shuffle(digits)
    code = "".join(str(d) for d in digits[:3])
    await render_lockpick_screen(callback, code, attempts_left=4, history=[])

async def render_lockpick_screen(callback: CallbackQuery, code: str, attempts_left: int, history: list):
    hist_text = "\n".join(history) if history else "*Попыток еще не было*"
    text = (
        f"🔓 **Взлом Сейфа («Быки и Коровы»)**\n\n"
        f"Код состоит из **3 уникальных цифр (от 1 до 6)**.\n"
        f"🐂 **Быки** — цифра угадана и на своем месте.\n"
        f"🐄 **Коровы** — цифра есть в коде, но на другой позиции.\n\n"
        f"Осталось попыток: **{attempts_left}**\n\n"
        f"📋 **Журнал взлома:**\n{hist_text}\n\n"
        f"Выберите комбинацию:"
    )

    combos = []
    while len(combos) < 4:
        c_digits = list(range(1, 7))
        random.shuffle(c_digits)
        c_str = "".join(str(d) for d in c_digits[:3])
        if c_str not in combos and not any(c_str in h for h in history):
            combos.append(c_str)
    if code not in combos and attempts_left > 1:
        combos[0] = code
    random.shuffle(combos)

    buttons = []
    row = []
    for c in combos:
        row.append(InlineKeyboardButton(text=f"🔑 {c}", callback_data=f"lock_try:{c}:{code}:{attempts_left}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="🔙 Отступить", callback_data="tavern_games_menu")])

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data.startswith("lock_try:"))
async def lock_try_exec(callback: CallbackQuery):
    parts = callback.data.split(":")
    guess = parts[1]
    code = parts[2]
    attempts = int(parts[3]) - 1
    user = get_user(callback.from_user.id)

    bulls = sum(1 for i in range(3) if guess[i] == code[i])
    cows = sum(1 for i in range(3) if guess[i] != code[i] and guess[i] in code)

    if bulls == 3:
        gold = random.randint(60, 120)
        gems = random.randint(1, 2)
        user['gold'] += gold
        new_gems = user.get('gems', 0) + gems
        track_stat(user['user_id'], 'locks_picked', 1)
        update_user(user['user_id'], gold=user['gold'], gems=new_gems)
        text = (
            f"🎉 **ЩЕЛЧОК! ЗАМОК ВЗЛОМАН!**\n\n"
            f"Код `[{guess}]` подошёл идеально!\n"
            f"Награда из сейфа: **+{gold} 🪙** золота и **+{gems} 💎** кристаллов!"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔓 Взломать ещё один", callback_data="game_lock_field")],
            [InlineKeyboardButton(text="🔙 К активностям", callback_data="tavern_games_menu")]
        ])
        return await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

    if attempts <= 0:
        track_stat(user['user_id'], 'locks_failed', 1)
        text = (
            f"💥 **ТРЕСК! Сработала блокировка замка!**\n\n"
            f"Отмычки сломались. Правильный шифр был: **{code}**."
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔓 Попробовать снова", callback_data="game_lock_field")],
            [InlineKeyboardButton(text="🔙 К активностям", callback_data="tavern_games_menu")]
        ])
        return await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

    new_hist = f"`{guess}` — 🐂 {bulls} | 🐄 {cows}"
    await render_lockpick_screen(callback, code, attempts, [new_hist])

# --- 3. КОСТИ: ЭКРАН С ПОДСКАЗКОЙ И КНОПКОЙ БРОСКА ---
@router.callback_query(F.data == "game_dice_intro")
async def game_dice_intro(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    e_cfg = get_energy_settings(user.get('level', 1))
    cost = e_cfg.get('cost_minigame', 1)
    cost_text = f" ({cost} ⚡)" if cost > 0 else ""

    text = (
        "🎲 **Игра в Кости с Трактирщиком**\n\n"
        "📖 **Правила:**\n"
        "• Ставка на кон: **50 🪙** золота.\n"
        "• Вы и трактирщик бросаете по два шестигранных кубика.\n"
        "• У кого сумма очков больше — тот забирает куш (**100 🪙**).\n"
        "• При ничьей ставка возвращается в ваш кошель.\n\n"
        f"Ваш баланс: **{user['gold']}** 🪙 | Энергия: **{user.get('energy', 5)}** ⚡\n\n"
        "Готовы бросить кости?"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🎲 Бросить кубики!{cost_text}", callback_data="game_dice_roll")],
        [InlineKeyboardButton(text="🔙 Назад к играм", callback_data="tavern_games_menu")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data == "game_dice_roll")
async def play_dice(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    e_cfg = get_energy_settings(user.get('level', 1))
    cost = e_cfg.get('cost_minigame', 1)
    
    if user['gold'] < 50:
        return await callback.answer("У вас нет 50 золота для ставки!", show_alert=True)
        
    if not consume_energy(user['user_id'], cost):
        return await callback.answer(f"Недостаточно энергии (нужно {cost} ⚡)!", show_alert=True)

    p_roll1, p_roll2 = random.randint(1, 6), random.randint(1, 6)
    d_roll1, d_roll2 = random.randint(1, 6), random.randint(1, 6)
    
    player_score = p_roll1 + p_roll2
    dealer_score = d_roll1 + d_roll2
    
    if player_score > dealer_score:
        reward = 100
        new_gold = user['gold'] + 50
        track_stat(user['user_id'], 'dice_won', 1)
        res_text = f"🎉 **ПОБЕДА!**\nТрактирщик бурчит и отсчитывает вам **+{reward}** 🪙!"
    elif player_score < dealer_score:
        new_gold = user['gold'] - 50
        track_stat(user['user_id'], 'dice_lost', 1)
        res_text = "💀 **ВЫ ПРОИГРАЛИ!**\nТрактирщик сгребает вашу ставку (-50 🪙)."
    else:
        new_gold = user['gold']
        res_text = "🤝 **НИЧЬЯ!**\nОчки равны, золото осталось при вас."
        
    update_user(user['user_id'], gold=new_gold)
    
    text = (
        "🎲 **Результат Броска:**\n\n"
        f"Ваш бросок: 🎲 **{p_roll1}** и 🎲 **{p_roll2}** (Всего: **{player_score}**)\n"
        f"Бросок Трактирщика: 🎲 **{d_roll1}** и 🎲 **{d_roll2}** (Всего: **{dealer_score}**)\n\n"
        f"{res_text}\n\n"
        f"Баланс: **{new_gold}** 🪙"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎲 Бросить ещё раз (50 🪙)", callback_data="game_dice_roll")],
        [InlineKeyboardButton(text="🔙 К активностям", callback_data="tavern_games_menu")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

# =========================================================
# 🏡 РАЗДЕЛ: МОЙ ДОМ
# =========================================================
@router.callback_query(F.data == "town_home")
async def open_home(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    home = user.get('home_data', {})
    stats = home.get('stats', {})
    
    active_skin = home.get('active_skin', 'tent')
    skin_data = COZY_SKINS.get(active_skin, COZY_SKINS['tent'])
    active_title = home.get('active_title', 'Новичок')
    
    medals = home.get('medals', [])
    medals_count = len(medals)
    
    text = (
        f"🏡 **Мой Дом: {skin_data['name']}**\n"
        f"*{skin_data['desc']}*\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🏷️ Текущий титул: **[{active_title}]**\n"
        f"🎖️ Памятных медалей: **{medals_count} шт.**\n\n"
        f"📊 **Летопись подвигов:**\n"
        f"• Монстров повержено: **{stats.get('mobs_killed', 0) + home.get('mobs_killed', 0)}**\n"
        f"• Боссов уничтожено: **{stats.get('bosses_killed', 0) + home.get('bosses_killed', 0)}**\n"
        f"• Вылазок в шахту: **{stats.get('mines_cleared', 0)}**\n"
        f"• Замков взломано: **{stats.get('locks_picked', 0)}** (Сломано: {stats.get('locks_failed', 0)})\n"
        f"• Побед в кости: **{stats.get('dice_won', 0)}** (Поражений: {stats.get('dice_lost', 0)})\n"
        f"• Загадок разгадано: **{stats.get('riddles_solved', 0)}**\n"
        f"• Зелий сварено: **{stats.get('potions_brewed', 0)}**\n"
        f"• Предметов выковано: **{stats.get('crafts_count', 0)}**\n"
        f"• Вклад в Войну: **{stats.get('war_clears', 0)} операций**\n"
        f"• Смертей: **{stats.get('deaths_count', 0)}** | Побегов: **{stats.get('flees_count', 0)}**\n"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛏️ Отдохнуть у очага (Полное ХП)", callback_data="home_rest")],
        [InlineKeyboardButton(text="⚙️ Интерьер и Настройки", callback_data="home_custom_menu")],
        [InlineKeyboardButton(text="🎖️ Витрина Медалей", callback_data="home_medals_show")],
        [InlineKeyboardButton(text="🔙 В лагерь", callback_data="town_back")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data == "home_rest")
async def home_rest(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    if user['hp'] >= user['max_hp']:
        return await callback.answer("Вы уже полны сил!", show_alert=True)
    update_user(user['user_id'], hp=user['max_hp'])
    await callback.answer("Вы сладко выспались и полностью восстановили силы! ❤️", show_alert=True)
    await open_home(callback)

@router.callback_query(F.data == "home_custom_menu")
async def home_custom_menu(callback: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏷️ Выбрать Активный Титул", callback_data="home_pick_title")],
        [InlineKeyboardButton(text="🛋️ Сменить Уют / Купить скин", callback_data="home_skins_shop")],
        [InlineKeyboardButton(text="🔙 Назад в дом", callback_data="town_home")]
    ])
    await callback.message.edit_text("⚙️ **Настройки Дома и Персонализация:**", reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data == "home_pick_title")
async def pick_title_menu(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    home = user.get('home_data', {})
    unlocked = get_unlocked_titles(home)
    active = home.get('active_title', 'Новичок')
    
    buttons = []
    for t in unlocked:
        mark = "✅ " if t == active else ""
        buttons.append([InlineKeyboardButton(text=f"{mark}{t}", callback_data=f"set_title:{t}")])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="home_custom_menu")])
    
    await callback.message.edit_text("🏷️ **Выберите титул для отображения в профиле:**", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data.startswith("set_title:"))
async def set_title_exec(callback: CallbackQuery):
    title = callback.data.split(":", 1)[1]
    user = get_user(callback.from_user.id)
    home = user.get('home_data', {})
    home['active_title'] = title
    update_user(user['user_id'], home_data=home)
    await callback.answer(f"Титул изменен на [{title}]!")
    await pick_title_menu(callback)

@router.callback_query(F.data == "home_skins_shop")
async def skins_shop_menu(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    home = user.get('home_data', {})
    owned = home.setdefault('owned_skins', ["tent"])
    active = home.get('active_skin', 'tent')
    gems = user.get('gems', 0)
    
    text = f"🛋️ **Магазин Уюта для Дома**\nВаши алмазы: **{gems}** 💎\n\n"
    buttons = []
    for s_id, s_data in COZY_SKINS.items():
        if s_id in owned:
            status = " [Надето]" if s_id == active else " [Надеть]"
            buttons.append([InlineKeyboardButton(text=f"✅ {s_data['name']}{status}", callback_data=f"skin_equip:{s_id}")])
        else:
            buttons.append([InlineKeyboardButton(text=f"🔒 {s_data['name']} ({s_data['price']} 💎)", callback_data=f"skin_buy:{s_id}")])
            
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="home_custom_menu")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data.startswith("skin_equip:"))
async def equip_skin(callback: CallbackQuery):
    s_id = callback.data.split(":")[1]
    user = get_user(callback.from_user.id)
    home = user.get('home_data', {})
    home['active_skin'] = s_id
    update_user(user['user_id'], home_data=home)
    await callback.answer("Интерьер дома обновлен!")
    await skins_shop_menu(callback)

@router.callback_query(F.data.startswith("skin_buy:"))
async def buy_skin(callback: CallbackQuery):
    s_id = callback.data.split(":")[1]
    user = get_user(callback.from_user.id)
    s_data = COZY_SKINS.get(s_id)
    
    if user.get('gems', 0) < s_data['price']:
        return await callback.answer("Недостаточно алмазов 💎!", show_alert=True)
        
    home = user.get('home_data', {})
    home.setdefault('owned_skins', ["tent"]).append(s_id)
    home['active_skin'] = s_id
    
    update_user(user['user_id'], gems=user['gems'] - s_data['price'], home_data=home)
    await callback.answer(f"Приобретено: {s_data['name']}!", show_alert=True)
    await skins_shop_menu(callback)

@router.callback_query(F.data == "home_medals_show")
async def show_medals_board(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    home = user.get('home_data', {})
    medals = home.get('medals', [])
    
    text = "🎖️ **Стенд Воинской Славы**\n\n"
    if medals:
        for m in medals:
            text += f"• **{m}**\n"
    else:
        text += "*У вас пока нет медалей за освобождение регионов Камарии.*\n*Примите участие в Войне в меню Походов!*"
        
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад в дом", callback_data="town_home")]])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

# =========================================================
# 📜 РАЗДЕЛ: ЕЖЕДНЕВНЫЕ ЗАДАНИЯ
# =========================================================
@router.callback_query(F.data == "town_quests")
async def show_daily_quests(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    q_data = check_and_generate_quests(user['user_id'])
    quests = q_data.get("quests", [])
    claimed = q_data.get("claimed", False)
    
    text = (
        "📜 **Ежедневные Поручения**\n"
        "Выполняйте задания каждый день, чтобы получать золото и кристаллы!\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
    )
    
    all_completed = True
    for i, q in enumerate(quests, start=1):
        target = q.get('target', 1)
        prog = min(target, q.get('progress', 0))
        is_done = q.get('completed', False) or (prog >= target)
        
        if not is_done:
            all_completed = False
            
        status_icon = "✅" if is_done else "⏳"
        filled = int((prog / target) * 8) if target > 0 else 8
        bar = "█" * filled + "░" * (8 - filled)
        
        text += (
            f"{status_icon} **{i}. {q.get('desc', 'Задание')}**\n"
            f"   └ Прогресс: `[{bar}]` **{prog}/{target}**\n\n"
        )
        
    reward_gold = 150 + user.get('level', 1) * 15
    reward_gems = 3
    
    text += (
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🎁 **Награда за все поручения:**\n"
        f"• **+{reward_gold}** 🪙 Золота\n"
        f"• **+{reward_gems}** 💎 Кристалла\n"
    )
    
    buttons = []
    if all_completed and not claimed:
        buttons.append([InlineKeyboardButton(text="🎁 Забрать награду!", callback_data="claim_quest_reward")])
    elif claimed:
        buttons.append([InlineKeyboardButton(text="✨ Награда уже получена", callback_data="town_quests_claimed_info")])
    else:
        buttons.append([InlineKeyboardButton(text="⏳ Не все задания выполнены", callback_data="town_quests_not_yet")])
        
    buttons.append([InlineKeyboardButton(text="🔙 В лагерь", callback_data="town_back")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data == "claim_quest_reward")
async def claim_quest_reward(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    q_data = check_and_generate_quests(user['user_id'])
    
    if q_data.get("claimed", False):
        return await callback.answer("Награда за сегодня уже получена!", show_alert=True)
        
    quests = q_data.get("quests", [])
    if not all(q.get("completed", False) or q.get("progress", 0) >= q.get("target", 1) for q in quests):
        return await callback.answer("Сначала выполните все задания!", show_alert=True)
        
    reward_gold = 150 + user.get('level', 1) * 15
    reward_gems = 3
    
    q_data["claimed"] = True
    new_gold = user.get('gold', 0) + reward_gold
    new_gems = user.get('gems', 0) + reward_gems
    
    update_user(user['user_id'], gold=new_gold, gems=new_gems, quests_data=q_data)
    await callback.answer(f"Получено: +{reward_gold} 🪙 и +{reward_gems} 💎!", show_alert=True)
    await show_daily_quests(callback)

@router.callback_query(F.data == "town_quests_claimed_info")
async def quests_claimed_info(callback: CallbackQuery):
    await callback.answer("Вы уже получили сегодняшнюю награду! Новые задания появятся завтра.", show_alert=True)

@router.callback_query(F.data == "town_quests_not_yet")
async def quests_not_yet(callback: CallbackQuery):
    await callback.answer("Выполните все 3 задания, чтобы забрать награду!", show_alert=True)
