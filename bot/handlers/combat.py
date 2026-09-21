import random
import datetime
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database import get_user, update_user, get_item, get_loot_table, get_item_name, get_setting, apply_flee_penalty, apply_death_penalty, add_quest_progress, get_clan, update_clan

router = Router()

def get_combat_kb(ap: int, distance: str):
    buttons = []
    buttons.append([InlineKeyboardButton(text="🗡️ Атака (2 ОД)" if ap >= 2 else "❌ Атака (2 ОД)", callback_data="combat_act_attack")])
    move_text = "🏃 Отступить (1 ОД)" if distance == "close" else "⚔️ Сблизиться (1 ОД)"
    buttons.append([InlineKeyboardButton(text=move_text if ap >= 1 else "❌ Смена позиции (1 ОД)", callback_data="combat_act_move")])
    buttons.append([InlineKeyboardButton(text="🧪 Зелье (1 ОД)", callback_data="combat_act_potion"), InlineKeyboardButton(text="⏳ Конец хода", callback_data="combat_act_end_turn")])
    buttons.append([InlineKeyboardButton(text="💨 Сбежать", callback_data="combat_act_flee")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

@router.callback_query(F.data.startswith("coop_join_"))
async def join_coop(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    host_id = int(callback.data.replace("coop_join_", ""))
    host_user = get_user(host_id)
    if not host_user or host_user['state'] != 'STATE_COMBAT': return await callback.answer("Игрок уже закончил бой!", show_alert=True)
    combat_data = host_user['combat_data'].copy()
    combat_data['coop_host'] = host_id
    combat_data['ap'] = 3
    update_user(user['user_id'], state='STATE_COMBAT', combat_data=combat_data)
    await render_combat(callback, user, combat_data, f"🔥 Вы ворвались на помощь к {host_user['username']}!")

@router.callback_query(F.data == "combat_act_attack")
async def combat_attack(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    combat = user.get('combat_data', {})
    
    if combat.get('ap', 0) < 2: return await callback.answer("Недостаточно ОД!", show_alert=True)
    combat['ap'] -= 2
    
    if 'coop_host' in combat:
        host = get_user(combat['coop_host'])
        if host['state'] != 'STATE_COMBAT':
            update_user(user['user_id'], state='STATE_TOWN', combat_data={})
            from handlers.town import get_town_kb
            return await callback.message.edit_text("Монстр уже мертв. Возврат в город.", reply_markup=get_town_kb())
        enemy_hp = host['combat_data'].get('enemy_hp', 50)
    else:
        enemy_hp = combat.get('enemy_hp', 50)
    
    inv = user['inventory']
    weapon_id = inv.get("equipment", {}).get("weapon")
    weapon_data = get_item(weapon_id) if weapon_id else None
    
    base_dmg = int(get_setting("base_unarmed_dmg", "5")) + (user.get('level', 1) * 2) + random.randint(0, 3)
    w_dmg = weapon_data['stats'].get('dmg', 0) if weapon_data else 0
    w_range = weapon_data['stats'].get('range', 'melee') if weapon_data else 'melee'
    
    distance = combat.get('distance', 'close')
    if w_range == "melee": row_mult = 1.0 if distance == "close" else 0.3
    else: row_mult = 1.0 if distance == "far" else 0.5
        
    dmg = int((base_dmg + w_dmg) * row_mult)
    mob_skills = combat.get('mob_skills', {})
    log_msg = ""
    enemy_name = combat.get('enemy_name', 'Враг')
    
    if random.random() < mob_skills.get("dodge", 0): log_msg = f"💨 {enemy_name} увернулся от атаки!"
    else:
        enemy_hp -= dmg
        log_msg = f"Вы нанесли {dmg} урона!"
        if row_mult < 1.0: log_msg += " (Штраф за дистанцию)"
        
        if enemy_hp > 0 and random.random() < mob_skills.get("counter", 0):
            counter_dmg = int(dmg * 0.5)
            user['hp'] -= counter_dmg
            log_msg += f"\n⚔️ Враг контратакует! (-{counter_dmg} ХП)"
            if user['hp'] <= 0:
                apply_death_penalty(user['user_id'], user.get('dungeon_data', {}))
                update_user(user['user_id'], state='STATE_TOWN', combat_data={}, dungeon_data={})
                from handlers.town import get_town_kb
                return await callback.message.edit_text("☠️ **Вы убиты!** Все собранные вещи утеряны.", reply_markup=get_town_kb(), parse_mode="Markdown")
    
    if 'coop_host' in combat:
        host = get_user(combat['coop_host'])
        host['combat_data']['enemy_hp'] = enemy_hp
        update_user(host['user_id'], combat_data=host['combat_data'])
    combat['enemy_hp'] = enemy_hp
    
    if enemy_hp <= 0:
        add_quest_progress(user['user_id'], "kill_mobs", 1)
        dungeon_data = user.get('dungeon_data', {})
        location_id = f"event_{datetime.datetime.today().weekday()}" if dungeon_data.get('dungeon_type', 'solo') == "event" else "solo"
        
        mod = combat.get('mob_modifier', 1.0)
        reward_gold = int(random.randint(combat.get('gold_min', 5), combat.get('gold_max', 15)) * mod)
        gained_xp = int(combat.get('xp_reward', 10) * mod)
        
        user['gold'] += reward_gold
        dungeon_data.setdefault('gathered_gold', 0)
        dungeon_data['gathered_gold'] += reward_gold
        
        user['xp'] = user.get('xp', 0) + gained_xp
        lvl_msg = f"✨ Получено {gained_xp} XP."
        
        while user['xp'] >= user.get('level', 1) * 100:
            user['xp'] -= user['level'] * 100
            user['level'] += 1
            user['max_hp'] += 15
            user['hp'] = user['max_hp']
            lvl_msg += f"\n🎉 **НОВЫЙ УРОВЕНЬ! ({user['level']})**"

        drop_msg = f"{lvl_msg}\n💰 Найдено {reward_gold} золота."
        
        for loot in get_loot_table(location_id):
            if random.random() <= loot['chance']:
                qty = random.randint(loot['min'], loot['max'])
                item_db = get_item(loot['item_id'])
                if item_db and item_db['type'] in ["weapon", "armor"]:
                    for _ in range(qty): 
                        inv.setdefault("backpack", []).append(loot['item_id'])
                        dungeon_data.setdefault("gathered_equipment", []).append(loot['item_id'])
                else:
                    inv.setdefault("materials", {})[loot['item_id']] = inv.setdefault("materials", {}).get(loot['item_id'], 0) + qty
                    dungeon_data.setdefault("gathered_materials", {})
                    dungeon_data["gathered_materials"][loot['item_id']] = dungeon_data["gathered_materials"].get(loot['item_id'], 0) + qty
                drop_msg += f"\n✨ Выбито: **{get_item_name(loot['item_id'])}** (x{qty})"
        
        update_user(user['user_id'], state='STATE_DUNGEON', gold=user['gold'], hp=user['hp'], max_hp=user['max_hp'], level=user['level'], xp=user['xp'], inventory=inv, combat_data={}, dungeon_data=dungeon_data)
        
        if not dungeon_data.get("nodes", {}).get(dungeon_data.get("current_node"), {}).get("next"):
            add_quest_progress(user['user_id'], "raid_success", 1)
            if user['clan_id'] != 0:
                clan = get_clan(user['clan_id'])
                if clan: update_clan(clan['clan_id'], weekly_raids=clan['weekly_raids'] + 1)
                
            from handlers.town import get_town_kb
            update_user(user['user_id'], state='STATE_TOWN', dungeon_data={})
            if 'coop_host' in combat: return await callback.message.edit_text(f"🏆 **Монстр повержен в Co-op!**\n{drop_msg}", reply_markup=get_town_kb(), parse_mode="Markdown")
            return await callback.message.edit_text(f"🏆 **Рейд завершен!**\n{drop_msg}", reply_markup=get_town_kb(), parse_mode="Markdown")
        else:
            from handlers.dungeon import get_navigation_kb
            if 'coop_host' in combat:
                from handlers.town import get_town_kb
                return await callback.message.edit_text(f"🎉 **Монстр повержен!** Вы помогли хосту.\n{drop_msg}", reply_markup=get_town_kb(), parse_mode="Markdown")
            return await callback.message.edit_text(f"🎉 **Победа!**\n{drop_msg}\n\nКуда дальше?", reply_markup=get_navigation_kb(dungeon_data), parse_mode="Markdown")
        
    update_user(user['user_id'], hp=user['hp'], combat_data=combat)
    await render_combat(callback, user, combat, log_msg)

@router.callback_query(F.data == "combat_act_move")
async def combat_move(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    combat = user.get('combat_data', {})
    if combat.get('ap', 0) < 1: return await callback.answer("Недостаточно ОД!", show_alert=True)
    combat['ap'] -= 1
    if combat.get('distance', 'close') == "close":
        combat['distance'] = "far"
        log_msg = "🏃 Вы разорвали дистанцию! Теперь вы далеко."
    else:
        combat['distance'] = "close"
        log_msg = "⚔️ Вы бросились вперед! Ближний бой."
    update_user(user['user_id'], combat_data=combat)
    await render_combat(callback, user, combat, log_msg)

@router.callback_query(F.data == "combat_act_end_turn")
async def combat_end_turn(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    combat = user.get('combat_data', {})
    
    if 'coop_host' in combat:
        host = get_user(combat['coop_host'])
        if host['state'] != 'STATE_COMBAT':
            update_user(user['user_id'], state='STATE_TOWN', combat_data={})
            from handlers.town import get_town_kb
            return await callback.message.edit_text("Монстр мертв. Возврат в город.", reply_markup=get_town_kb())
        combat['enemy_hp'] = host['combat_data'].get('enemy_hp', 50)
    
    armor_id = user['inventory'].get("equipment", {}).get("armor")
    armor_def = get_item(armor_id)['stats'].get('def', 0) if armor_id else 0
    mob_skills = combat.get('mob_skills', {})
    log_msg = ""
    
    mob_pref_dist = "close" if combat.get('mob_pref', 'front') == "front" else "far"
    if combat.get('distance', 'close') != mob_pref_dist and random.random() < mob_skills.get('reposition', 0):
        combat['distance'] = mob_pref_dist
        action = "сокращает" if mob_pref_dist == "close" else "разрывает"
        log_msg += f"🏃 Враг {action} дистанцию!\n"
    
    dmg_min = combat.get('dmg_min', 10)
    dmg_max = combat.get('dmg_max', 15)
    raw_dmg = random.randint(dmg_min, dmg_max)
    
    if combat.get('distance', 'close') != mob_pref_dist: raw_dmg = int(raw_dmg * 0.5) 
        
    monster_dmg = max(1, raw_dmg - armor_def)
    user['hp'] -= monster_dmg
    log_msg += f"Враг бьет на {monster_dmg} урона."
    
    if random.random() < mob_skills.get('poison', 0):
        user['hp'] -= 10
        log_msg += "\n🟢 Отравление! (-10 ХП)"
    
    if user['hp'] <= 0:
        apply_death_penalty(user['user_id'], user.get('dungeon_data', {}))
        update_user(user['user_id'], state='STATE_TOWN', combat_data={}, dungeon_data={})
        from handlers.town import get_town_kb
        return await callback.message.edit_text("☠️ **Вы убиты!** Все собранные вещи утеряны.", reply_markup=get_town_kb(), parse_mode="Markdown")
            
    combat['ap'] = 3
    update_user(user['user_id'], hp=user['hp'], combat_data=combat)
    await render_combat(callback, user, combat, log_msg)

@router.callback_query(F.data == "combat_act_potion")
async def combat_use_potion(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    combat = user.get('combat_data', {})
    inv = user['inventory']
    if combat.get('ap', 0) < 1: return await callback.answer("Недостаточно ОД!", show_alert=True)
    potions = inv.get("potions", [])
    if not potions: return await callback.answer("У вас нет зелий!", show_alert=True)
        
    used_item = potions.pop(0)
    combat['ap'] -= 1
    p_lower = used_item.lower()
    log_msg = f"Выпито [{used_item}].\n"
    
    if "рагу" in p_lower:
        heal = int(user['max_hp'] * 0.35); user['hp'] = min(user['max_hp'], user['hp'] + heal); log_msg += f"💚 +{heal} ХП\n"
    if "хил" in p_lower or "реген хп" in p_lower:
        heal = int(user['max_hp'] * 0.25); user['hp'] = min(user['max_hp'], user['hp'] + heal); log_msg += f"💚 +{heal} ХП\n"
    if "урон огнем" in p_lower or "урон ядом" in p_lower or "сила тьмы" in p_lower or "урон льдом" in p_lower:
        dmg = 30 + user.get('level', 1) * 5
        combat['enemy_hp'] = combat.get('enemy_hp', 50) - dmg
        log_msg += f"🔥 Враг получил {dmg} маг. урона!\n"
    if "реген од" in p_lower or "ускорение" in p_lower:
        combat['ap'] += 2; log_msg += "⚡ +2 ОД\n"
    if "вампиризм" in p_lower:
        v_dmg = 20
        combat['enemy_hp'] = combat.get('enemy_hp', 50) - v_dmg
        user['hp'] = min(user['max_hp'], user['hp'] + v_dmg)
        log_msg += f"🩸 Иссушение врага на {v_dmg} ХП!\n"
    if "богатство" in p_lower or "удача" in p_lower:
        gold_b = random.randint(30, 80)
        user['gold'] += gold_b
        dungeon_data = user.get('dungeon_data', {})
        dungeon_data.setdefault('gathered_gold', 0)
        dungeon_data['gathered_gold'] += gold_b
        update_user(user['user_id'], dungeon_data=dungeon_data)
        log_msg += f"💰 Свинец стал золотом! (+{gold_b} 🪙)\n"
        
    if "слабость" in p_lower or "ожог" in p_lower or "хрупкость" in p_lower or "болезнь" in p_lower:
        self_dmg = 15; user['hp'] -= self_dmg; log_msg += f"🤢 Побочный эффект! (-{self_dmg} ХП)\n"
        
    if combat.get('enemy_hp', 50) <= 0:
        combat['enemy_hp'] = 1
        log_msg += " Враг еле стоит на ногах!"
        
    update_user(user['user_id'], hp=user['hp'], inventory=inv, combat_data=combat)
    await render_combat(callback, user, combat, log_msg)

async def render_combat(callback: CallbackQuery, user: dict, combat: dict, log_msg: str):
    dist_str = "УПОР (Ближний бой)" if combat.get('distance', 'close') == "close" else "ИЗДАЛЕКА (Дальний бой)"
    ap_icons = "🟢 " * combat.get('ap', 3) + "⚪ " * (3 - combat.get('ap', 3))
    enemy_name = combat.get('enemy_name', 'Враг')
    enemy_hp = combat.get('enemy_hp', 50)
    enemy_max = combat.get('enemy_max_hp', 50)
    
    text = (f"⚔️ **Бой: {enemy_name}**\n❤️ Враг: {enemy_hp}/{enemy_max} HP\n━━━━━━━━━━━━━━\n"
            f"👤 Вы: {user['hp']}/{user['max_hp']} HP\n📏 Дистанция: **{dist_str}**\n⚡ ОД: {ap_icons}\n\n💬 *{log_msg}*")
    await callback.message.edit_text(text, reply_markup=get_combat_kb(combat.get('ap', 3), combat.get('distance', 'close')), parse_mode="Markdown")

# НОВАЯ СИСТЕМА ПОДТВЕРЖДЕНИЯ ПОБЕГА
@router.callback_query(F.data == "combat_act_flee")
async def combat_flee(callback: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏃‍♂️ ДА, СБЕЖАТЬ", callback_data="combat_act_flee_confirm")],
        [InlineKeyboardButton(text="⚔️ НЕТ, В БОЙ!", callback_data="combat_act_flee_cancel")]
    ])
    await callback.message.edit_text("⚠️ **Вы уверены?**\nПри побеге вы потеряете часть золота и лута из этого рейда!", reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data == "combat_act_flee_confirm")
async def combat_flee_confirm(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    lost_gold, lost_mats = apply_flee_penalty(user['user_id'], user.get('dungeon_data', {}))
    update_user(user['user_id'], state='STATE_TOWN', combat_data={}, dungeon_data={})
    from handlers.town import get_town_kb
    mats_str = f" и {', '.join(lost_mats)}" if lost_mats else ""
    await callback.message.edit_text(f"🏃‍♂️ Вы сбежали! Потеряно из рейда: **{lost_gold} золота**{mats_str}.", reply_markup=get_town_kb(), parse_mode="Markdown")

@router.callback_query(F.data == "combat_act_flee_cancel")
async def combat_flee_cancel(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    combat = user.get('combat_data', {})
    await render_combat(callback, user, combat, "Вы решили остаться и драться!")
