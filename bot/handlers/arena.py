import time
import json
import random
import asyncio
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database import (
    get_user, update_user, get_connection, get_pvp_match, update_pvp_match, 
    remove_from_queue, track_stat, add_global_event, get_item, get_setting, calculate_damage_received
)

router = Router()

@router.callback_query(F.data == "town_arena")
async def arena_menu(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    if user['level'] < 10:
        return await callback.answer("Арена доступна только с 10 уровня!", show_alert=True)
        
    stats = user.get('home_data', {}).get('stats', {})
    wins = stats.get('pvp_wins', 0)
    
    text = (
        "⚔️ **Арена Чемпионов**\n\n"
        "Взнос за участие: **100 🪙**\n"
        "Победитель забирает **200 🪙** (свой взнос + взнос врага).\n\n"
        "Подбор ищет соперника максимально близкого к вашему уровню. Члены одного клана не могут встретиться на арене.\n\n"
        f"🏆 Ваши победы: **{wins}**"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔎 Встать в очередь (100 🪙)", callback_data="arena_join")],
        [InlineKeyboardButton(text="🔙 В лагерь", callback_data="town_back")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data == "arena_join")
async def arena_join(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    
    if user['gold'] < 100:
        return await callback.answer("У вас нет 100 золота для взноса!", show_alert=True)
        
    my_lvl = user['level']
    my_clan = user.get('clan_id', 0)
    
    user['gold'] -= 100
    update_user(user['user_id'], gold=user['gold'])
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT user_id FROM arena_queue 
            WHERE user_id != ? AND (clan_id != ? OR clan_id = 0)
            ORDER BY ABS(level - ?) ASC LIMIT 1
        """, (user['user_id'], my_clan, my_lvl))
        match = cursor.fetchone()
        
        if not match:
            cursor.execute("SELECT user_id FROM users WHERE is_bot=1 AND ABS(level - ?) <= 5 ORDER BY RANDOM() LIMIT 1", (my_lvl,))
            bot_match = cursor.fetchone()
            if bot_match:
                match = bot_match
        
        if match:
            opp_id = match[0]
            cursor.execute("DELETE FROM arena_queue WHERE user_id = ?", (opp_id,))
            
            opp = get_user(opp_id)
            initial_state = json.dumps({"distance": "close", "p1": {}, "p2": {}})
            cursor.execute("""
                INSERT INTO pvp_matches (p1_id, p2_id, p1_hp, p2_hp, p1_max, p2_max, p1_ap, p2_ap, turn, log, match_state, last_action_time) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (user['user_id'], opp_id, user['max_hp'], opp['max_hp'], user['max_hp'], opp['max_hp'], 3, 3, user['user_id'], "⚔️ Битва началась!", initial_state, time.time()))
            match_id = cursor.lastrowid
            conn.commit()
            
            update_user(user['user_id'], state='STATE_PVP', combat_data={"pvp_match_id": match_id})
            if opp.get('is_bot', 0) == 0:
                update_user(opp_id, state='STATE_PVP', combat_data={"pvp_match_id": match_id})
            
            await render_pvp(callback.bot, match_id)
            await callback.answer()
        else:
            cursor.execute("INSERT OR REPLACE INTO arena_queue (user_id, level, clan_id, joined_at) VALUES (?, ?, ?, ?)", 
                           (user['user_id'], my_lvl, my_clan, time.time()))
            conn.commit()
            
            update_user(user['user_id'], state='STATE_ARENA_QUEUE')
            kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Отменить поиск", callback_data="arena_cancel")]])
            await callback.message.edit_text("⏳ **Поиск противника...**\nВзнос 100 🪙 уплачен. Ожидаем бойца.", reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data == "arena_cancel")
async def arena_cancel(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    remove_from_queue(user['user_id'])
    
    user['gold'] += 100
    update_user(user['user_id'], state='STATE_TOWN', gold=user['gold'])
    
    await callback.answer("Поиск отменен, 100 🪙 возвращены.", show_alert=True)
    await arena_menu(callback)


# --- ДВИЖОК PVP ---
def render_effects_badge(buffs: dict) -> str:
    badges = []
    if buffs.get('buff_armor', 0) > 0: badges.append(f"🛡️ Броня +{buffs['buff_armor']}")
    if buffs.get('buff_str', 0) > 0: badges.append(f"⚔️ Сила +{buffs['buff_str']}")
    if buffs.get('buff_dodge', 0) > 0: badges.append("💨 Уворот")
    if buffs.get('debuff_blind', 0) > 0: badges.append("👁️ Слепота")
    if buffs.get('debuff_fragile', 0) > 0: badges.append("💔 Хрупкость")
    if buffs.get('debuff_vuln', 0) > 0: badges.append("🎯 Уязвимость")
    if buffs.get('dot_burn', 0) > 0: badges.append("🔥 Горение")
    if buffs.get('dot_poison', 0) > 0: badges.append("🟢 Яд")
    if buffs.get('dot_bleed', 0) > 0: badges.append("🩸 Кровотечение")
    if buffs.get('stun', 0) > 0: badges.append("💫 Оглушение")
    return " | ".join(badges) if badges else "Нет"

def get_pvp_kb(is_my_turn: bool, ap: int, distance: str):
    if not is_my_turn:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⏳ Обновить статус (Проверка AFK)", callback_data="pvp_noop")],
            [InlineKeyboardButton(text="🏳️ Сдаться", callback_data="pvp_surrender")]
        ])
    
    move_text = "🏃 Отступить (1 ОД)" if distance == "close" else "⚔️ Сблизиться (1 ОД)"
    
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗡️ Атака (2 ОД)" if ap >= 2 else "❌ Атака (2 ОД)", callback_data="pvp_attack")],
        [InlineKeyboardButton(text=move_text if ap >= 1 else "❌ Смена позиции (1 ОД)", callback_data="pvp_move")],
        [InlineKeyboardButton(text="🧪 Инвентарь (1 ОД)", callback_data="pvp_potion"), InlineKeyboardButton(text="⏳ Конец хода", callback_data="pvp_end_turn")],
        [InlineKeyboardButton(text="🏳️ Сдаться", callback_data="pvp_surrender")]
    ])

@router.callback_query(F.data == "pvp_noop")
async def pvp_noop(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    match_id = user.get('combat_data', {}).get('pvp_match_id')
    match = get_pvp_match(match_id)
    
    if not match: 
        return await callback.answer("Матч не найден!", show_alert=True)
        
    elapsed = time.time() - match.get('last_action_time', time.time())
    if elapsed > 300:
        await end_pvp_draw(callback.bot, match_id, "Один из игроков покинул Арену (AFK 5 минут).")
        return await callback.answer("Техническая ничья по тайм-ауту.")
        
    left = int(300 - elapsed)
    await callback.answer(f"Сейчас ход противника! До авто-ничьей (AFK): {left} сек.", show_alert=False)

async def render_pvp(bot, match_id: int):
    match = get_pvp_match(match_id)
    if not match: return
    
    p1, p2 = get_user(match['p1_id']), get_user(match['p2_id'])
    state = json.loads(match.get('match_state', '{}'))
    dist_str = "УПОР (Ближний бой)" if state.get('distance', 'close') == "close" else "ИЗДАЛЕКА (Дальний бой)"
    
    p1_eff = render_effects_badge(state.get('p1', {}))
    p2_eff = render_effects_badge(state.get('p2', {}))
    
    p1_turn = (match['turn'] == p1['user_id'])
    p1_text = (
        f"⚔️ **Арена (PvP)**\n📏 Дистанция: **{dist_str}**\n\n"
        f"👤 Вы: {match['p1_hp']}/{match['p1_max']} HP | ОД: {'🟢'*match['p1_ap']}\n✨ Эффекты: {p1_eff}\n\n"
        f"🛡️ {p2['username']}: {match['p2_hp']}/{match['p2_max']} HP | ОД: {'🟢'*match['p2_ap']}\n✨ Эффекты: {p2_eff}\n\n"
        f"💬 {match['log']}"
    )
    
    p2_turn = (match['turn'] == p2['user_id'])
    p2_text = (
        f"⚔️ **Арена (PvP)**\n📏 Дистанция: **{dist_str}**\n\n"
        f"👤 Вы: {match['p2_hp']}/{match['p2_max']} HP | ОД: {'🟢'*match['p2_ap']}\n✨ Эффекты: {p2_eff}\n\n"
        f"🛡️ {p1['username']}: {match['p1_hp']}/{match['p1_max']} HP | ОД: {'🟢'*match['p1_ap']}\n✨ Эффекты: {p1_eff}\n\n"
        f"💬 {match['log']}"
    )
    
    if p1.get('is_bot', 0) == 0:
        try: await bot.edit_message_text(p1_text, chat_id=p1['user_id'], message_id=p1['last_msg_id'], reply_markup=get_pvp_kb(p1_turn, match['p1_ap'], state.get('distance', 'close')), parse_mode="Markdown")
        except Exception: pass
    
    if p2.get('is_bot', 0) == 0:
        try: await bot.edit_message_text(p2_text, chat_id=p2['user_id'], message_id=p2['last_msg_id'], reply_markup=get_pvp_kb(p2_turn, match['p2_ap'], state.get('distance', 'close')), parse_mode="Markdown")
        except Exception: pass

async def end_pvp_match(bot, match_id: int, winner_id: int, loser_id: int, reason_log: str):
    winner = get_user(winner_id)
    loser = get_user(loser_id)
    
    reward = 200
    winner['gold'] += reward
    track_stat(winner_id, 'pvp_wins', 1)
    
    if winner.get('is_bot', 0) == 0:
        update_user(winner_id, state='STATE_TOWN', gold=winner['gold'], combat_data={})
        add_global_event(f"⚔️ Гладиатор **{winner['username']}** одержал славную победу на Арене!")
    if loser.get('is_bot', 0) == 0:
        update_user(loser_id, state='STATE_TOWN', combat_data={})
    
    from handlers.town import get_town_kb
    win_txt = f"🏆 **ПОБЕДА!**\n{reason_log}\nВы забрали банк арены: **+{reward} 🪙**."
    lose_txt = f"☠️ **ПОРАЖЕНИЕ!**\n{reason_log}\nВаш взнос в 100 🪙 достался противнику."
    
    if winner.get('is_bot', 0) == 0:
        try: await bot.edit_message_text(win_txt, chat_id=winner_id, message_id=winner['last_msg_id'], reply_markup=get_town_kb(winner), parse_mode="Markdown")
        except Exception: pass
    if loser.get('is_bot', 0) == 0:
        try: await bot.edit_message_text(lose_txt, chat_id=loser_id, message_id=loser['last_msg_id'], reply_markup=get_town_kb(loser), parse_mode="Markdown")
        except Exception: pass

async def end_pvp_draw(bot, match_id: int, reason_log: str):
    match = get_pvp_match(match_id)
    p1 = get_user(match['p1_id'])
    p2 = get_user(match['p2_id'])
    
    if p1.get('is_bot', 0) == 0: p1['gold'] += 100
    if p2.get('is_bot', 0) == 0: p2['gold'] += 100
    
    if p1.get('is_bot', 0) == 0: update_user(p1['user_id'], state='STATE_TOWN', gold=p1['gold'], combat_data={})
    if p2.get('is_bot', 0) == 0: update_user(p2['user_id'], state='STATE_TOWN', gold=p2['gold'], combat_data={})
    
    from handlers.town import get_town_kb
    draw_txt = f"🤝 **ТЕХНИЧЕСКАЯ НИЧЬЯ!**\n{reason_log}\nВам возвращен взнос 100 🪙."
    
    if p1.get('is_bot', 0) == 0:
        try: await bot.edit_message_text(draw_txt, chat_id=p1['user_id'], message_id=p1['last_msg_id'], reply_markup=get_town_kb(p1), parse_mode="Markdown")
        except Exception: pass
    if p2.get('is_bot', 0) == 0:
        try: await bot.edit_message_text(draw_txt, chat_id=p2['user_id'], message_id=p2['last_msg_id'], reply_markup=get_town_kb(p2), parse_mode="Markdown")
        except Exception: pass

# --- ЛОГИКА ИСКУССТВЕННОГО ИНТЕЛЛЕКТА (БОТА) ---
async def process_bot_turn(bot, match_id: int):
    await asyncio.sleep(random.uniform(2.5, 6.0))
    
    match = get_pvp_match(match_id)
    if not match: return
    
    bot_user = get_user(match['turn'])
    if bot_user.get('is_bot', 0) == 0: return 
        
    is_p1 = (bot_user['user_id'] == match['p1_id'])
    ap_key = 'p1_ap' if is_p1 else 'p2_ap'
    
    if match[ap_key] < 2:
        return await finalize_bot_turn(bot, match_id, is_p1, bot_user)
        
    state = json.loads(match.get('match_state', '{}'))
    my_buffs = state.get('p1' if is_p1 else 'p2', {})
    opp_buffs = state.get('p2' if is_p1 else 'p1', {})
    
    log = ""
    my_hp = match['p1_hp'] if is_p1 else 'p2_hp'
    my_max = match['p1_max'] if is_p1 else 'p2_max'
    
    if match[my_hp] < (match[my_max] * 0.3) and match[ap_key] >= 1:
        match[my_hp] += int(match[my_max] * 0.25)
        match[ap_key] -= 1
        log = f"🧪 {bot_user['username']} выпил зелье лечения!\n"
    
    if state.get('distance', 'close') == "far" and match[ap_key] >= 1:
        state['distance'] = "close"
        match[ap_key] -= 1
        log += f"⚔️ {bot_user['username']} бросился вперед! Ближний бой.\n"
        
    if match[ap_key] >= 2:
        if opp_buffs.get('buff_dodge', 0) > 0 and random.random() < 0.35:
            log += f"💨 Противник ловко увернулся от атаки {bot_user['username']}!"
            dmg = 0
        else:
            row_mult = 1.0 if state.get('distance', 'close') == "close" else 0.5
            
            # Бот теперь тоже использует оружие! Если его нет, бьет кулаками.
            inv = bot_user['inventory']
            weapon_id = inv.get("equipment", {}).get("weapon")
            weapon_data = get_item(weapon_id) if weapon_id else None
            
            base_dmg = int(get_setting("base_unarmed_dmg", "5")) + (bot_user.get('level', 1) * 2) + random.randint(0, 3)
            w_dmg = weapon_data['stats'].get('dmg', 0) if weapon_data else 0
            
            raw_dmg = int((base_dmg + w_dmg) * row_mult)
            if opp_buffs.get('debuff_vuln', 0) > 0: raw_dmg = int(raw_dmg * 1.25)
            
            # Считаем броню игрока
            opp_user = get_user(match['p2_id'] if is_p1 else match['p1_id'])
            opp_inv = opp_user['inventory']
            opp_armor_id = opp_inv.get("equipment", {}).get("armor")
            opp_armor_data = get_item(opp_armor_id) if opp_armor_id else None
            base_armor = opp_armor_data['stats'].get('def', 0) if opp_armor_data else 0
            
            if opp_buffs.get('debuff_fragile', 0) > 0: base_armor = int(base_armor * 0.5)
            
            total_armor = base_armor + opp_buffs.get('buff_armor', 0)
            dmg = calculate_damage_received(raw_dmg, total_armor)
            
            log += f"🗡️ {bot_user['username']} пробивает вашу броню на {dmg} урона!"
            
        match[ap_key] -= 2
        if is_p1: match['p2_hp'] -= dmg
        else: match['p1_hp'] -= dmg
            
    if is_p1: update_pvp_match(match_id, p1_hp=match['p1_hp'], p2_hp=match['p2_hp'], p1_ap=match['p1_ap'], match_state=json.dumps(state), log=log, last_action_time=time.time())
    else: update_pvp_match(match_id, p1_hp=match['p1_hp'], p2_hp=match['p2_hp'], p2_ap=match['p2_ap'], match_state=json.dumps(state), log=log, last_action_time=time.time())

    if match['p2_hp' if is_p1 else 'p1_hp'] <= 0:
        return await end_pvp_match(bot, match_id, bot_user['user_id'], match['p2_id' if is_p1 else 'p1_id'], log)
        
    await finalize_bot_turn(bot, match_id, is_p1, bot_user)

async def finalize_bot_turn(bot, match_id: int, is_p1: bool, bot_user: dict):
    match = get_pvp_match(match_id)
    next_turn = match['p2_id'] if is_p1 else match['p1_id']
    
    state = json.loads(match.get('match_state', '{}'))
    opp_key = 'p2' if is_p1 else 'p1'
    opp_buffs = state.setdefault(opp_key, {})
    
    dot_dmg = 0
    if opp_buffs.get('dot_burn', 0) > 0: dot_dmg += 15; opp_buffs['dot_burn'] -= 1
    if opp_buffs.get('dot_poison', 0) > 0: dot_dmg += 12; opp_buffs['dot_poison'] -= 1
    if opp_buffs.get('dot_bleed', 0) > 0: dot_dmg += 10; opp_buffs['dot_bleed'] -= 1
    
    log = match['log'] + f"\n⏳ {bot_user['username']} завершил ход."
    if dot_dmg > 0:
        log += f"\n🩸 Вы получили {dot_dmg} урона от эффектов!"
        if is_p1: match['p2_hp'] -= dot_dmg
        else: match['p1_hp'] -= dot_dmg

    for buff_t in ['buff_armor_t', 'buff_str_t', 'buff_dodge_t', 'debuff_blind', 'debuff_fragile', 'debuff_vuln']:
        if opp_buffs.get(buff_t, 0) > 0:
            opp_buffs[buff_t] -= 1
            if opp_buffs[buff_t] == 0:
                attr = buff_t.replace('_t', '')
                opp_buffs[attr] = 0

    if match['p2_hp'] <= 0: return await end_pvp_match(bot, match_id, match['p1_id'], match['p2_id'], log)
    if match['p1_hp'] <= 0: return await end_pvp_match(bot, match_id, match['p2_id'], match['p1_id'], log)
    
    if is_p1: update_pvp_match(match_id, p1_ap=3, p2_hp=match['p2_hp'], turn=next_turn, match_state=json.dumps(state), log=log, last_action_time=time.time())
    else: update_pvp_match(match_id, p2_ap=3, p1_hp=match['p1_hp'], turn=next_turn, match_state=json.dumps(state), log=log, last_action_time=time.time())
        
    await render_pvp(bot, match_id)


# --- ДЕЙСТВИЯ ИГРОКА ---
@router.callback_query(F.data == "pvp_move")
async def pvp_move(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    match_id = user.get('combat_data', {}).get('pvp_match_id')
    match = get_pvp_match(match_id)
    
    if not match or match['turn'] != user['user_id']: return await callback.answer("Сейчас не ваш ход!", show_alert=True)
        
    is_p1 = (user['user_id'] == match['p1_id'])
    ap_key = 'p1_ap' if is_p1 else 'p2_ap'
    
    if match[ap_key] < 1: return await callback.answer("Недостаточно ОД!", show_alert=True)
    
    state = json.loads(match.get('match_state', '{}'))
    if state.get('distance', 'close') == "close":
        state['distance'] = "far"
        log = f"🏃 {user['username']} разорвал дистанцию! Теперь бой идет издалека."
    else:
        state['distance'] = "close"
        log = f"⚔️ {user['username']} бросился вперед! Ближний бой."
        
    if is_p1: update_pvp_match(match_id, p1_ap=match['p1_ap'] - 1, match_state=json.dumps(state), log=log, last_action_time=time.time())
    else: update_pvp_match(match_id, p2_ap=match['p2_ap'] - 1, match_state=json.dumps(state), log=log, last_action_time=time.time())
        
    await render_pvp(callback.bot, match_id)
    await callback.answer()

@router.callback_query(F.data == "pvp_attack")
async def pvp_attack(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    match_id = user.get('combat_data', {}).get('pvp_match_id')
    match = get_pvp_match(match_id)
    
    if not match or match['turn'] != user['user_id']: return await callback.answer("Сейчас не ваш ход!", show_alert=True)
        
    is_p1 = (user['user_id'] == match['p1_id'])
    ap_key = 'p1_ap' if is_p1 else 'p2_ap'
    
    if match[ap_key] < 2: return await callback.answer("Недостаточно ОД!", show_alert=True)
        
    state = json.loads(match.get('match_state', '{}'))
    my_buffs = state.get('p1' if is_p1 else 'p2', {})
    opp_buffs = state.get('p2' if is_p1 else 'p1', {})
    
    if my_buffs.get('debuff_blind', 0) > 0 and random.random() < 0.4:
        log = f"👁️ {user['username']} ослеплен и промахнулся!"
        dmg = 0
    elif opp_buffs.get('buff_dodge', 0) > 0 and random.random() < 0.35:
        log = f"💨 Противник ловко увернулся от атаки {user['username']}!"
        dmg = 0
    else:
        # Учет экипированного оружия
        inv = user['inventory']
        weapon_id = inv.get("equipment", {}).get("weapon")
        weapon_data = get_item(weapon_id) if weapon_id else None
        
        base_dmg = int(get_setting("base_unarmed_dmg", "5")) + (user.get('level', 1) * 2) + random.randint(0, 3)
        w_dmg = weapon_data['stats'].get('dmg', 0) if weapon_data else 0
        w_range = weapon_data['stats'].get('range', 'melee') if weapon_data else 'melee'
        
        distance = state.get('distance', 'close')
        row_mult = (1.0 if distance == "close" else 0.3) if w_range == "melee" else (1.0 if distance == "far" else 0.5)
        
        extra_str = my_buffs.get('buff_str', 0)
        raw_dmg = int((base_dmg + w_dmg + extra_str) * row_mult)
        
        if opp_buffs.get('debuff_vuln', 0) > 0: raw_dmg = int(raw_dmg * 1.25)
        
        # Расчет брони противника
        opp_user = get_user(match['p2_id'] if is_p1 else match['p1_id'])
        opp_inv = opp_user['inventory']
        opp_armor_id = opp_inv.get("equipment", {}).get("armor")
        opp_armor_data = get_item(opp_armor_id) if opp_armor_id else None
        base_armor = opp_armor_data['stats'].get('def', 0) if opp_armor_data else 0
        
        if opp_buffs.get('debuff_fragile', 0) > 0:
            base_armor = int(base_armor * 0.5)
            
        total_armor = base_armor + opp_buffs.get('buff_armor', 0)
        dmg = calculate_damage_received(raw_dmg, total_armor)
        
        log = f"🗡️ {user['username']} пробивает броню на {dmg} урона!"
        if extra_str > 0: log += f" (+Сила)"
        if row_mult < 1.0: log += " (Штраф дистанции)"
    
    if is_p1:
        match['p2_hp'] -= dmg
        update_pvp_match(match_id, p2_hp=match['p2_hp'], p1_ap=match['p1_ap'] - 2, log=log, last_action_time=time.time())
        if match['p2_hp'] <= 0: return await end_pvp_match(callback.bot, match_id, user['user_id'], match['p2_id'], log)
    else:
        match['p1_hp'] -= dmg
        update_pvp_match(match_id, p1_hp=match['p1_hp'], p2_ap=match['p2_ap'] - 2, log=log, last_action_time=time.time())
        if match['p1_hp'] <= 0: return await end_pvp_match(callback.bot, match_id, user['user_id'], match['p1_id'], log)

    await render_pvp(callback.bot, match_id)
    await callback.answer()

@router.callback_query(F.data == "pvp_potion")
async def pvp_potion_menu(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    match = get_pvp_match(user.get('combat_data', {}).get('pvp_match_id'))
    is_p1 = (user['user_id'] == match['p1_id'])
    
    if match['p1_ap' if is_p1 else 'p2_ap'] < 1:
        return await callback.answer("Недостаточно ОД!", show_alert=True)
        
    inv = user['inventory']
    potions = list(set(inv.get("potions", [])))
    if not potions: return await callback.answer("У вас нет зелий!", show_alert=True)

    buttons = []
    for i, p in enumerate(potions):
        buttons.append([InlineKeyboardButton(text=f"Выпить: {p} (x{inv['potions'].count(p)})", callback_data=f"pvp_drink_{i}")])
    buttons.append([InlineKeyboardButton(text="🔙 Отмена", callback_data="pvp_drink_cancel")])
    await callback.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@router.callback_query(F.data == "pvp_drink_cancel")
async def pvp_drink_cancel(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    match = get_pvp_match(user.get('combat_data', {}).get('pvp_match_id'))
    is_p1 = (user['user_id'] == match['p1_id'])
    state = json.loads(match.get('match_state', '{}'))
    await callback.message.edit_reply_markup(reply_markup=get_pvp_kb(True, match['p1_ap' if is_p1 else 'p2_ap'], state.get('distance', 'close')))

@router.callback_query(F.data.startswith("pvp_drink_"))
async def execute_drink_pvp(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    match_id = user.get('combat_data', {}).get('pvp_match_id')
    match = get_pvp_match(match_id)
    is_p1 = (user['user_id'] == match['p1_id'])
    
    inv = user['inventory']
    idx = int(callback.data.replace("pvp_drink_", ""))
    unique_potions = list(set(inv.get("potions", [])))
    
    if idx >= len(unique_potions): return await callback.answer("Ошибка зелья!")
    used_item = unique_potions[idx]
    inv["potions"].remove(used_item)
    update_user(user['user_id'], inventory=inv)
    
    state = json.loads(match.get('match_state', '{}'))
    my_buffs_key = 'p1' if is_p1 else 'p2'
    opp_buffs_key = 'p2' if is_p1 else 'p1'
    my_buffs = state.setdefault(my_buffs_key, {})
    opp_buffs = state.setdefault(opp_buffs_key, {})
    
    p_lower = used_item.lower()
    positive = ["хил", "реген", "рагу", "броня", "сила", "уклонение", "очищение", "защита"]
    is_thrown = not any(pos in p_lower for pos in positive)
    log = f"🧪 {user['username']} бросил [{used_item}]!" if is_thrown else f"🧪 {user['username']} выпил [{used_item}]!"
    
    dmg_to_opp = 0
    heal_to_me = 0
    ap_gain = -1 
    
    if "хил" in p_lower or "реген хп" in p_lower or "рагу" in p_lower: heal_to_me += int(user['max_hp'] * 0.25)
    if "броня" in p_lower: my_buffs['buff_armor'] = my_buffs.get('buff_armor', 0) + 15; my_buffs['buff_armor_t'] = 3
    if "сила" in p_lower and "тьмы" not in p_lower: my_buffs['buff_str'] = my_buffs.get('buff_str', 0) + 20; my_buffs['buff_str_t'] = 2
    if "уклонение" in p_lower: my_buffs['buff_dodge'] = 1; my_buffs['buff_dodge_t'] = 2
    if "очищение" in p_lower: 
        my_buffs['debuff_blind'] = 0; my_buffs['debuff_fragile'] = 0; my_buffs['debuff_vuln'] = 0; my_buffs['dot_burn'] = 0; my_buffs['dot_poison'] = 0; my_buffs['dot_bleed'] = 0
        
    if "урон огнем" in p_lower: dmg_to_opp += 30; opp_buffs['dot_burn'] = 3
    if "урон ядом" in p_lower: dmg_to_opp += 20; opp_buffs['dot_poison'] = 4
    if "кровотечение" in p_lower: opp_buffs['dot_bleed'] = 3
    if "урон льдом" in p_lower: dmg_to_opp += 25; state['distance'] = "far"
    if "оцепенение" in p_lower or "сон" in p_lower: opp_buffs['stun'] = 1
    
    if "хрупкость" in p_lower:
        if is_thrown: opp_buffs['debuff_vuln'] = 3
        else: my_buffs['debuff_fragile'] = 3
    if "слепота" in p_lower:
        if is_thrown: opp_buffs['debuff_blind'] = 2
        else: my_buffs['debuff_blind'] = 2
        
    if is_p1:
        match['p1_hp'] = min(match['p1_max'], match['p1_hp'] + heal_to_me)
        match['p2_hp'] -= dmg_to_opp
        match['p1_ap'] += ap_gain
        update_pvp_match(match_id, p1_hp=match['p1_hp'], p2_hp=match['p2_hp'], p1_ap=match['p1_ap'], match_state=json.dumps(state), log=log, last_action_time=time.time())
    else:
        match['p2_hp'] = min(match['p2_max'], match['p2_hp'] + heal_to_me)
        match['p1_hp'] -= dmg_to_opp
        match['p2_ap'] += ap_gain
        update_pvp_match(match_id, p1_hp=match['p1_hp'], p2_hp=match['p2_hp'], p2_ap=match['p2_ap'], match_state=json.dumps(state), log=log, last_action_time=time.time())

    if match['p2_hp'] <= 0: return await end_pvp_match(callback.bot, match_id, match['p1_id'], match['p2_id'], log)
    if match['p1_hp'] <= 0: return await end_pvp_match(callback.bot, match_id, match['p2_id'], match['p1_id'], log)

    await render_pvp(callback.bot, match_id)
    await callback.answer()

@router.callback_query(F.data == "pvp_end_turn")
async def pvp_end_turn(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    match_id = user.get('combat_data', {}).get('pvp_match_id')
    match = get_pvp_match(match_id)
    
    if not match or match['turn'] != user['user_id']: return await callback.answer()
        
    is_p1 = (user['user_id'] == match['p1_id'])
    next_turn = match['p2_id'] if is_p1 else match['p1_id']
    
    state = json.loads(match.get('match_state', '{}'))
    opp_key = 'p2' if is_p1 else 'p1'
    opp_buffs = state.setdefault(opp_key, {})
    
    dot_dmg = 0
    if opp_buffs.get('dot_burn', 0) > 0: dot_dmg += 15; opp_buffs['dot_burn'] -= 1
    if opp_buffs.get('dot_poison', 0) > 0: dot_dmg += 12; opp_buffs['dot_poison'] -= 1
    if opp_buffs.get('dot_bleed', 0) > 0: dot_dmg += 10; opp_buffs['dot_bleed'] -= 1
    
    log = f"⏳ {user['username']} завершил ход."
    if dot_dmg > 0:
        log += f"\n🩸 Противник получил {dot_dmg} урона от эффектов!"
        if is_p1: match['p2_hp'] -= dot_dmg
        else: match['p1_hp'] -= dot_dmg

    for buff_t in ['buff_armor_t', 'buff_str_t', 'buff_dodge_t', 'debuff_blind', 'debuff_fragile', 'debuff_vuln']:
        if opp_buffs.get(buff_t, 0) > 0:
            opp_buffs[buff_t] -= 1
            if opp_buffs[buff_t] == 0:
                attr = buff_t.replace('_t', '')
                opp_buffs[attr] = 0

    if match['p2_hp'] <= 0: return await end_pvp_match(callback.bot, match_id, match['p1_id'], match['p2_id'], log)
    if match['p1_hp'] <= 0: return await end_pvp_match(callback.bot, match_id, match['p2_id'], match['p1_id'], log)
    
    if is_p1: update_pvp_match(match_id, p1_ap=3, p2_hp=match['p2_hp'], turn=next_turn, match_state=json.dumps(state), log=log, last_action_time=time.time())
    else: update_pvp_match(match_id, p2_ap=3, p1_hp=match['p1_hp'], turn=next_turn, match_state=json.dumps(state), log=log, last_action_time=time.time())
        
    await render_pvp(callback.bot, match_id)
    await callback.answer()
    
    next_user = get_user(next_turn)
    if next_user.get('is_bot', 0) == 1:
        asyncio.create_task(process_bot_turn(callback.bot, match_id))

@router.callback_query(F.data == "pvp_surrender")
async def pvp_surrender(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    match_id = user.get('combat_data', {}).get('pvp_match_id')
    match = get_pvp_match(match_id)
    
    if not match: return await callback.answer()
        
    winner_id = match['p2_id'] if user['user_id'] == match['p1_id'] else match['p1_id']
    await end_pvp_match(callback.bot, match_id, winner_id, user['user_id'], f"🏳️ {user['username']} позорно бежал с поля боя!")

