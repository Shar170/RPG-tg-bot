import random
import datetime
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database import (
    get_user, update_user, get_item, get_loot_table, get_item_name, get_setting,
    apply_flee_penalty, apply_death_penalty, add_quest_progress, get_clan, update_clan,
    calculate_damage_received, progress_war_region, track_stat, add_global_event,
    roll_card, log_event  
)
from utils.potions import analyze_traits, parse_custom_potion_traits, get_potion_display_name
from i18n import t

router = Router()

def get_combat_kb(ap: int, distance: str):
    buttons = [
        [InlineKeyboardButton(text=t("combat.btn.attack") if ap >= 2 else t("combat.btn.attack_no"), callback_data="combat_act_attack")],
        [InlineKeyboardButton(text=t("combat.btn.retreat") if distance == "close" else t("combat.btn.close_in") if ap >= 1 else t("combat.btn.move_no"), callback_data="combat_act_move")],
        [InlineKeyboardButton(text=t("combat.btn.potion"), callback_data="combat_act_potion"), InlineKeyboardButton(text=t("combat.btn.end_turn"), callback_data="combat_act_end_turn")],
        [InlineKeyboardButton(text=t("combat.btn.flee"), callback_data="combat_act_flee")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_combat_effects(combat: dict) -> tuple[str, str]:
    p_badges = []
    e_badges = []
    
    if combat.get('buff_armor', 0) > 0: p_badges.append(t("combat.effect.armor", v=combat['buff_armor'], turns=combat.get('buff_armor_t', 1)))
    if combat.get('buff_str', 0) > 0: p_badges.append(t("combat.effect.str", v=combat['buff_str'], turns=combat.get('buff_str_t', 1)))
    if combat.get('buff_dodge', 0) > 0: p_badges.append(t("combat.effect.dodge", p=int(combat['buff_dodge']*100), turns=combat.get('buff_dodge_t', 1)))
    if combat.get('debuff_blind', 0) > 0: p_badges.append(t("combat.effect.blind", turns=combat['debuff_blind']))
    if combat.get('debuff_fragile', 0) > 0: p_badges.append(t("combat.effect.fragile", turns=combat['debuff_fragile']))
    if combat.get('debuff_vuln', 0) > 0: p_badges.append(t("combat.effect.vuln", turns=combat['debuff_vuln']))
    
    if combat.get('enemy_blind', 0) > 0: e_badges.append(t("combat.effect.enemy_blind", turns=combat['enemy_blind']))
    if combat.get('enemy_vuln', 0) > 0: e_badges.append(t("combat.effect.enemy_vuln", turns=combat['enemy_vuln']))
    if combat.get('dot_burn', 0) > 0: e_badges.append(t("combat.effect.burn", turns=combat['dot_burn']))
    if combat.get('dot_poison', 0) > 0: e_badges.append(t("combat.effect.poison", turns=combat['dot_poison']))
    if combat.get('dot_bleed', 0) > 0: e_badges.append(t("combat.effect.bleed", turns=combat['dot_bleed']))
    if combat.get('enemy_stun', 0) > 0: e_badges.append(t("combat.effect.stun", turns=combat['enemy_stun']))

    p_text = " | ".join(p_badges) if p_badges else t("common.none")
    e_text = " | ".join(e_badges) if e_badges else t("common.none")
    return p_text, e_text

async def render_combat(callback: CallbackQuery, user: dict, combat: dict, log_msg: str):
    dist_str = t("combat.dist.close") if combat.get('distance', 'close') == "close" else t("combat.dist.far")
    ap_icons = "🟢 " * combat.get('ap', 3) + "⚪ " * (3 - combat.get('ap', 3))
    enemy_name = combat.get('enemy_name', t("combat.enemy_default"))
    enemy_hp = combat.get('enemy_hp', 50)
    enemy_max = combat.get('enemy_max_hp', 50)
    p_effects, e_effects = get_combat_effects(combat)

    text = (t("combat.title", name=enemy_name)
            + t("combat.enemy_hp", hp=enemy_hp, max=enemy_max)
            + t("combat.enemy_effects", effects=e_effects)
            + "━━━━━━━━━━━━━━\n"
            + t("combat.you_hp", hp=user['hp'], max=user['max_hp'])
            + t("combat.distance", dist=dist_str)
            + t("combat.ap", icons=ap_icons)
            + t("combat.your_effects", effects=p_effects)
            + t("combat.log", log=log_msg))
    await callback.message.edit_text(text, reply_markup=get_combat_kb(combat.get('ap', 3), combat.get('distance', 'close')), parse_mode="Markdown")

async def handle_combat_victory(callback: CallbackQuery, user_id: int, combat: dict):
    fresh_user = get_user(user_id)
    
    if combat.get('is_story'):
        win_node = combat.get('win_node')
        update_user(user_id, state='STATE_STORY', combat_data={})
        from handlers.story import render_story_node
        await callback.answer(t("combat.victory.story"))
        return await render_story_node(callback, fresh_user, win_node)
        
    inv = fresh_user['inventory']
    dungeon_data = fresh_user.get('dungeon_data', {})
    
    if dungeon_data.get('dungeon_type', 'solo') == "event":
        location_id = f"event_{datetime.datetime.today().weekday()}"
    else:
        location_id = dungeon_data.get('location_id', 'solo')
        
    current_node_data = (dungeon_data.get("nodes") or {}).get(dungeon_data.get("current_node")) or {}
    is_boss = current_node_data.get("type") == "boss" or (bool(current_node_data) and not current_node_data.get("next"))

    home = fresh_user.get('home_data', {})
    stats = home.setdefault('stats', {})
    
    stats['mobs_killed'] = stats.get('mobs_killed', 0) + 1
    
    enemy_id = combat.get('enemy_id', '')
    if enemy_id:
        stats[f"kills_{enemy_id}"] = stats.get(f"kills_{enemy_id}", 0) + 1
        
    if is_boss:
        stats['bosses_killed'] = stats.get('bosses_killed', 0) + 1

    add_quest_progress(user_id, "kill_mobs", 1)

    mod = combat.get('mob_modifier', 1.0)
    reward_gold = int(random.randint(combat.get('gold_min', 5), combat.get('gold_max', 15)) * mod)
    
    gained_xp = int(combat.get('xp_reward', 10) * mod)
    if is_boss and dungeon_data.get('saved_prisoner'):
        bonus_xp = fresh_user.get('level', 1) * 35
        gained_xp += bonus_xp
        lvl_msg = t("combat.xp_bonus", xp=gained_xp)
    else:
        lvl_msg = t("combat.xp", xp=gained_xp)

    fresh_user['gold'] += reward_gold
    dungeon_data.setdefault('gathered_gold', 0)
    dungeon_data['gathered_gold'] += reward_gold

    fresh_user['xp'] = fresh_user.get('xp', 0) + gained_xp

    while fresh_user['xp'] >= fresh_user.get('level', 1) * 100:
        fresh_user['xp'] -= fresh_user['level'] * 100
        fresh_user['level'] += 1
        fresh_user['max_hp'] += 15
        fresh_user['hp'] = fresh_user['max_hp']
        lvl_msg += t("combat.new_level", level=fresh_user['level'])

    drop_msg = f"{lvl_msg}\n" + t("combat.gold_found", gold=reward_gold)

    loot_table = get_loot_table(location_id)
    random.shuffle(loot_table)
    max_drops = random.randint(5, 8) if is_boss else random.randint(1, 2)
    dropped_count = 0

    for loot in loot_table:
        if dropped_count >= max_drops: break
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
            drop_msg += t("combat.loot_drop", item=get_item_name(loot['item_id']), qty=qty)
            dropped_count += 1

    if is_boss:
        c1 = roll_card(user_id)
        c2 = roll_card(user_id)
        if c1: drop_msg += t("combat.card_trophy", emoji=c1['emoji'], name=c1['name'], rarity=c1['rarity'])
        if c2: drop_msg += t("combat.card_trophy", emoji=c2['emoji'], name=c2['name'], rarity=c2['rarity'])

    if dungeon_data.get('dungeon_type') == 'war' and is_boss:
        home, bonus_gems = progress_war_region(dungeon_data['war_region_id'], user_id, home_data=home)
        fresh_user['gems'] = fresh_user.get('gems', 0) + bonus_gems
        drop_msg += t("combat.war_contribution")
        add_global_event(f"🌍 Игрок **{fresh_user['username']}** нанес сокрушительный удар по силам демонов в Войне за Камарию!")
        if bonus_gems > 0:
            drop_msg += t("combat.region_free", gems=bonus_gems)
            add_global_event(f"🏆 Великий герой **{fresh_user['username']}** нанес решающий удар и полностью ОСВОБОДИЛ один из регионов!")
            
    elif is_boss and dungeon_data.get('dungeon_type') == 'event':
        add_global_event(f"💀 Игрок **{fresh_user['username']}** бросил вызов Боссу Дня и вышел победителем!")

    update_user(
        user_id, state='STATE_DUNGEON', gold=fresh_user['gold'], gems=fresh_user.get('gems', 0),
        hp=fresh_user['hp'], max_hp=fresh_user['max_hp'], level=fresh_user['level'], xp=fresh_user['xp'],
        inventory=inv, combat_data={}, dungeon_data=dungeon_data, home_data=home
    )

    if is_boss:
        add_quest_progress(user_id, "raid_success", 1)
        if fresh_user['clan_id'] != 0:
            clan = get_clan(fresh_user['clan_id'])
            if clan:
                update_clan(clan['clan_id'], weekly_raids=clan.get('weekly_raids', 0) + 1, total_raids=clan.get('total_raids', 0) + 1)
        from handlers.town import get_town_kb
        update_user(user_id, state='STATE_TOWN', dungeon_data={})
        if 'coop_host' in combat:
            return await callback.message.edit_text(t("combat.coop_boss", drop=drop_msg), reply_markup=get_town_kb(fresh_user), parse_mode="Markdown")
        return await callback.message.edit_text(t("combat.raid_done", drop=drop_msg), reply_markup=get_town_kb(fresh_user), parse_mode="Markdown")
    else:
        from handlers.dungeon import get_navigation_kb
        if 'coop_host' in combat:
            from handlers.town import get_town_kb
            update_user(user_id, state='STATE_TOWN', dungeon_data={})
            return await callback.message.edit_text(t("combat.coop_help", drop=drop_msg), reply_markup=get_town_kb(fresh_user), parse_mode="Markdown")
        return await callback.message.edit_text(t("combat.victory", drop=drop_msg), reply_markup=get_navigation_kb(dungeon_data), parse_mode="Markdown")

@router.callback_query(F.data.startswith("coop_join_"))
async def join_coop(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    host_id = int(callback.data.replace("coop_join_", ""))
    host_user = get_user(host_id)
    if not host_user or host_user['state'] != 'STATE_COMBAT': return await callback.answer(t("combat.coop.host_finished"), show_alert=True)
    combat_data = host_user['combat_data'].copy()
    combat_data['coop_host'] = host_id
    combat_data['ap'] = 3
    update_user(user['user_id'], state='STATE_COMBAT', combat_data=combat_data)
    await render_combat(callback, user, combat_data, t("combat.coop.join", name=host_user['username']))

@router.callback_query(F.data == "combat_act_attack")
async def combat_attack(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    combat = user.get('combat_data', {})
    if combat.get('ap', 0) < 2: return await callback.answer(t("combat.err.ap"), show_alert=True)
    combat['ap'] -= 2

    if 'coop_host' in combat:
        host = get_user(combat['coop_host'])
        if host['state'] != 'STATE_COMBAT':
            update_user(user['user_id'], state='STATE_TOWN', combat_data={})
            from handlers.town import get_town_kb
            return await callback.message.edit_text(t("combat.coop.monster_dead"), reply_markup=get_town_kb(user))
        enemy_hp = host['combat_data'].get('enemy_hp', 50)
    else: enemy_hp = combat.get('enemy_hp', 50)

    if combat.get('debuff_blind', 0) > 0 and random.random() < 0.4:
        log_msg = t("combat.attack.blind")
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
        if combat.get('enemy_vuln', 0) > 0: dmg = int(dmg * 1.25)

        mob_skills = combat.get('mob_skills', {})
        enemy_name = combat.get('enemy_name', t("combat.enemy_default"))

        if random.random() < mob_skills.get("dodge", 0):
            log_msg = t("combat.attack.dodge", name=enemy_name)
        else:
            enemy_hp -= dmg
            log_event(user['user_id'], 'combat', 'damage_dealt', dmg, {'enemy': enemy_name, 'weapon_id': weapon_id})
            log_msg = t("combat.attack.hit", dmg=dmg)
            if extra_str > 0: log_msg += t("combat.attack.str_bonus", v=extra_str)
            if combat.get('enemy_vuln', 0) > 0: log_msg += t("combat.attack.vuln")
            if row_mult < 1.0: log_msg += t("combat.attack.dist_penalty")

            if enemy_hp > 0 and random.random() < mob_skills.get("counter", 0):
                counter_dmg = int(dmg * 0.5)
                user['hp'] -= counter_dmg
                log_event(user['user_id'], 'combat', 'damage_taken', -counter_dmg, {'enemy': enemy_name, 'source': 'counter'})
                log_msg += t("combat.attack.counter", dmg=counter_dmg)
                
                if user['hp'] <= 0:
                    log_event(user['user_id'], 'combat', 'death', 0, {'enemy': enemy_name, 'dungeon_type': user.get('dungeon_data', {}).get('dungeon_type')})
                    track_stat(user['user_id'], 'deaths_count', 1)
                    
                    if combat.get('is_story'):
                        lose_node = combat.get('lose_node')
                        update_user(user['user_id'], state='STATE_STORY', combat_data={}, hp=max(1, int(user['max_hp'] * 0.1))) 
                        from handlers.story import render_story_node
                        await callback.answer(t("combat.story.defeated"), show_alert=True)
                        return await render_story_node(callback, user, lose_node)
                        
                    apply_death_penalty(user['user_id'], user.get('dungeon_data', {}))
                    update_user(user['user_id'], state='STATE_TOWN', combat_data={}, dungeon_data={})
                    from handlers.town import get_town_kb
                    fresh = get_user(user['user_id']) or user
                    return await callback.message.edit_text(t("combat.death"), reply_markup=get_town_kb(fresh), parse_mode="Markdown")

    if 'coop_host' in combat:
        host = get_user(combat['coop_host'])
        host['combat_data']['enemy_hp'] = enemy_hp
        update_user(host['user_id'], combat_data=host['combat_data'])
    combat['enemy_hp'] = enemy_hp

    if enemy_hp <= 0: return await handle_combat_victory(callback, user['user_id'], combat)

    update_user(user['user_id'], hp=user['hp'], combat_data=combat)
    await render_combat(callback, user, combat, log_msg)

@router.callback_query(F.data == "combat_act_move")
async def combat_move(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    combat = user.get('combat_data', {})
    if combat.get('ap', 0) < 1: return await callback.answer(t("combat.err.ap"), show_alert=True)
    combat['ap'] -= 1
    if combat.get('distance', 'close') == "close":
        combat['distance'] = "far"
        log_msg = t("combat.move.retreat")
    else:
        combat['distance'] = "close"
        log_msg = t("combat.move.close_in")
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
            return await callback.message.edit_text(t("combat.coop.monster_dead_short"), reply_markup=get_town_kb(user))
        combat['enemy_hp'] = host['combat_data'].get('enemy_hp', 50)

    log_parts = []
    dot_dmg = 0
    if combat.get('dot_burn', 0) > 0: dot_dmg += 15; combat['dot_burn'] -= 1; log_parts.append(t("combat.dot.burn_log"))
    if combat.get('dot_poison', 0) > 0: dot_dmg += 12; combat['dot_poison'] -= 1; log_parts.append(t("combat.dot.poison_log"))
    if combat.get('dot_bleed', 0) > 0: dot_dmg += 10; combat['dot_bleed'] -= 1; log_parts.append(t("combat.dot.bleed_log"))

    if dot_dmg > 0:
        combat['enemy_hp'] -= dot_dmg
        if combat['enemy_hp'] <= 0:
            if 'coop_host' in combat:
                host = get_user(combat['coop_host'])
                host['combat_data']['enemy_hp'] = combat['enemy_hp']
                update_user(host['user_id'], combat_data=host['combat_data'])
            return await handle_combat_victory(callback, user['user_id'], combat)

    if combat.get('enemy_stun', 0) > 0:
        combat['enemy_stun'] -= 1
        log_parts.append(t("combat.stun.skip"))
    else:
        dodge_chance = 0.05 + combat.get('buff_dodge', 0.0)
        enemy_name = combat.get('enemy_name', t("combat.enemy_default"))
        if combat.get('enemy_blind', 0) > 0 and random.random() < 0.4: log_parts.append(t("combat.enemy_blind_miss", name=enemy_name))
        elif random.random() < dodge_chance: log_parts.append(t("combat.dodge"))
        else:
            armor_id = user['inventory'].get("equipment", {}).get("armor")
            base_armor = get_item(armor_id)['stats'].get('def', 0) if armor_id else 0
            if combat.get('debuff_fragile', 0) > 0: base_armor = int(base_armor * 0.5)

            total_armor = base_armor + combat.get('buff_armor', 0)
            mob_skills = combat.get('mob_skills', {})
            mob_pref_dist = "close" if combat.get('mob_pref', 'front') == "front" else "far"
            
            if combat.get('distance', 'close') != mob_pref_dist and random.random() < mob_skills.get('reposition', 0):
                combat['distance'] = mob_pref_dist
                action = t("combat.enemy_move_close") if mob_pref_dist == "close" else t("combat.enemy_move_far")
                log_parts.append(action)

            dmg_min, dmg_max = combat.get('dmg_min', 10), combat.get('dmg_max', 15)
            raw_dmg = random.randint(dmg_min, dmg_max)
            if combat.get('distance', 'close') != mob_pref_dist: raw_dmg = int(raw_dmg * 0.5)
            if combat.get('debuff_vuln', 0) > 0: raw_dmg = int(raw_dmg * 1.25)

            monster_dmg = calculate_damage_received(raw_dmg, total_armor)
            user['hp'] -= monster_dmg
            log_event(user['user_id'], 'combat', 'damage_taken', -monster_dmg, {'enemy': enemy_name, 'source': 'attack'})
            log_parts.append(t("combat.enemy_hit", dmg=monster_dmg))

            if random.random() < mob_skills.get('poison', 0):
                user['hp'] -= 10
                log_parts.append(t("combat.enemy_poison"))

    for buff_t in ['buff_armor_t', 'buff_str_t', 'buff_dodge_t', 'debuff_blind', 'debuff_fragile', 'debuff_vuln', 'enemy_blind', 'enemy_vuln']:
        if combat.get(buff_t, 0) > 0:
            combat[buff_t] -= 1
            if combat[buff_t] == 0:
                attr = buff_t.replace('_t', '')
                combat[attr] = 0

    if user['hp'] <= 0:
        log_event(user['user_id'], 'combat', 'death', 0, {'enemy': enemy_name, 'dungeon_type': user.get('dungeon_data', {}).get('dungeon_type')})
        track_stat(user['user_id'], 'deaths_count', 1)
        
        if combat.get('is_story'):
            lose_node = combat.get('lose_node')
            update_user(user['user_id'], state='STATE_STORY', combat_data={}, hp=max(1, int(user['max_hp'] * 0.1))) 
            from handlers.story import render_story_node
            await callback.answer(t("combat.story.defeated"), show_alert=True)
            return await render_story_node(callback, user, lose_node)
            
        apply_death_penalty(user['user_id'], user.get('dungeon_data', {}))
        update_user(user['user_id'], state='STATE_TOWN', combat_data={}, dungeon_data={})
        from handlers.town import get_town_kb
        fresh = get_user(user['user_id']) or user
        return await callback.message.edit_text(t("combat.death_short"), reply_markup=get_town_kb(fresh), parse_mode="Markdown")

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
    if combat.get('ap', 0) < 1: return await callback.answer(t("combat.err.ap"), show_alert=True)
    potions = list(dict.fromkeys(inv.get("potions", [])))
    if not potions: return await callback.answer(t("combat.potion.none"), show_alert=True)

    buttons = []
    for i, p in enumerate(potions):
        count = inv["potions"].count(p)
        name = get_item_name(p)
        buttons.append([InlineKeyboardButton(text=t("combat.potion.use", name=name, count=count), callback_data=f"c_drink_{i}")])
        
    buttons.append([InlineKeyboardButton(text=t("combat.potion.cancel"), callback_data="c_drink_cancel")])
    await callback.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@router.callback_query(F.data == "c_drink_cancel")
async def combat_drink_cancel(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    combat = user.get('combat_data', {})
    await callback.message.edit_reply_markup(reply_markup=get_combat_kb(combat.get('ap', 3), combat.get('distance', 'close')))

@router.callback_query(F.data.startswith("c_drink_"))
async def execute_drink_combat(callback: CallbackQuery):
    if callback.data == "c_drink_cancel": return
    user = get_user(callback.from_user.id)
    combat = user.get('combat_data', {})
    inv = user['inventory']
    if combat.get('ap', 0) < 1: return await callback.answer(t("combat.err.ap"), show_alert=True)

    unique_potions = list(dict.fromkeys(inv.get("potions", [])))
    idx = int(callback.data.replace("c_drink_", ""))
    if idx >= len(unique_potions): return await callback.answer(t("combat.potion.error"), show_alert=True)

    used_item = unique_potions[idx]
    inv["potions"].remove(used_item)
    combat['ap'] -= 1

    if 'coop_host' in combat:
        host = get_user(combat['coop_host'])
        if host['state'] != 'STATE_COMBAT':
            update_user(user['user_id'], state='STATE_TOWN', combat_data={})
            from handlers.town import get_town_kb
            return await callback.message.edit_text(t("combat.coop.monster_dead"), reply_markup=get_town_kb(user))
        combat['enemy_hp'] = host['combat_data'].get('enemy_hp', 50)

    mob_skills = combat.get('mob_skills', {})
    immunes = mob_skills.get('immune', [])
    weaks = mob_skills.get('weak', [])
    resists = mob_skills.get('resist', [])
    enemy_name = combat.get('enemy_name', t("combat.enemy_default"))

    def calc_element_dmg(base_val: int, elem: str) -> tuple[int, str]:
        if elem in immunes: return 0, t("combat.immune", name=enemy_name, elem=elem)
        multiplier, note = 1.0, ""
        if elem in weaks: multiplier, note = 1.5, t("combat.weak_note")
        elif elem in resists: multiplier, note = 0.5, t("combat.resist_note")
        return int(base_val * multiplier), note

    # ИСПРАВЛЕНИЕ: Умная логика (БД предметы vs Кастомная Алхимия)
    item_data = get_item(used_item)

    if item_data and item_data.get('type') == 'consumable':
        # --- ЛОГИКА ДЛЯ СТАНДАРТНЫХ ПРЕДМЕТОВ ИЗ БД ---
        name = item_data['name']
        stats = item_data.get('stats', {})
        effect = stats.get('effect')
        heal_pct = stats.get('heal_pct')
        
        is_thrown = effect in ["escape", "bleed", "vuln"]
        log_msg = t("combat.potion.thrown", name=name) if is_thrown else t("combat.potion.applied", name=name)
        
        if heal_pct:
            heal = int(user['max_hp'] * heal_pct)
            user['hp'] = min(user['max_hp'], user['hp'] + heal)
            log_msg += t("combat.heal", heal=heal)
            
        if effect == "escape":
            combat['enemy_blind'] = 3
            log_msg += t("combat.potion.escape")
        elif effect == "bleed":
            combat['dot_bleed'] = 3
            log_msg += t("combat.potion.bleed")
        elif effect == "vuln":
            combat['enemy_vuln'] = 3
            log_msg += t("combat.potion.vuln")
        elif effect == "cleanse":
            combat['debuff_blind'] = 0
            combat['debuff_fragile'] = 0
            combat['debuff_vuln'] = 0
            log_msg += t("combat.potion.cleanse")
        elif effect == "ap_boost":
            combat['ap'] += 3
            log_msg += t("combat.potion.ap_boost")

    else:
        # --- КАСТОМНАЯ АЛХИМИЯ: эффекты считаются по ID свойств ---
        trait_ids = parse_custom_potion_traits(used_item)
        effects = analyze_traits(trait_ids)
        is_thrown = effects["is_thrown"]
        potion_name = get_potion_display_name(used_item)
        
        log_msg = t("combat.potion.thrown", name=potion_name) if is_thrown else t("combat.potion.drank", name=potion_name)

        if effects["heal_pct"]:
            heal = int(user['max_hp'] * effects["heal_pct"])
            user['hp'] = min(user['max_hp'], user['hp'] + heal)
            log_msg += t("combat.heal", heal=heal)
        if effects["ap_bonus"]:
            combat['ap'] += effects["ap_bonus"]
            log_msg += t("combat.potion.ap_bonus", v=effects['ap_bonus'])
        if effects["armor_bonus"]:
            combat['buff_armor'] = combat.get('buff_armor', 0) + effects["armor_bonus"]
            combat['buff_armor_t'] = effects["armor_turns"]
            log_msg += t("combat.potion.armor_bonus", v=effects['armor_bonus'], turns=effects['armor_turns'])
        if effects["str_bonus"]:
            combat['buff_str'] = combat.get('buff_str', 0) + effects["str_bonus"]
            combat['buff_str_t'] = effects["str_turns"]
            log_msg += t("combat.potion.str_bonus", v=effects['str_bonus'], turns=effects['str_turns'])
        if effects["dodge_bonus"]:
            combat['buff_dodge'] = effects["dodge_bonus"]
            combat['buff_dodge_t'] = effects["dodge_turns"]
            log_msg += t("combat.potion.dodge_bonus", p=int(effects['dodge_bonus'] * 100), turns=effects['dodge_turns'])
        if effects["cleanse"]:
            combat['debuff_blind'] = 0
            combat['debuff_fragile'] = 0
            combat['debuff_vuln'] = 0
            log_msg += t("combat.potion.cleanse2")

        element_labels = {
            "fire": ("🔥", t("combat.element.fire")),
            "poison": ("🟢", t("combat.element.poison")),
            "ice": ("❄️", t("combat.element.ice")),
            "shock": ("⚡", t("combat.element.shock")),
            "dark": ("🌑", t("combat.element.dark")),
            "light": ("☀️", t("combat.element.light")),
        }
        for event in effects["damage_events"]:
            base = event["base"] + user.get('level', 1) * event.get("scale", 0)
            dmg, note = calc_element_dmg(base, event["element"])
            icon, label = element_labels.get(event["element"], ("✨", event["element"]))
            if dmg > 0:
                combat['enemy_hp'] -= dmg
                extra = ""
                if event.get("dot"):
                    combat[event["dot"]] = event["dot_turns"]
                    extra = t("combat.dot_extra", turns=event['dot_turns'])
                if event["element"] == "ice":
                    extra += t("combat.ice_extra")
                log_msg += t("combat.element_dmg", icon=icon, label=label, dmg=dmg, extra=extra, note=note)
            else:
                log_msg += note

        if "bleed" in trait_ids:
            if "bleed" in immunes:
                log_msg += t("combat.no_blood", name=enemy_name)
            else:
                combat['dot_bleed'] = 3
                log_msg += t("combat.bleed_applied")

        if effects["vampirism"]:
            if "bleed" in immunes:
                log_msg += t("combat.vamp_immune")
            else:
                v_dmg = effects["vampirism"]
                combat['enemy_hp'] -= v_dmg
                user['hp'] = min(user['max_hp'], user['hp'] + v_dmg)
                log_msg += t("combat.vamp", v=v_dmg)

        if effects["enemy_stun"]:
            combat['enemy_stun'] = 1
            log_msg += t("combat.stun_applied")

        if effects["gold_range"]:
            gold_b = random.randint(*effects["gold_range"])
            user['gold'] += gold_b
            dungeon_data = user.get('dungeon_data', {})
            dungeon_data.setdefault('gathered_gold', 0)
            dungeon_data['gathered_gold'] += gold_b
            update_user(user['user_id'], gold=user['gold'], dungeon_data=dungeon_data)
            log_msg += t("combat.gold_transform", gold=gold_b)

        if effects["enemy_flat_damage"]:
            combat['enemy_hp'] -= effects["enemy_flat_damage"]
            log_msg += t("combat.flask", v=effects['enemy_flat_damage'])
        if effects["self_damage"]:
            user['hp'] -= effects["self_damage"]
            log_msg += t("combat.self_damage", v=effects['self_damage'])

        enemy_debuff_logs = {
            "debuff_vuln": t("combat.enemy_debuff.vuln"),
            "debuff_blind": t("combat.enemy_debuff.blind"),
        }
        for key, turns in effects["enemy_debuffs"].items():
            combat[key] = turns
            log_msg += enemy_debuff_logs.get(key, t("combat.enemy_debuff.default"))

        self_debuff_logs = {
            "debuff_fragile": t("combat.self_debuff.fragile"),
            "debuff_blind": t("combat.self_debuff.blind"),
            "debuff_vuln": t("combat.self_debuff.vuln"),
        }
        for key, turns in effects["self_debuffs"].items():
            combat[key] = turns
            log_msg += self_debuff_logs.get(key, t("combat.self_debuff.default"))

        if effects["distance"]:
            combat["distance"] = effects["distance"]

    # --- ЗАВЕРШЕНИЕ ЭФФЕКТОВ ---
    if 'coop_host' in combat:
        host = get_user(combat['coop_host'])
        host['combat_data']['enemy_hp'] = combat['enemy_hp']
        update_user(host['user_id'], combat_data=host['combat_data'])

    if user['hp'] <= 0:
        log_event(user['user_id'], 'combat', 'death', 0, {'enemy': enemy_name, 'source': 'potion_side_effect', 'potion': used_item})
        track_stat(user['user_id'], 'deaths_count', 1)
        
        if combat.get('is_story'):
            lose_node = combat.get('lose_node')
            update_user(user['user_id'], state='STATE_STORY', combat_data={}, hp=max(1, int(user['max_hp'] * 0.1))) 
            from handlers.story import render_story_node
            await callback.answer(t("combat.story.defeated"), show_alert=True)
            return await render_story_node(callback, user, lose_node)
            
        apply_death_penalty(user['user_id'], user.get('dungeon_data', {}))
        update_user(user['user_id'], state='STATE_TOWN', combat_data={}, dungeon_data={})
        from handlers.town import get_town_kb
        fresh = get_user(user['user_id']) or user
        return await callback.message.edit_text(t("combat.potion_death"), reply_markup=get_town_kb(fresh), parse_mode="Markdown")

    # Фиксируем расход зелья и изменения ХП до проверки победы:
    # handle_combat_victory перечитывает игрока из БД.
    update_user(user['user_id'], hp=user['hp'], inventory=inv, combat_data=combat)

    if combat.get('enemy_hp', 50) <= 0: return await handle_combat_victory(callback, user['user_id'], combat)

    await render_combat(callback, user, combat, log_msg)

@router.callback_query(F.data == "combat_act_flee")
async def combat_flee(callback: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("combat.flee.confirm_btn"), callback_data="combat_act_flee_confirm")],
        [InlineKeyboardButton(text=t("combat.flee.stay_btn"), callback_data="combat_act_flee_cancel")]
    ])
    await callback.message.edit_text(t("combat.flee.confirm"), reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data == "combat_act_flee_confirm")
async def combat_flee_confirm(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    track_stat(user['user_id'], 'flees_count', 1)
    lost_gold, lost_mats = apply_flee_penalty(user['user_id'], user.get('dungeon_data', {}))
    
    log_event(user['user_id'], 'combat', 'flee', -lost_gold, {'lost_mats': lost_mats})
    
    update_user(user['user_id'], state='STATE_TOWN', combat_data={}, dungeon_data={})
    from handlers.town import get_town_kb
    mats_str = t("combat.flee.lost_mats", mats=', '.join(lost_mats)) if lost_mats else ""
    await callback.message.edit_text(t("combat.flee.lost", gold=lost_gold, mats=mats_str), reply_markup=get_town_kb(user), parse_mode="Markdown")

@router.callback_query(F.data == "combat_act_flee_cancel")
async def combat_flee_cancel(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    if user.get('state') == 'STATE_COMBAT':
        combat = user.get('combat_data', {})
        await render_combat(callback, user, combat, t("combat.flee.stay"))
    else:
        d_data = user.get('dungeon_data', {})
        from handlers.dungeon import get_navigation_kb
        await callback.message.edit_text(t("combat.flee.cancel"), reply_markup=get_navigation_kb(d_data), parse_mode="Markdown")

