import random
import datetime
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database import (
    get_user, update_user, get_item, get_loot_table, get_item_name, get_setting,
    apply_flee_penalty, apply_death_penalty, add_quest_progress, get_clan, update_clan,
    calculate_damage_received
)

router = Router()

def get_combat_kb(ap: int, distance: str):
    buttons = [
        [InlineKeyboardButton(text="🗡️ Атака (2 ОД)" if ap >= 2 else "❌ Атака (2 ОД)", callback_data="combat_act_attack")],
        [InlineKeyboardButton(text="🏃 Отступить (1 ОД)" if distance == "close" else "⚔️ Сблизиться (1 ОД)" if ap >= 1 else "❌ Смена позиции (1 ОД)", callback_data="combat_act_move")],
        [InlineKeyboardButton(text="🧪 Инвентарь (1 ОД)", callback_data="combat_act_potion"), InlineKeyboardButton(text="⏳ Конец хода", callback_data="combat_act_end_turn")],
        [InlineKeyboardButton(text="💨 Сбежать", callback_data="combat_act_flee")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def render_effects_badge(combat: dict) -> str:
    badges = []
    # Баффы и дебаффы игрока
    if combat.get('buff_armor', 0) > 0:
        badges.append(f"🛡️ Броня +{combat['buff_armor']} ({combat.get('buff_armor_t', 1)}х)")
    if combat.get('buff_str', 0) > 0:
        badges.append(f"⚔️ Сила +{combat['buff_str']} ({combat.get('buff_str_t', 1)}х)")
    if combat.get('buff_dodge', 0) > 0:
        badges.append(f"💨 Уворот +{int(combat['buff_dodge']*100)}% ({combat.get('buff_dodge_t', 1)}х)")
    if combat.get('debuff_blind', 0) > 0:
        badges.append(f"👁️ Слепота ({combat['debuff_blind']}х)")
    if combat.get('debuff_fragile', 0) > 0:
        badges.append(f"💔 Хрупкость ({combat['debuff_fragile']}х)")
    if combat.get('debuff_vuln', 0) > 0:
        badges.append(f"🎯 Уязвимость +25% ({combat['debuff_vuln']}х)")

    # Дебаффы на враге
    if combat.get('dot_burn', 0) > 0:
        badges.append(f"🔥 Горение ({combat['dot_burn']}х)")
    if combat.get('dot_poison', 0) > 0:
        badges.append(f"🟢 Отравление ({combat['dot_poison']}х)")
    if combat.get('dot_bleed', 0) > 0:
        badges.append(f"🩸 Кровотечение ({combat['dot_bleed']}х)")
    if combat.get('enemy_stun', 0) > 0:
        badges.append(f"💫 Враг оглушен ({combat['enemy_stun']}х)")

    return " | ".join(badges) if badges else "Нет"

async def render_combat(callback: CallbackQuery, user: dict, combat: dict, log_msg: str):
    dist_str = "УПОР (Ближний бой)" if combat.get('distance', 'close') == "close" else "ИЗДАЛЕКА (Дальний бой)"
    ap_icons = "🟢 " * combat.get('ap', 3) + "⚪ " * (3 - combat.get('ap', 3))
    enemy_name = combat.get('enemy_name', 'Враг')
    enemy_hp = combat.get('enemy_hp', 50)
    enemy_max = combat.get('enemy_max_hp', 50)
    effects_text = render_effects_badge(combat)

    text = (f"⚔️ **Бой: {enemy_name}**\n❤️ Враг: {enemy_hp}/{enemy_max} HP\n━━━━━━━━━━━━━━\n"
            f"👤 Вы: {user['hp']}/{user['max_hp']} HP\n📏 Дистанция: **{dist_str}**\n⚡ ОД: {ap_icons}\n"
            f"✨ **Эффекты:** {effects_text}\n\n💬 *{log_msg}*")
    await callback.message.edit_text(text, reply_markup=get_combat_kb(combat.get('ap', 3), combat.get('distance', 'close')), parse_mode="Markdown")

async def handle_combat_victory(callback: CallbackQuery, user_id: int, combat: dict):
    fresh_user = get_user(user_id)
    inv = fresh_user['inventory']
    dungeon_data = fresh_user.get('dungeon_data', {})
    location_id = f"event_{datetime.datetime.today().weekday()}" if dungeon_data.get('dungeon_type', 'solo') == "event" else "solo"
    is_boss = not dungeon_data.get("nodes", {}).get(dungeon_data.get("current_node"), {}).get("next")

    # Сохранение статистики в home_data
    home = fresh_user.get('home_data', {})
    home['mobs_killed'] = home.get('mobs_killed', 0) + 1
    if is_boss:
        home['bosses_killed'] = home.get('bosses_killed', 0) + 1

    add_quest_progress(user_id, "kill_mobs", 1)

    mod = combat.get('mob_modifier', 1.0)
    reward_gold = int(random.randint(combat.get('gold_min', 5), combat.get('gold_max', 15)) * mod)
    gained_xp = int(combat.get('xp_reward', 10) * mod)

    fresh_user['gold'] += reward_gold
    dungeon_data.setdefault('gathered_gold', 0)
    dungeon_data['gathered_gold'] += reward_gold

    fresh_user['xp'] = fresh_user.get('xp', 0) + gained_xp
    lvl_msg = f"✨ Получено {gained_xp} XP."

    while fresh_user['xp'] >= fresh_user.get('level', 1) * 100:
        fresh_user['xp'] -= fresh_user['level'] * 100
        fresh_user['level'] += 1
        fresh_user['max_hp'] += 15
        fresh_user['hp'] = fresh_user['max_hp']
        lvl_msg += f"\n🎉 **НОВЫЙ УРОВЕНЬ! ({fresh_user['level']})**"

    drop_msg = f"{lvl_msg}\n💰 Найдено {reward_gold} золота."

    loot_table = get_loot_table(location_id)
    random.shuffle(loot_table)
    max_drops = random.randint(5, 8) if is_boss else random.randint(1, 2)
    dropped_count = 0

    for loot in loot_table:
        if dropped_count >= max_drops:
            break
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
            dropped_count += 1

    update_user(
        user_id,
        state='STATE_DUNGEON',
        gold=fresh_user['gold'],
        hp=fresh_user['hp'],
        max_hp=fresh_user['max_hp'],
        level=fresh_user['level'],
        xp=fresh_user['xp'],
        inventory=inv,
        combat_data={},
        dungeon_data=dungeon_data,
        home_data=home
    )

    if is_boss:
        add_quest_progress(user_id, "raid_success", 1)
        if fresh_user['clan_id'] != 0:
            clan = get_clan(fresh_user['clan_id'])
            if clan:
                update_clan(clan['clan_id'], weekly_raids=clan['weekly_raids'] + 1)

        from handlers.town import get_town_kb
        update_user(user_id, state='STATE_TOWN', dungeon_data={})
        if 'coop_host' in combat:
            return await callback.message.edit_text(f"🏆 **Монстр повержен в Co-op!**\n{drop_msg}", reply_markup=get_town_kb(), parse_mode="Markdown")
        return await callback.message.edit_text(f"🏆 **Рейд завершен!**\n{drop_msg}", reply_markup=get_town_kb(), parse_mode="Markdown")
    else:
        from handlers.dungeon import get_navigation_kb
        if 'coop_host' in combat:
            from handlers.town import get_town_kb
            return await callback.message.edit_text(f"🎉 **Монстр повержен!** Вы помогли хосту.\n{drop_msg}", reply_markup=get_town_kb(), parse_mode="Markdown")
        return await callback.message.edit_text(f"🎉 **Победа!**\n{drop_msg}\n\nКуда дальше?", reply_markup=get_navigation_kb(dungeon_data), parse_mode="Markdown")

@router.callback_query(F.data.startswith("coop_join_"))
async def join_coop(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    host_id = int(callback.data.replace("coop_join_", ""))
    host_user = get_user(host_id)
    if not host_user or host_user['state'] != 'STATE_COMBAT':
        return await callback.answer("Игрок уже закончил бой!", show_alert=True)
    combat_data = host_user['combat_data'].copy()
    combat_data['coop_host'] = host_id
    combat_data['ap'] = 3
    update_user(user['user_id'], state='STATE_COMBAT', combat_data=combat_data)
    await render_combat(callback, user, combat_data, f"🔥 Вы ворвались на помощь к {host_user['username']}!")

@router.callback_query(F.data == "combat_act_attack")
async def combat_attack(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    combat = user.get('combat_data', {})

    if combat.get('ap', 0) < 2:
        return await callback.answer("Недостаточно ОД!", show_alert=True)
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

    # Учет слепоты (шанс промаха 40%)
    if combat.get('debuff_blind', 0) > 0 and random.random() < 0.4:
        log_msg = "👁️ Вы ослеплены и промахнулись!"
    else:
        inv = user['inventory']
        weapon_id = inv.get("equipment", {}).get("weapon")
        weapon_data = get_item(weapon_id) if weapon_id else None

        base_dmg = int(get_setting("base_unarmed_dmg", "5")) + (user.get('level', 1) * 2) + random.randint(0, 3)
        w_dmg = weapon_data['stats'].get('dmg', 0) if weapon_data else 0
        w_range = weapon_data['stats'].get('range', 'melee') if weapon_data else 'melee'

        distance = combat.get('distance', 'close')
        row_mult = (1.0 if distance == "close" else 0.3) if w_range == "melee" else (1.0 if distance == "far" else 0.5)

        extra_str = combat.get('buff_str', 0)
        dmg = int((base_dmg + w_dmg + extra_str) * row_mult)

        mob_skills = combat.get('mob_skills', {})
        enemy_name = combat.get('enemy_name', 'Враг')

        if random.random() < mob_skills.get("dodge", 0):
            log_msg = f"💨 {enemy_name} увернулся от атаки!"
        else:
            enemy_hp -= dmg
            log_msg = f"Вы нанесли {dmg} урона!"
            if extra_str > 0:
                log_msg += f" (Сила +{extra_str})"
            if row_mult < 1.0:
                log_msg += " (Штраф за дистанцию)"

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
        return await handle_combat_victory(callback, user['user_id'], combat)

    update_user(user['user_id'], hp=user['hp'], combat_data=combat)
    await render_combat(callback, user, combat, log_msg)

@router.callback_query(F.data == "combat_act_move")
async def combat_move(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    combat = user.get('combat_data', {})
    if combat.get('ap', 0) < 1:
        return await callback.answer("Недостаточно ОД!", show_alert=True)
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

    log_parts = []

    # 1. ТИКИ ДОТОВ ПО ВРАГУ
    dot_dmg = 0
    if combat.get('dot_burn', 0) > 0:
        dot_dmg += 15
        combat['dot_burn'] -= 1
        log_parts.append("🔥 Ожог нанес врагу 15 урона")
    if combat.get('dot_poison', 0) > 0:
        dot_dmg += 12
        combat['dot_poison'] -= 1
        log_parts.append("🟢 Яд отравил врага на 12 урона")
    if combat.get('dot_bleed', 0) > 0:
        dot_dmg += 10
        combat['dot_bleed'] -= 1
        log_parts.append("🩸 Кровотечение сняло врагу 10 урона")

    if dot_dmg > 0:
        combat['enemy_hp'] -= dot_dmg
        if combat['enemy_hp'] <= 0:
            if 'coop_host' in combat:
                host = get_user(combat['coop_host'])
                host['combat_data']['enemy_hp'] = combat['enemy_hp']
                update_user(host['user_id'], combat_data=host['combat_data'])
            return await handle_combat_victory(callback, user['user_id'], combat)

    # 2. АТАКА МОНСТРА
    if combat.get('enemy_stun', 0) > 0:
        combat['enemy_stun'] -= 1
        log_parts.append("💫 Враг оглушен/спит и пропускает атаку!")
    else:
        dodge_chance = 0.05 + combat.get('buff_dodge', 0.0)
        if random.random() < dodge_chance:
            log_parts.append("💨 Вы ловко увернулись от удара монстра!")
        else:
            armor_id = user['inventory'].get("equipment", {}).get("armor")
            base_armor = get_item(armor_id)['stats'].get('def', 0) if armor_id else 0
            
            if combat.get('debuff_fragile', 0) > 0:
                base_armor = int(base_armor * 0.5)

            total_armor = base_armor + combat.get('buff_armor', 0)
            mob_skills = combat.get('mob_skills', {})

            mob_pref_dist = "close" if combat.get('mob_pref', 'front') == "front" else "far"
            if combat.get('distance', 'close') != mob_pref_dist and random.random() < mob_skills.get('reposition', 0):
                combat['distance'] = mob_pref_dist
                action = "сокращает" if mob_pref_dist == "close" else "разрывает"
                log_parts.append(f"🏃 Враг {action} дистанцию!")

            dmg_min = combat.get('dmg_min', 10)
            dmg_max = combat.get('dmg_max', 15)
            raw_dmg = random.randint(dmg_min, dmg_max)
            if combat.get('distance', 'close') != mob_pref_dist:
                raw_dmg = int(raw_dmg * 0.5)

            if combat.get('debuff_vuln', 0) > 0:
                raw_dmg = int(raw_dmg * 1.25)

            # ПРИМЕНЕНИЕ ФОРМУЛЫ БРОНИ С КАПОМ 75%
            monster_dmg = calculate_damage_received(raw_dmg, total_armor)
            user['hp'] -= monster_dmg
            log_parts.append(f"Враг ударил на {monster_dmg} урона.")

            if random.random() < mob_skills.get('poison', 0):
                user['hp'] -= 10
                log_parts.append("🟢 Отравление! (-10 ХП)")

    # 3. ТИКИ БАФФОВ И ДЕБАФФОВ ГЕРОЯ
    for buff_t in ['buff_armor_t', 'buff_str_t', 'buff_dodge_t', 'debuff_blind', 'debuff_fragile', 'debuff_vuln']:
        if combat.get(buff_t, 0) > 0:
            combat[buff_t] -= 1
            if combat[buff_t] == 0:
                attr = buff_t.replace('_t', '')
                combat[attr] = 0

    if user['hp'] <= 0:
        apply_death_penalty(user['user_id'], user.get('dungeon_data', {}))
        update_user(user['user_id'], state='STATE_TOWN', combat_data={}, dungeon_data={})
        from handlers.town import get_town_kb
        return await callback.message.edit_text("☠️ **Вы убиты!** Все собранные вещи утеряны.", reply_markup=get_town_kb(), parse_mode="Markdown")

    combat['ap'] = 3
    if 'coop_host' in combat:
        host = get_user(combat['coop_host'])
        host['combat_data']['enemy_hp'] = combat['enemy_hp']
        update_user(host['user_id'], combat_data=host['combat_data'])

    update_user(user['user_id'], hp=user['hp'], combat_data=combat)
    await render_combat(callback, user, combat, "\n".join(log_parts))

@router.callback_query(F.data == "combat_act_potion")
async def combat_use_potion_menu(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    combat = user.get('combat_data', {})
    inv = user['inventory']
    if combat.get('ap', 0) < 1:
        return await callback.answer("Недостаточно ОД!", show_alert=True)
    potions = list(set(inv.get("potions", [])))
    if not potions:
        return await callback.answer("У вас нет зелий!", show_alert=True)

    buttons = []
    for i, p in enumerate(potions):
        count = inv["potions"].count(p)
        buttons.append([InlineKeyboardButton(text=f"Использовать: {p} (x{count})", callback_data=f"c_drink_{i}")])
    buttons.append([InlineKeyboardButton(text="🔙 Отмена", callback_data="c_drink_cancel")])
    await callback.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@router.callback_query(F.data == "c_drink_cancel")
async def combat_drink_cancel(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    combat = user.get('combat_data', {})
    await callback.message.edit_reply_markup(reply_markup=get_combat_kb(combat.get('ap', 3), combat.get('distance', 'close')))

@router.callback_query(F.data.startswith("c_drink_"))
async def execute_drink_combat(callback: CallbackQuery):
    if callback.data == "c_drink_cancel":
        return
    user = get_user(callback.from_user.id)
    combat = user.get('combat_data', {})
    inv = user['inventory']
    if combat.get('ap', 0) < 1:
        return await callback.answer("Недостаточно ОД!", show_alert=True)

    idx = int(callback.data.replace("c_drink_", ""))
    unique_potions = list(set(inv.get("potions", [])))
    if idx >= len(unique_potions):
        return await callback.answer("Ошибка выбора зелья!", show_alert=True)

    used_item = unique_potions[idx]
    inv["potions"].remove(used_item)
    combat['ap'] -= 1

    if 'coop_host' in combat:
        host = get_user(combat['coop_host'])
        if host['state'] != 'STATE_COMBAT':
            update_user(user['user_id'], state='STATE_TOWN', combat_data={})
            from handlers.town import get_town_kb
            return await callback.message.edit_text("Монстр уже мертв. Возврат в город.", reply_markup=get_town_kb())
        combat['enemy_hp'] = host['combat_data'].get('enemy_hp', 50)

    p_lower = used_item.lower()
    log_msg = f"Использовано [{used_item}]:\n"

    mob_skills = combat.get('mob_skills', {})
    immunes = mob_skills.get('immune', [])
    weaks = mob_skills.get('weak', [])
    resists = mob_skills.get('resist', [])
    enemy_name = combat.get('enemy_name', 'Враг')

    def calc_element_dmg(base_val: int, elem: str) -> tuple[int, str]:
        if elem in immunes:
            return 0, f"🚫 {enemy_name} невосприимчив к [{elem}]! (Иммунитет)\n"
        multiplier = 1.0
        note = ""
        if elem in weaks:
            multiplier = 1.5
            note = " 💥 Уязвимость (+50% урона)!"
        elif elem in resists:
            multiplier = 0.5
            note = " 🛡️ Сопротивление (-50% урона)."
        return int(base_val * multiplier), note

    # 1. Восстановление и баффы героя
    if "рагу" in p_lower:
        heal = int(user['max_hp'] * 0.35)
        user['hp'] = min(user['max_hp'], user['hp'] + heal)
        log_msg += f"💚 +{heal} ХП\n"
    if "хил" in p_lower or "реген хп" in p_lower:
        heal = int(user['max_hp'] * 0.25)
        user['hp'] = min(user['max_hp'], user['hp'] + heal)
        log_msg += f"💚 +{heal} ХП\n"
    if "реген од" in p_lower or "ускорение" in p_lower or "бодрость" in p_lower:
        combat['ap'] += 2
        log_msg += "⚡ +2 ОД\n"
    if "броня" in p_lower or "сопротивление" in p_lower or "тяжесть" in p_lower:
        combat['buff_armor'] = combat.get('buff_armor', 0) + 15
        combat['buff_armor_t'] = 3
        log_msg += "🛡️ Броня увеличена на +15 на 3 хода\n"
    if "сила" in p_lower:
        combat['buff_str'] = combat.get('buff_str', 0) + 20
        combat['buff_str_t'] = 2
        log_msg += "⚔️ Сила атаки увеличена на +20 на 2 хода\n"
    if "уклонение" in p_lower or "ловкость" in p_lower or "полет" in p_lower:
        combat['buff_dodge'] = 0.35
        combat['buff_dodge_t'] = 2
        log_msg += "💨 Шанс уворота +35% на 2 хода\n"
    if "очищение" in p_lower or "мана" in p_lower:
        combat['debuff_blind'] = 0
        combat['debuff_fragile'] = 0
        combat['debuff_vuln'] = 0
        log_msg += "✨ Очищение: все негативные эффекты сняты!\n"

    # 2. Боевые стихии с учетом РЕЗИСТОВ и ИММУНИТЕТОВ
    if "урон огнем" in p_lower:
        dmg, note = calc_element_dmg(30 + user.get('level', 1) * 5, "fire")
        if dmg > 0:
            combat['enemy_hp'] -= dmg
            combat['dot_burn'] = 3
            log_msg += f"🔥 Огненный взрыв: {dmg} урона + поджог на 3 хода!{note}\n"
        else:
            log_msg += note

    if "урон ядом" in p_lower:
        dmg, note = calc_element_dmg(20 + user.get('level', 1) * 4, "poison")
        if dmg > 0:
            combat['enemy_hp'] -= dmg
            combat['dot_poison'] = 4
            log_msg += f"🟢 Отравление: {dmg} урона + яд на 4 хода!{note}\n"
        else:
            log_msg += note

    if "кровотечение" in p_lower:
        if "bleed" in immunes:
            log_msg += f"🚫 У {enemy_name} нет крови! Иммунитет к кровотечению.\n"
        else:
            combat['dot_bleed'] = 3
            log_msg += "🩸 Наложено кровотечение на 3 хода!\n"

    if "урон льдом" in p_lower or "замедление" in p_lower:
        dmg, note = calc_element_dmg(25 + user.get('level', 1) * 4, "ice")
        if dmg > 0:
            combat['enemy_hp'] -= dmg
            combat['distance'] = "far"
            log_msg += f"❄️ Лед нанес {dmg} урона и отбросил врага!{note}\n"
        else:
            log_msg += note

    if "урон током" in p_lower:
        dmg, note = calc_element_dmg(35 + user.get('level', 1) * 6, "shock")
        if dmg > 0:
            combat['enemy_hp'] -= dmg
            log_msg += f"⚡ Электрошок: {dmg} урона сквозь броню!{note}\n"
        else:
            log_msg += note

    if "сила тьмы" in p_lower:
        dmg, note = calc_element_dmg(35 + user.get('level', 1) * 6, "dark")
        if dmg > 0:
            combat['enemy_hp'] -= dmg
            log_msg += f"🌑 Энергия Бездны: {dmg} урона!{note}\n"
        else:
            log_msg += note

    if "свет" in p_lower or "защита от тьмы" in p_lower:
        dmg, note = calc_element_dmg(40 + user.get('level', 1) * 5, "light")
        if dmg > 0:
            combat['enemy_hp'] -= dmg
            combat['debuff_blind'] = 0
            log_msg += f"☀️ Священное сияние: {dmg} святого урона!{note}\n"
        else:
            log_msg += note

    if "вампиризм" in p_lower:
        if "bleed" in immunes:
            log_msg += f"🚫 Нельзя выпить жизнь из бескровного существа!\n"
        else:
            v_dmg = 20
            combat['enemy_hp'] -= v_dmg
            user['hp'] = min(user['max_hp'], user['hp'] + v_dmg)
            log_msg += f"🩸 Иссушение врага на {v_dmg} ХП в вашу пользу!\n"

    if "оцепенение" in p_lower or "сон" in p_lower or "страх" in p_lower:
        combat['enemy_stun'] = 1
        log_msg += "💫 Враг парализован и пропустит следующий ход!\n"

    # 3. Экономика
    if "богатство" in p_lower or "удача" in p_lower:
        gold_b = random.randint(30, 80)
        user['gold'] += gold_b
        dungeon_data = user.get('dungeon_data', {})
        dungeon_data.setdefault('gathered_gold', 0)
        dungeon_data['gathered_gold'] += gold_b
        update_user(user['user_id'], dungeon_data=dungeon_data)
        log_msg += f"💰 Превращение в золото: +{gold_b} 🪙!\n"

    # 4. Побочки
    if "слабость" in p_lower or "ожог" in p_lower or "болезнь" in p_lower or "удушье" in p_lower:
        user['hp'] -= 15
        log_msg += "🤢 Побочный эффект: ожог пищевода (-15 ХП)!\n"
    if "хрупкость" in p_lower:
        combat['debuff_fragile'] = 3
        log_msg += "💔 Побочный эффект: броня ослаблена на 50% на 3 хода!\n"
    if "слепота" in p_lower:
        combat['debuff_blind'] = 2
        log_msg += "👁️ Побочный эффект: ослепление на 2 хода!\n"
    if "уязвимость" in p_lower:
        combat['debuff_vuln'] = 3
        log_msg += "🎯 Побочный эффект: входящий урон увеличен на 25% на 3 хода!\n"

    if 'coop_host' in combat:
        host = get_user(combat['coop_host'])
        host['combat_data']['enemy_hp'] = combat['enemy_hp']
        update_user(host['user_id'], combat_data=host['combat_data'])

    if user['hp'] <= 0:
        apply_death_penalty(user['user_id'], user.get('dungeon_data', {}))
        update_user(user['user_id'], state='STATE_TOWN', combat_data={}, dungeon_data={})
        from handlers.town import get_town_kb
        return await callback.message.edit_text("☠️ **Вы погибли от побочного эффекта зелья!**", reply_markup=get_town_kb(), parse_mode="Markdown")

    if combat.get('enemy_hp', 50) <= 0:
        return await handle_combat_victory(callback, user['user_id'], combat)

    update_user(user['user_id'], hp=user['hp'], inventory=inv, combat_data=combat)
    await render_combat(callback, user, combat, log_msg)

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
