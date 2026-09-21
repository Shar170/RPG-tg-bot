import random
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database import get_user, update_user, consume_energy

router = Router()

def get_tavern_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⛏️ Шахта (1 ⚡)", callback_data="mg_mine_start")],
        [InlineKeyboardButton(text="🎲 Кости (1 ⚡ + 50🪙)", callback_data="mg_dice_start")],
        [InlineKeyboardButton(text="🔐 Взлом сундука (1 ⚡)", callback_data="mg_lock_start")],
        [InlineKeyboardButton(text="🔙 Уйти на площадь", callback_data="town_back")]
    ])

@router.callback_query(F.data == "town_tavern")
async def open_tavern(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    en = user['energy']
    timer = f"*(+1 ⚡ через {user['next_energy_in'] // 60} мин)*" if en < 5 else "*(Максимум)*"
    
    text = (f"🍻 **Таверна «Хмельной Голем»**\n\n"
            f"Здесь можно скоротать время и заработать ресурсы.\n\n"
            f"⚡ **Энергия:** {en}/5 {timer}\n"
            f"💰 **Золото:** {user['gold']}\n\n"
            f"Во что будем играть?")
    await callback.message.edit_text(text, reply_markup=get_tavern_kb(), parse_mode="Markdown")

# --- 1. ШАХТА (Раскопки) ---
@router.callback_query(F.data == "mg_mine_start")
async def mine_start(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    if not consume_energy(user['user_id']):
        return await callback.answer("Недостаточно энергии!", show_alert=True)
    
    # Генерация сетки 3x3: 3 золота, 2 железа, 1 алмаз, 2 пустых, 1 обвал
    pool = ["gold", "gold", "gold", "iron", "iron", "gem", "empty", "empty", "bomb"]
    random.shuffle(pool)
    
    home = user['home_data']
    home['mine_grid'] = pool
    home['mine_opened'] = [False] * 9
    home['mine_picks'] = 3
    update_user(user['user_id'], home_data=home)
    
    await render_mine(callback, user)

async def render_mine(callback: CallbackQuery, user: dict):
    home = user['home_data']
    opened = home['mine_opened']
    grid = home['mine_grid']
    picks = home['mine_picks']
    
    icons = {"gold": "🪙", "iron": "📦", "gem": "💎", "empty": "🕸", "bomb": "💥"}
    buttons = []
    row = []
    for i in range(9):
        if opened[i]:
            row.append(InlineKeyboardButton(text=icons[grid[i]], callback_data="mg_mine_noop"))
        else:
            row.append(InlineKeyboardButton(text="🪨", callback_data=f"mg_mine_dig_{i}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
            
    buttons.append([InlineKeyboardButton(text="🏃 Уйти из шахты", callback_data="town_tavern")])
    
    text = f"⛏️ **Заброшенная Шахта**\nОсталось взмахов киркой: **{picks}**\n\nКопайте осторожно, можно наткнуться на обвал!"
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data.startswith("mg_mine_dig_"))
async def mine_dig(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    idx = int(callback.data.split("_")[-1])
    home = user['home_data']
    
    if home.get('mine_picks', 0) <= 0: return await callback.answer("Кирки сломались!", show_alert=True)
    if home['mine_opened'][idx]: return await callback.answer("Здесь уже раскопано!", show_alert=True)
        
    home['mine_opened'][idx] = True
    home['mine_picks'] -= 1
    found = home['mine_grid'][idx]
    
    if found == "bomb":
        dmg = int(user['max_hp'] * 0.2)
        user['hp'] = max(1, user['hp'] - dmg)
        update_user(user['user_id'], hp=user['hp'], home_data=home)
        await callback.answer(f"💥 ОБВАЛ! Вы потеряли {dmg} ХП!", show_alert=True)
        return await open_tavern(callback) # Выбрасываем в таверну
        
    elif found == "gold":
        reward = random.randint(15, 30)
        user['gold'] += reward
        await callback.answer(f"🪙 Найдено {reward} золота!")
    elif found == "iron":
        user['inventory'].setdefault("materials", {})["iron_ingot"] = user['inventory'].get("materials", {}).get("iron_ingot", 0) + 1
        await callback.answer("📦 Найдена железная руда!")
    elif found == "gem":
        user['gems'] += 1
        await callback.answer("💎 Вы откопали АЛМАЗ!", show_alert=True)
        
    update_user(user['user_id'], gold=user['gold'], gems=user['gems'], inventory=user['inventory'], home_data=home)
    
    if home['mine_picks'] == 0:
        await callback.answer("Кирка сломалась. Возвращаемся в таверну.")
        return await open_tavern(callback)
        
    await render_mine(callback, user)

# --- 2. КОСТИ (Азарт) ---
@router.callback_query(F.data == "mg_dice_start")
async def dice_start(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    if user['gold'] < 50: return await callback.answer("У вас нет 50 золота для ставки!", show_alert=True)
    if not consume_energy(user['user_id']): return await callback.answer("Недостаточно энергии!", show_alert=True)
        
    user['gold'] -= 50
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
        [InlineKeyboardButton(text="🎲 Сыграть еще (1⚡ + 50🪙)", callback_data="mg_dice_start")],
        [InlineKeyboardButton(text="🔙 В таверну", callback_data="town_tavern")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

# --- 3. ВЗЛОМ ЗАМКА (Быки и Коровы) ---
@router.callback_query(F.data == "mg_lock_start")
async def lock_start(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    if not consume_energy(user['user_id']): return await callback.answer("Недостаточно энергии!", show_alert=True)
        
    code = random.sample([str(i) for i in range(1, 10)], 3) # 3 уникальные цифры
    home = user['home_data']
    home['lock_code'] = "".join(code)
    home['lock_attempts'] = 5
    home['lock_history'] = ""
    home['lock_input'] = ""
    update_user(user['user_id'], home_data=home)
    
    await render_lock(callback, user)

async def render_lock(callback: CallbackQuery, user: dict):
    home = user['home_data']
    
    text = f"🔐 **Взлом древнего сундука**\nОсталось отмычек (попыток): **{home['lock_attempts']}**\n\n"
    if home['lock_history']: text += f"📜 *История попыток:*\n{home['lock_history']}\n"
    
    current = home['lock_input']
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
        InlineKeyboardButton(text="🏃 Уйти", callback_data="town_tavern")
    ])
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data.startswith("mg_lock_btn_"))
async def lock_input(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    btn = callback.data.split("_")[-1]
    home = user['home_data']
    
    if btn == "clear":
        home['lock_input'] = ""
        update_user(user['user_id'], home_data=home)
        return await render_lock(callback, user)
        
    if len(home['lock_input']) < 3:
        if btn in home['lock_input']:
            return await callback.answer("Цифры не повторяются!", show_alert=True)
        home['lock_input'] += btn
        
    if len(home['lock_input']) == 3:
        # Проверка (Быки и Коровы)
        guess = home['lock_input']
        secret = home['lock_code']
        bulls = sum(1 for i in range(3) if guess[i] == secret[i])
        cows = sum(1 for i in range(3) if guess[i] in secret and guess[i] != secret[i])
        
        if bulls == 3:
            user['gold'] += 300
            user['gems'] += 3
            user['inventory'].setdefault("materials", {})["epic_token"] = user['inventory'].get("materials", {}).get("epic_token", 0) + 1
            update_user(user['user_id'], gold=user['gold'], gems=user['gems'], inventory=user['inventory'])
            text = f"🎉 **СУНДУК ОТКРЫТ!**\nКод был `{secret}`.\n\nВы нашли:\n💰 300 Золота\n💎 3 Алмаза\n🎫 Эпический жетон!"
            return await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 В таверну", callback_data="town_tavern")]]), parse_mode="Markdown")
            
        home['lock_history'] += f"`{guess}` ➡️ 🟢 Точно: {bulls} | 🟡 Рядом: {cows}\n"
        home['lock_attempts'] -= 1
        home['lock_input'] = ""
        
        if home['lock_attempts'] == 0:
            text = f"🔒 **Замок заклинило!**\nПравильный код был `{secret}`.\nОтмычки сломаны."
            update_user(user['user_id'], home_data=home)
            return await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 В таверну", callback_data="town_tavern")]]), parse_mode="Markdown")
            
    update_user(user['user_id'], home_data=home)
    await render_lock(callback, user)
