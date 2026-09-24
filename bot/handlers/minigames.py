import time
import random
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database import get_user, update_user, consume_energy, get_energy_settings

router = Router()

def get_tavern_kb(cost: int = 1):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"⛏️ Шахта", callback_data="mg_mine_start"),
         InlineKeyboardButton(text=f"🎲 Кости", callback_data="mg_dice_start")],
        [InlineKeyboardButton(text=f"🔐 Взлом сундука", callback_data="mg_lock_start"),
         InlineKeyboardButton(text=f"🎣 Озеро (Рыбалка)", callback_data="mg_fish_start")],
        [InlineKeyboardButton(text="🔙 Уйти на площадь", callback_data="town_back")]
    ])

@router.callback_query(F.data == "town_tavern")
async def open_tavern(callback: CallbackQuery):
    await callback.answer()
    
    user = get_user(callback.from_user.id)
    en = user.get('energy', 5)
    
    e_cfg = get_energy_settings(user.get('level', 1))
    max_e = e_cfg['max_energy']
    regen_sec = e_cfg['regen_seconds']
    last_time = user.get('last_energy_time', 0)
    
    if en < max_e:
        elapsed = time.time() - last_time
        left = int(regen_sec - elapsed) if elapsed < regen_sec else 0
        timer = f"*(+1 ⚡ через {left // 60} мин)*"
    else:
        timer = "*(Максимум)*"
    
    text = (f"🍻 **Таверна «Хмельной Голем»**\n\n"
            f"Здесь можно скоротать время и заработать ресурсы.\n\n"
            f"⚡ **Энергия:** {en}/{max_e} {timer}\n"
            f"💰 **Золото:** {user.get('gold', 0)}\n\n"
            f"Во что будем играть?")
    await callback.message.edit_text(text, reply_markup=get_tavern_kb(e_cfg['cost_minigame']), parse_mode="Markdown")

# ==========================================
# --- 1. ШАХТА (Раскопки) ---
# ==========================================
@router.callback_query(F.data == "mg_mine_start")
async def mine_start(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    e_cfg = get_energy_settings(user.get('level', 1))
    cost = e_cfg["cost_minigame"]
    
    text = (
        "⛏️ **Заброшенная Шахта**\n\n"
        "Тьма, сырость и звон кирок. Здесь можно найти золото, железо и даже алмазы!\n"
        "Но будьте осторожны: одно неверное движение, и свод обрушится.\n\n"
        f"Стоимость спуска: **{cost} ⚡** (Вам дадут 3 кирки для раскопок)."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"⛏ Начать раскопки ({cost} ⚡)", callback_data="mg_mine_play")],
        [InlineKeyboardButton(text="🔙 Назад в таверну", callback_data="town_tavern")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data == "mg_mine_play")
async def mine_play(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    e_cfg = get_energy_settings(user.get('level', 1))
    cost = e_cfg["cost_minigame"]
    
    if not consume_energy(user['user_id'], cost):
        return await callback.answer(f"Недостаточно энергии (нужно {cost} ⚡)!", show_alert=True)
    
    await callback.answer()
    
    pool = ["gold", "gold", "gold", "iron", "iron", "gem", "empty", "empty", "bomb"]
    random.shuffle(pool)
    
    home = user.get('home_data', {})
    home['mine_grid'] = pool
    home['mine_opened'] = [False] * 9
    home['mine_picks'] = 3
    update_user(user['user_id'], home_data=home)
    
    await render_mine(callback, user)

async def render_mine(callback: CallbackQuery, user: dict):
    home = user.get('home_data', {})
    opened = home.get('mine_opened', [False]*9)
    grid = home.get('mine_grid', ["empty"]*9)
    picks = home.get('mine_picks', 0)
    
    icons = {"gold": "🪙", "iron": "📦", "gem": "💎", "empty": "🕸", "bomb": "💥"}
    buttons = []
    row = []
    for i in range(9):
        if opened[i]:
            row.append(InlineKeyboardButton(text=icons.get(grid[i], "❓"), callback_data="mg_mine_noop"))
        else:
            row.append(InlineKeyboardButton(text="🪨", callback_data=f"mg_mine_dig_{i}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
            
    buttons.append([InlineKeyboardButton(text="🏃 Уйти из шахты", callback_data="mg_mine_start")])
    
    text = f"⛏️ **Заброшенная Шахта**\nОсталось взмахов киркой: **{picks}**\n\nКопайте осторожно, можно наткнуться на обвал!"
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data == "mg_mine_noop")
async def mine_noop(callback: CallbackQuery):
    await callback.answer("Эта ячейка уже раскопана!", show_alert=False)

@router.callback_query(F.data.startswith("mg_mine_dig_"))
async def mine_dig(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    idx = int(callback.data.split("_")[-1])
    home = user.get('home_data', {})
    
    if home.get('mine_picks', 0) <= 0: return await callback.answer("Кирки сломались!", show_alert=True)
    if home['mine_opened'][idx]: return await callback.answer("Здесь уже раскопано!", show_alert=True)
        
    home['mine_opened'][idx] = True
    home['mine_picks'] -= 1
    found = home['mine_grid'][idx]
    
    if found == "bomb":
        dmg = int(user.get('max_hp', 100) * 0.2)
        user['hp'] = max(1, user.get('hp', 100) - dmg)
        home['mine_picks'] = 0 
        update_user(user['user_id'], hp=user['hp'], home_data=home)
        await callback.answer(f"💥 ОБВАЛ! Вы потеряли {dmg} ХП!", show_alert=True)
        return await mine_start(callback) 
        
    elif found == "gold":
        reward = random.randint(15, 30)
        user['gold'] = user.get('gold', 0) + reward
        await callback.answer(f"🪙 Найдено {reward} золота!")
    elif found == "iron":
        inv = user.get('inventory', {})
        inv.setdefault("materials", {})["iron_ingot"] = inv.get("materials", {}).get("iron_ingot", 0) + 1
        user['inventory'] = inv
        await callback.answer("📦 Найдена железная руда!")
    elif found == "gem":
        user['gems'] = user.get('gems', 0) + 1
        await callback.answer("💎 Вы откопали АЛМАЗ!", show_alert=True)
    else:
        await callback.answer("🕸 Здесь пусто...")
        
    update_user(user['user_id'], gold=user.get('gold', 0), gems=user.get('gems', 0), inventory=user.get('inventory', {}), home_data=home)
    
    if home['mine_picks'] == 0:
        await callback.answer("Жила истощилась. Инструменты сломались.", show_alert=True)
        return await mine_start(callback)
        
    await render_mine(callback, user)


# ==========================================
# --- 2. КОСТИ (Азарт) ---
# ==========================================
@router.callback_query(F.data == "mg_dice_start")
async def dice_start(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    e_cfg = get_energy_settings(user.get('level', 1))
    cost = e_cfg["cost_minigame"]
    
    text = (
        "🎲 **Стол для игры в Кости**\n\n"
        "Трактирщик хитро улыбается и трясет стаканчик с костями.\n"
        "Правила просты: у кого больше — тот забирает банк!\n\n"
        f"Ставка: **50 🪙**\n"
        f"Стоимость игры: **{cost} ⚡**"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🎲 Бросить кости ({cost} ⚡ + 50 🪙)", callback_data="mg_dice_play")],
        [InlineKeyboardButton(text="🔙 Назад в таверну", callback_data="town_tavern")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data == "mg_dice_play")
async def dice_play(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    e_cfg = get_energy_settings(user.get('level', 1))
    cost = e_cfg["cost_minigame"]
    
    if user.get('gold', 0) < 50: return await callback.answer("У вас нет 50 золота для ставки!", show_alert=True)
    if not consume_energy(user['user_id'], cost): return await callback.answer(f"Недостаточно энергии (нужно {cost} ⚡)!", show_alert=True)
    
    await callback.answer()
    
    user['gold'] = user.get('gold', 0) - 50
    p_roll = random.randint(1, 6) + random.randint(1, 6)
    b_roll = random.randint(1, 6) + random.randint(1, 6)
    
    if p_roll > b_roll:
        user['gold'] += 100
        msg = f"🎉 **Вы выиграли!** (+50 чистыми)"
    elif p_roll == b_roll:
        user['gold'] += 50
        msg = f"🤝 **Ничья.** (Ставка возвращена)"
    else:
        msg = f"💀 **Вы проиграли.** (-50 золота)"
        
    update_user(user['user_id'], gold=user['gold'])
    
    text = (f"🎲 **Игра в Кости**\n\n"
            f"Вы бросили: **{p_roll}**\n"
            f"Трактирщик бросил: **{b_roll}**\n\n{msg}")
            
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🎲 Сыграть еще ({cost} ⚡ + 50 🪙)", callback_data="mg_dice_play")],
        [InlineKeyboardButton(text="🔙 В подменю костей", callback_data="mg_dice_start")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")


# ==========================================
# --- 3. ВЗЛОМ ЗАМКА (Быки и Коровы) ---
# ==========================================
@router.callback_query(F.data == "mg_lock_start")
async def lock_start(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    e_cfg = get_energy_settings(user.get('level', 1))
    cost = e_cfg["cost_minigame"]
    
    text = (
        "🔐 **Взлом древнего сундука**\n\n"
        "В углу таверны стоит загадочный сундук с цифровым замком.\n"
        "Нужно угадать 3 неповторяющиеся цифры (от 1 до 9).\n\n"
        "🟢 — цифра на своем месте\n"
        "🟡 — цифра есть, но на другом месте\n\n"
        f"Стоимость попытки: **{cost} ⚡** (Дается 5 отмычек)."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🔐 Начать взлом ({cost} ⚡)", callback_data="mg_lock_play")],
        [InlineKeyboardButton(text="🔙 Назад в таверну", callback_data="town_tavern")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data == "mg_lock_play")
async def lock_play(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    e_cfg = get_energy_settings(user.get('level', 1))
    cost = e_cfg["cost_minigame"]
    
    if not consume_energy(user['user_id'], cost): return await callback.answer(f"Недостаточно энергии (нужно {cost} ⚡)!", show_alert=True)
    
    await callback.answer()
    
    code = random.sample([str(i) for i in range(1, 10)], 3)
    home = user.get('home_data', {})
    home['lock_code'] = "".join(code)
    home['lock_attempts'] = 5
    home['lock_history'] = ""
    home['lock_input'] = ""
    update_user(user['user_id'], home_data=home)
    
    await render_lock(callback, user)

async def render_lock(callback: CallbackQuery, user: dict):
    home = user.get('home_data', {})
    
    text = f"🔐 **Взлом древнего сундука**\nОсталось отмычек (попыток): **{home.get('lock_attempts', 0)}**\n\n"
    if home.get('lock_history'): text += f"📜 *История попыток:*\n{home['lock_history']}\n"
    
    current = home.get('lock_input', "")
    display = current + "_" * (3 - len(current))
    text += f"Ввод: `[ {display[0]} | {display[1]} | {display[2]} ]`"
    
    buttons = []
    row = []
    for i in range(1, 10):
        row.append(InlineKeyboardButton(text=str(i), callback_data=f"mg_lock_btn_{i}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    buttons.append([
        InlineKeyboardButton(text="❌ Сброс", callback_data="mg_lock_btn_clear"),
        InlineKeyboardButton(text="🏃 Уйти", callback_data="mg_lock_start")
    ])
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data.startswith("mg_lock_btn_"))
async def lock_input(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    btn = callback.data.split("_")[-1]
    home = user.get('home_data', {})
    
    if btn == "clear":
        home['lock_input'] = ""
        update_user(user['user_id'], home_data=home)
        await callback.answer("Ввод сброшен")
        return await render_lock(callback, user)
        
    current_input = home.get('lock_input', "")
    if len(current_input) < 3:
        if btn in current_input:
            return await callback.answer("Цифры не повторяются!", show_alert=True)
        home['lock_input'] = current_input + btn
        
    if len(home['lock_input']) == 3:
        guess = home['lock_input']
        secret = home.get('lock_code', "123")
        bulls = sum(1 for i in range(3) if guess[i] == secret[i])
        cows = sum(1 for i in range(3) if guess[i] in secret and guess[i] != secret[i])
        
        if bulls == 3:
            user['gold'] = user.get('gold', 0) + 300
            user['gems'] = user.get('gems', 0) + 3
            inv = user.get('inventory', {})
            inv.setdefault("materials", {})["epic_token"] = inv.get("materials", {}).get("epic_token", 0) + 1
            update_user(user['user_id'], gold=user['gold'], gems=user['gems'], inventory=inv)
            text = f"🎉 **СУНДУК ОТКРЫТ!**\nКод был `{secret}`.\n\nВы нашли:\n💰 300 Золота\n💎 3 Алмаза\n🎫 Эпический жетон!"
            await callback.answer()
            return await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Сыграть еще", callback_data="mg_lock_start")],
                [InlineKeyboardButton(text="🔙 В таверну", callback_data="town_tavern")]
            ]), parse_mode="Markdown")
            
        home['lock_history'] = home.get('lock_history', "") + f"`{guess}` ➡️ 🟢 Точно: {bulls} | 🟡 Рядом: {cows}\n"
        home['lock_attempts'] -= 1
        home['lock_input'] = ""
        
        if home['lock_attempts'] <= 0:
            text = f"🔒 **Замок заклинило!**\nПравильный код был `{secret}`.\nОтмычки сломаны."
            update_user(user['user_id'], home_data=home)
            await callback.answer("Вы провалили взлом!", show_alert=True)
            return await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Попробовать другой сундук", callback_data="mg_lock_start")],
                [InlineKeyboardButton(text="🔙 В таверну", callback_data="town_tavern")]
            ]), parse_mode="Markdown")
            
    update_user(user['user_id'], home_data=home)
    await callback.answer()
    await render_lock(callback, user)


# ==========================================
# --- 4. РЫБАЛКА (Натяжение лески) ---
# ==========================================
@router.callback_query(F.data == "mg_fish_start")
async def fish_start(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    e_cfg = get_energy_settings(user.get('level', 1))
    cost = e_cfg["cost_minigame"]
    
    text = (
        "🎣 **Подземное озеро**\n\n"
        "В дальнем углу подвала таверны есть выход к подземной реке.\n"
        "Закидывайте удочку и тяните леску! Главное — не порвать её (до 100%).\n"
        "Чем сильнее натянута леска перед подсечкой, тем ценнее улов:\n\n"
        "🐟 `50-79%` — Обычная рыба\n"
        "💎 `80-100%` — Редкий сундук\n"
        "💥 `>100%` — Леска рвется!\n\n"
        f"Стоимость заброса: **{cost} ⚡**"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🎣 Закинуть удочку ({cost} ⚡)", callback_data="mg_fish_play")],
        [InlineKeyboardButton(text="🔙 Назад в таверну", callback_data="town_tavern")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data == "mg_fish_play")
async def fish_play(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    e_cfg = get_energy_settings(user.get('level', 1))
    cost = e_cfg["cost_minigame"]
    
    if not consume_energy(user['user_id'], cost):
        return await callback.answer(f"Недостаточно энергии (нужно {cost} ⚡)!", show_alert=True)
    
    await callback.answer()
    
    home = user.get('home_data', {})
    home['fish_tension'] = 0
    update_user(user['user_id'], home_data=home)
    
    await render_fish(callback, user)

async def render_fish(callback: CallbackQuery, user: dict):
    home = user.get('home_data', {})
    tension = home.get('fish_tension', 0)
    
    filled = min(10, int((tension / 100) * 10))
    bar = "🟥" * filled + "⬜" * (10 - filled)
    
    status = "Надежно" if tension < 50 else "Опасно!" if tension >= 80 else "Натянуто"
    
    text = (
        f"🎣 **Рыбалка**\n\n"
        f"Натяжение лески: **{tension}%** ({status})\n"
        f"[{bar}]\n\n"
        "Тяните осторожно, или доставайте улов!"
    )
    
    buttons = [
        [InlineKeyboardButton(text="🎣 Тянуть катушку (+15-35%)", callback_data="mg_fish_pull")],
        [InlineKeyboardButton(text="🤚 Подсечь (Достать улов)", callback_data="mg_fish_catch")]
    ]
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data == "mg_fish_pull")
async def fish_pull(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    home = user.get('home_data', {})
    tension = home.get('fish_tension', 0)
    
    pull_power = random.randint(15, 35)
    tension += pull_power
    
    if tension > 100:
        home['fish_tension'] = 0
        update_user(user['user_id'], home_data=home)
        await callback.answer("💥 Леска порвалась!", show_alert=True)
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Попробовать еще", callback_data="mg_fish_start")],
            [InlineKeyboardButton(text="🔙 В таверну", callback_data="town_tavern")]
        ])
        return await callback.message.edit_text(f"💥 **Срыв!**\n\nЛеска не выдержала натяжения в {tension}% и лопнула. Рыба ушла...", reply_markup=kb, parse_mode="Markdown")
        
    home['fish_tension'] = tension
    update_user(user['user_id'], home_data=home)
    await callback.answer()
    await render_fish(callback, user)

@router.callback_query(F.data == "mg_fish_catch")
async def fish_catch(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    home = user.get('home_data', {})
    tension = home.get('fish_tension', 0)
    
    home['fish_tension'] = 0
    
    if tension < 50:
        msg = "Вы вытащили **Ржавый башмак**... Ничего ценного."
        reward = ""
    elif 50 <= tension < 80:
        user['gold'] = user.get('gold', 0) + 50
        inv = user.get('inventory', {})
        inv.setdefault("potions", []).append("Сытное рагу")
        user['inventory'] = inv
        msg = "Вы вытащили **Озерную форель**!"
        reward = "\n💰 +50 Золота\n🍲 +1 Сытное рагу"
    else:
        user['gold'] = user.get('gold', 0) + 150
        user['gems'] = user.get('gems', 0) + 1
        msg = "Вы вытащили со дна **Затопленный сундук**!"
        reward = "\n💰 +150 Золота\n💎 +1 Алмаз"
        
    update_user(user['user_id'], gold=user.get('gold', 0), gems=user.get('gems', 0), inventory=user.get('inventory', {}), home_data=home)
    await callback.answer("Улов пойман!", show_alert=False)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Закинуть еще", callback_data="mg_fish_start")],
        [InlineKeyboardButton(text="🔙 В таверну", callback_data="town_tavern")]
    ])
    await callback.message.edit_text(f"🎣 **Результат рыбалки (Натяжение: {tension}%)**\n\n{msg}{reward}", reply_markup=kb, parse_mode="Markdown")

