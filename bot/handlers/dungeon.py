import random
import time
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database import (
    get_user, update_user, consume_energy, get_today_dungeon,
    get_all_war_regions, get_all_solo_dungeons, get_solo_dungeon, 
    get_scaled_mob, track_stat, get_energy_settings, apply_death_penalty, get_setting,
    roll_card, log_event, get_random_material_id, get_item_name
)
from utils.generators import generate_dungeon_graph
from i18n import t

router = Router()

def get_navigation_kb(dungeon_data: dict):
    curr = dungeon_data.get("current_node")
    next_nodes = dungeon_data.get("nodes", {}).get(curr, {}).get("next", [])
    buttons = []

    type_labels = {
        "combat": t("dungeon.nav.combat"),
        "boss": t("dungeon.nav.boss"),
        "campfire": t("dungeon.nav.campfire"),
        "puzzle": t("dungeon.nav.puzzle"),
        "treasure": t("dungeon.nav.treasure"),
        "empty": t("dungeon.nav.empty"),
        "sleeping_enemy": t("dungeon.nav.sleeping_enemy"),
        "prisoner": t("dungeon.nav.prisoner"),
        "map_room": t("dungeon.nav.map_room"),
        "sanctuary": t("dungeon.nav.sanctuary")
    }

    for nxt in next_nodes:
        n_info = dungeon_data["nodes"].get(nxt, {})
        n_type = n_info.get("type", "empty")
        label = type_labels.get(n_type, t("dungeon.nav.unknown"))
        buttons.append([InlineKeyboardButton(text=t("dungeon.nav.forward", label=label), callback_data=f"dungeon_go_{nxt}")])

    if next_nodes:
        buttons.append([InlineKeyboardButton(text=t("dungeon.nav.flee"), callback_data="combat_act_flee")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

@router.callback_query(F.data == "town_dungeon_menu")
async def select_dungeon_mode(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    e_cfg = get_energy_settings(user.get('level', 1))

    solo_badge = f" ({e_cfg['cost_solo']} ⚡)" if e_cfg['cost_solo'] > 0 else ""
    event_badge = f" ({e_cfg['cost_event']} ⚡)" if e_cfg['cost_event'] > 0 else ""
    war_badge = f" ({e_cfg['cost_war']} ⚡)" if e_cfg['cost_war'] > 0 else ""

    text = (
        t("dungeon.menu.title")
        + t("dungeon.menu.prompt")
        + t("dungeon.menu.solo")
        + t("dungeon.menu.event")
        + t("dungeon.menu.war")
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("dungeon.btn.solo", badge=solo_badge), callback_data="dungeon_start_solo")],
        [InlineKeyboardButton(text=t("dungeon.btn.event", badge=event_badge), callback_data="dungeon_start_event")],
        [InlineKeyboardButton(text=t("dungeon.btn.war", badge=war_badge), callback_data="war_hub")],
        [InlineKeyboardButton(text=t("dungeon.btn.back_town"), callback_data="town_back")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data == "dungeon_start_solo")
async def start_solo_dungeon(callback: CallbackQuery):
    dungeons = get_all_solo_dungeons()
    
    text = t("dungeon.solo.title")
    buttons = []
    
    for d in dungeons:
        text += t("dungeon.solo.location_line", name=d['name'], desc=d['desc'])
        buttons.append([InlineKeyboardButton(text=t("dungeon.solo.enter", name=d['name']), callback_data=f"dungeon_enter_solo:{d['id']}")])
        
    buttons.append([InlineKeyboardButton(text=t("dungeon.btn.back"), callback_data="town_dungeon_menu")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data.startswith("dungeon_enter_solo:"))
async def enter_solo_dungeon(callback: CallbackQuery):
    d_id = callback.data.split(":")[1]
    user = get_user(callback.from_user.id)
    dungeon = get_solo_dungeon(d_id)
    if not dungeon:
        return await callback.answer(t("dungeon.error.not_found"), show_alert=True)
    
    e_cfg = get_energy_settings(user.get('level', 1))
    cost = e_cfg["cost_solo"]
    
    if not consume_energy(user['user_id'], cost):
        return await callback.answer(t("dungeon.error.energy", cost=cost), show_alert=True)
        
    log_event(user['user_id'], 'progression', 'dungeon_start_solo', -cost, {'dungeon_id': d_id, 'currency': 'energy'})
        
    d_data = generate_dungeon_graph(
        dungeon_type="solo", 
        mobs_pool=dungeon['mobs'], 
        boss_id=dungeon['boss_id'],
        min_rooms=dungeon.get('min_rooms', 3),
        max_rooms=dungeon.get('max_rooms', 5),
        room_weights=dungeon.get('room_weights')
    )
    
    d_data['location_id'] = d_id
    update_user(user['user_id'], state='STATE_DUNGEON', dungeon_data=d_data)
    await enter_node(callback, user, d_data, d_data["current_node"])

@router.callback_query(F.data == "dungeon_start_event")
async def start_event_dungeon(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    today = get_today_dungeon()
    if not today:
        return await callback.answer(t("dungeon.error.closed"), show_alert=True)

    e_cfg = get_energy_settings(user.get('level', 1))
    cost = e_cfg["cost_event"]

    if not consume_energy(user['user_id'], cost):
        return await callback.answer(t("dungeon.error.energy", cost=cost), show_alert=True)

    log_event(user['user_id'], 'progression', 'dungeon_start_event', -cost, {'currency': 'energy'})

    d_data = generate_dungeon_graph(
        dungeon_type="event", 
        mobs_pool=today["mobs"], 
        boss_id=today["boss_id"],
        min_rooms=today.get('min_rooms', 3),
        max_rooms=today.get('max_rooms', 4),
        room_weights=today.get('room_weights')
    )
    update_user(user['user_id'], state='STATE_DUNGEON', dungeon_data=d_data)
    await enter_node(callback, user, d_data, d_data["current_node"])

@router.callback_query(F.data == "war_hub")
async def show_war_fronts(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    regions = get_all_war_regions()
    e_cfg = get_energy_settings(user.get('level', 1))
    cost_badge = f" ({e_cfg['cost_war']} ⚡)" if e_cfg['cost_war'] > 0 else ""

    text = t("dungeon.war.title")
    buttons = []
    for r in regions:
        filled = int(r['pct'] // 10)
        bar = "█" * filled + "░" * (10 - filled)
        status = t("dungeon.war.liberated") if r['is_liberated'] else t("dungeon.war.progress", bar=bar, pct=r['pct'])
        text += t("dungeon.war.line", name=r['name'], status=status, current=r['current'], target=r['target'])
        btn_label = t("dungeon.war.fight", name=r['name'], badge=cost_badge) if not r['is_liberated'] else t("dungeon.war.cleared", name=r['name'])
        buttons.append([InlineKeyboardButton(text=btn_label, callback_data=f"war_enter:{r['id']}")])

    if regions and all(r.get('is_liberated') for r in regions):
        reset_at = max((r.get('reset_at') or 0) for r in regions)
        if reset_at > 0:
            minutes = max(1, int((reset_at - time.time()) / 60) + 1)
            text += t("dungeon.war.reset_pending", minutes=minutes)

    buttons.append([InlineKeyboardButton(text=t("dungeon.btn.back"), callback_data="town_dungeon_menu")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data.startswith("war_enter:"))
async def enter_war_region(callback: CallbackQuery):
    reg_id = int(callback.data.split(":")[1])
    user = get_user(callback.from_user.id)

    # Сначала проверяем регион, чтобы не списывать энергию впустую
    regions = get_all_war_regions()
    region = next((r for r in regions if r['id'] == reg_id), None)
    if not region:
        return await callback.answer(t("dungeon.error.region_not_found"), show_alert=True)
    if region.get('is_liberated'):
        return await callback.answer(t("dungeon.error.region_liberated"), show_alert=True)

    e_cfg = get_energy_settings(user.get('level', 1))
    cost = e_cfg["cost_war"]

    if not consume_energy(user['user_id'], cost):
        return await callback.answer(t("dungeon.error.energy", cost=cost), show_alert=True)

    log_event(user['user_id'], 'progression', 'dungeon_start_war', -cost, {'region_id': reg_id, 'currency': 'energy'})

    d_data = generate_dungeon_graph(
        dungeon_type="war", 
        mobs_pool=region.get('mobs'), 
        boss_id=region.get('boss_id'),
        min_rooms=region.get('min_rooms', 4),
        max_rooms=region.get('max_rooms', 6),
        room_weights=region.get('room_weights')
    )
    d_data['war_region_id'] = reg_id
    d_data['war_cycle'] = region.get('cycle', 0)
    update_user(user['user_id'], state='STATE_DUNGEON', dungeon_data=d_data)
    await enter_node(callback, user, d_data, d_data["current_node"])

@router.callback_query(F.data.startswith("dungeon_go_"))
async def go_to_node(callback: CallbackQuery):
    target_node = callback.data.replace("dungeon_go_", "")
    user = get_user(callback.from_user.id)
    d_data = user.get('dungeon_data', {})
    current = (d_data.get('nodes') or {}).get(d_data.get('current_node'), {})
    if (user.get('state') != 'STATE_DUNGEON' or target_node not in current.get('next', [])
            or d_data.get('trap_active')
            or (current.get('type') == 'puzzle' and not current.get('puzzle_solved'))):
        return await callback.answer(t("dungeon.riddle.stale"), show_alert=True)
    d_data["current_node"] = target_node
    update_user(user['user_id'], dungeon_data=d_data)
    await enter_node(callback, user, d_data, target_node)
    try:
        await callback.answer()
    except Exception:
        pass

async def enter_node(callback: CallbackQuery, user: dict, d_data: dict, node_id: str):
    node = d_data["nodes"][node_id]
    n_type = node.get("type", "empty")

    start_node_id = list(d_data["nodes"].keys())[0]
    if node_id == start_node_id:
        text = t("dungeon.entered")
        return await callback.message.edit_text(text, reply_markup=get_navigation_kb(d_data), parse_mode="Markdown")

    if n_type in ["combat", "boss"]:
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
        boss_prefix = t("dungeon.boss_prefix") if n_type == "boss" else ""
        await render_combat(callback, user, combat_data, t("dungeon.enemy_attack", prefix=boss_prefix, name=mob['name']))

    elif n_type == "sleeping_enemy":
        mob_id = node.get("mob_id", "temple_guard")
        mob = get_scaled_mob(mob_id, player_lvl=user.get('level', 1))
        text = (
            t("dungeon.sleep.title")
            + t("dungeon.sleep.text", name=mob['name'])
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=t("dungeon.sleep.sneak"), callback_data=f"dungeon_sleep_sneak")],
            [InlineKeyboardButton(text=t("dungeon.sleep.attack"), callback_data=f"dungeon_sleep_attack")]
        ])
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

    elif n_type == "prisoner":
        text = (
            t("dungeon.prisoner.title")
            + t("dungeon.prisoner.text")
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=t("dungeon.prisoner.free"), callback_data="dungeon_pris_free")],
            [InlineKeyboardButton(text=t("dungeon.prisoner.kill"), callback_data="dungeon_pris_kill")],
            [InlineKeyboardButton(text=t("dungeon.prisoner.leave"), callback_data="dungeon_pris_leave")]
        ])
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

    elif n_type == "sanctuary":
        heal_amt = int(user['max_hp'] * 0.4)
        user['hp'] = min(user['max_hp'], user['hp'] + heal_amt)
        update_user(user['user_id'], hp=user['hp'])
        text = t("dungeon.sanctuary.text", heal=heal_amt, hp=user['hp'], max_hp=user['max_hp'])
        await callback.message.edit_text(text, reply_markup=get_navigation_kb(d_data), parse_mode="Markdown")

    elif n_type == "map_room":
        map_text = t("dungeon.map.title")
        visited = set()
        layer_nodes = [list(d_data["nodes"].keys())[0]]
        layer_idx = 1
        
        emoji_map = {
            "combat": "⚔️", "boss": "💀", "campfire": "🏕️", "puzzle": "🧩", 
            "treasure": "📦", "sleeping_enemy": "💤", "prisoner": "🔗", 
            "map_room": "🗺️", "sanctuary": "⛲", "empty": "💨"
        }
        
        while layer_nodes:
            row_str = t("dungeon.map.step", step=layer_idx)
            next_layer = []
            for n_id in layer_nodes:
                if n_id not in visited:
                    visited.add(n_id)
                    n_info = d_data["nodes"][n_id]
                    icon = emoji_map.get(n_info["type"], "💨")
                    if n_id == node_id:
                        icon = f"📍[{icon}]"
                    row_str += f"{icon} "
                    for nxt in n_info.get("next", []):
                        if nxt not in next_layer:
                            next_layer.append(nxt)
            map_text += row_str + "\n"
            layer_nodes = next_layer
            layer_idx += 1
            
        map_text += t("dungeon.map.legend")
        await callback.message.edit_text(map_text, reply_markup=get_navigation_kb(d_data), parse_mode="Markdown")

    elif n_type == "campfire":
        heal_amt = int(user['max_hp'] * 0.4)
        user['hp'] = min(user['max_hp'], user['hp'] + heal_amt)
        update_user(user['user_id'], hp=user['hp'])
        text = t("dungeon.campfire.text", heal=heal_amt, hp=user['hp'], max_hp=user['max_hp'])
        await callback.message.edit_text(text, reply_markup=get_navigation_kb(d_data), parse_mode="Markdown")

    elif n_type == "treasure":
        mimic_chance = float(get_setting("dungeon_mimic_chance", "0.15"))
        if random.random() < mimic_chance:
            mob_id = "golden_mimic"
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
            await render_combat(callback, user, combat_data, t("dungeon.mimic"))
        else:
            gold_find = random.randint(35, 80)
            user['gold'] += gold_find
            d_data.setdefault('gathered_gold', 0)
            d_data['gathered_gold'] += gold_find
            
            log_event(user['user_id'], 'economy', 'dungeon_treasure_gold', gold_find)
            
            card_msg = ""
            c1 = roll_card(user['user_id'])
            if c1: card_msg += t("dungeon.treasure.card", emoji=c1['emoji'], name=c1['name'], rarity=c1['rarity'])
            
            if random.random() < 0.2:
                c2 = roll_card(user['user_id'])
                if c2: card_msg += t("dungeon.treasure.bonus_card", emoji=c2['emoji'], name=c2['name'], rarity=c2['rarity'])
            
            update_user(user['user_id'], gold=user['gold'], dungeon_data=d_data)
            text = t("dungeon.treasure.text", gold=gold_find, cards=card_msg)
            await callback.message.edit_text(text, reply_markup=get_navigation_kb(d_data), parse_mode="Markdown")

    elif n_type == "empty":
        trap_chance = float(get_setting("dungeon_trap_chance", "0.2"))
        if random.random() < trap_chance:
            d_data['trap_active'] = True
            d_data['trap_side'] = random.choice(["left", "right"])
            update_user(user['user_id'], dungeon_data=d_data)
            
            text = t("dungeon.trap.text")
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text=t("dungeon.trap.left"), callback_data="trap_dodge_left"),
                    InlineKeyboardButton(text=t("dungeon.trap.right"), callback_data="trap_dodge_right")
                ]
            ])
            await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        else:
            track_stat(user['user_id'], 'empty_rooms', 1)
            text = t("dungeon.empty_room")
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
        for index, opt in enumerate(p_data["options"]):
            cb = f"riddle_ans:{index}"
            row.append(InlineKeyboardButton(text=str(opt), callback_data=cb))
            if len(row) == 2:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)

        await callback.message.edit_text(p_data["text"], reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")
        
    else:
        track_stat(user['user_id'], 'empty_rooms', 1)
        text = t("dungeon.unknown")
        await callback.message.edit_text(text, reply_markup=get_navigation_kb(d_data), parse_mode="Markdown")

@router.callback_query(F.data == "dungeon_sleep_sneak")
async def sleep_sneak(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    d_data = user.get('dungeon_data', {})
    node_id = d_data.get("current_node")
    node = d_data["nodes"][node_id]
    
    if random.random() < 0.4:
        mob_id = node.get("mob_id", "temple_guard")
        mob = get_scaled_mob(mob_id, player_lvl=user.get('level', 1))
        m_hp = random.randint(mob['hp_min'], mob['hp_max'])
        
        combat_data = {
            "enemy_id": mob['mob_id'], "enemy_name": mob['name'],
            "enemy_hp": m_hp, "enemy_max_hp": m_hp,
            "dmg_min": mob['dmg_min'], "dmg_max": mob['dmg_max'],
            "mob_pref": mob['row_pref'], "mob_skills": mob['skills'],
            "gold_min": mob.get('gold_min', 5), "gold_max": mob.get('gold_max', 15),
            "xp_reward": mob.get('xp_reward', 10), "ap": 3, "distance": "close"
        }
        update_user(user['user_id'], state='STATE_COMBAT', combat_data=combat_data)
        from handlers.combat import render_combat
        await render_combat(callback, user, combat_data, t("dungeon.sneak.fail", name=mob['name']))
    else:
        text = t("dungeon.sneak.success")
        await callback.message.edit_text(text, reply_markup=get_navigation_kb(d_data), parse_mode="Markdown")

@router.callback_query(F.data == "dungeon_sleep_attack")
async def sleep_attack(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    d_data = user.get('dungeon_data', {})
    node_id = d_data.get("current_node")
    node = d_data["nodes"][node_id]
    
    mob_id = node.get("mob_id", "temple_guard")
    mob = get_scaled_mob(mob_id, player_lvl=user.get('level', 1))
    m_max_hp = random.randint(mob['hp_min'], mob['hp_max'])
    m_hp = max(1, int(m_max_hp * 0.5)) 
    
    combat_data = {
        "enemy_id": mob['mob_id'], "enemy_name": mob['name'],
        "enemy_hp": m_hp, "enemy_max_hp": m_max_hp,
        "dmg_min": mob['dmg_min'], "dmg_max": mob['dmg_max'],
        "mob_pref": mob['row_pref'], "mob_skills": mob['skills'],
        "gold_min": mob.get('gold_min', 5), "gold_max": mob.get('gold_max', 15),
        "xp_reward": mob.get('xp_reward', 10), "ap": 3, "distance": "close"
    }
    update_user(user['user_id'], state='STATE_COMBAT', combat_data=combat_data)
    from handlers.combat import render_combat
    await render_combat(callback, user, combat_data, t("dungeon.sleep_attack", name=mob['name']))

@router.callback_query(F.data == "dungeon_pris_free")
async def pris_free(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    d_data = user.get('dungeon_data', {})
    
    if random.random() < 0.3:
        mob = get_scaled_mob("living_dead", player_lvl=user.get('level', 1))
        m_hp = random.randint(mob['hp_min'], mob['hp_max'])
        combat_data = {
            "enemy_id": mob['mob_id'], "enemy_name": t("dungeon.prisoner.ghoul_name"),
            "enemy_hp": m_hp, "enemy_max_hp": m_hp,
            "dmg_min": mob['dmg_min'], "dmg_max": mob['dmg_max'],
            "mob_pref": mob['row_pref'], "mob_skills": mob['skills'],
            "gold_min": 0, "gold_max": 5, "xp_reward": mob.get('xp_reward', 10),
            "ap": 3, "distance": "close"
        }
        update_user(user['user_id'], state='STATE_COMBAT', combat_data=combat_data)
        from handlers.combat import render_combat
        await render_combat(callback, user, combat_data, t("dungeon.prisoner.betrayal"))
    else:
        d_data['saved_prisoner'] = True
        update_user(user['user_id'], dungeon_data=d_data)
        text = t("dungeon.prisoner.freed")
        await callback.message.edit_text(text, reply_markup=get_navigation_kb(d_data), parse_mode="Markdown")

@router.callback_query(F.data == "dungeon_pris_kill")
async def pris_kill(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    d_data = user.get('dungeon_data', {})
    
    mat_id = get_random_material_id()
    qty = random.randint(1, 2)
    
    d_data.setdefault("gathered_materials", {})
    d_data["gathered_materials"][mat_id] = d_data["gathered_materials"].get(mat_id, 0) + qty
    
    inv = user.get('inventory', {})
    inv.setdefault("materials", {})[mat_id] = inv.setdefault("materials", {}).get(mat_id, 0) + qty
    
    update_user(user['user_id'], inventory=inv, dungeon_data=d_data)
    
    mat_name = get_item_name(mat_id)
    text = t("dungeon.prisoner.killed", item=mat_name, qty=qty)
    await callback.message.edit_text(text, reply_markup=get_navigation_kb(d_data), parse_mode="Markdown")

@router.callback_query(F.data == "dungeon_pris_leave")
async def pris_leave(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    d_data = user.get('dungeon_data', {})
    text = t("dungeon.prisoner.left")
    await callback.message.edit_text(text, reply_markup=get_navigation_kb(d_data), parse_mode="Markdown")

@router.callback_query(F.data.startswith("trap_dodge_"))
async def trap_dodge(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    d_data = user.get('dungeon_data', {})
    if not d_data.get('trap_active'):
        return await callback.answer(t("dungeon.trap.none"), show_alert=True)
        
    chosen_side = callback.data.replace("trap_dodge_", "")
    correct_side = d_data.get('trap_side')
    d_data['trap_active'] = False
    
    if chosen_side == correct_side:
        text = t("dungeon.trap.success")
        update_user(user['user_id'], dungeon_data=d_data)
        await callback.message.edit_text(text, reply_markup=get_navigation_kb(d_data), parse_mode="Markdown")
    else:
        dmg = int(user.get('max_hp', 100) * random.uniform(0.15, 0.25))
        user['hp'] -= dmg
        
        log_event(user['user_id'], 'dungeon', 'trap_damage', -dmg)
        
        if user['hp'] <= 0:
            track_stat(user['user_id'], 'deaths_count', 1)
            apply_death_penalty(user['user_id'], d_data)
            update_user(user['user_id'], state='STATE_TOWN', combat_data={}, dungeon_data={})
            from handlers.town import get_town_kb
            fresh = get_user(user['user_id']) or user
            return await callback.message.edit_text(t("dungeon.trap.death"), reply_markup=get_town_kb(fresh), parse_mode="Markdown")
        
        update_user(user['user_id'], hp=user['hp'], dungeon_data=d_data)
        text = t("dungeon.trap.damage", dmg=dmg)
        await callback.message.edit_text(text, reply_markup=get_navigation_kb(d_data), parse_mode="Markdown")

@router.callback_query(F.data.startswith("riddle_ans:"))
async def riddle_answer(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    d_data = user.get('dungeon_data', {})
    node = (d_data.get('nodes') or {}).get(d_data.get('current_node'), {})
    puzzle = node.get('puzzle', {})
    try:
        index = int(callback.data.split(':', 1)[1])
        options = puzzle['options']
        if index < 0 or index >= len(options):
            raise ValueError
    except (ValueError, KeyError, IndexError):
        return await callback.answer(t("dungeon.riddle.stale"), show_alert=True)
    if user.get('state') != 'STATE_DUNGEON' or node.get('type') != 'puzzle' or node.get('puzzle_solved'):
        return await callback.answer(t("dungeon.riddle.stale"), show_alert=True)
    if str(options[index]) == str(puzzle['correct']):
        return await riddle_correct(callback)
    return await riddle_wrong(callback)


async def riddle_correct(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    d_data = user.get('dungeon_data', {})
    node_id = d_data.get("current_node")
    node = (d_data.get("nodes") or {}).get(node_id)
    
    # Защита от многократного нажатия: награда выдаётся один раз на узел
    if not node or node.get("type") != "puzzle":
        return await callback.answer(t("dungeon.riddle.stale"), show_alert=True)
    if node.get("puzzle_solved"):
        return await callback.answer(t("dungeon.riddle.solved_already"), show_alert=True)
        
    node["puzzle_solved"] = True
    track_stat(user['user_id'], 'riddles_solved', 1)
    reward = random.randint(35, 75)
    user['gold'] += reward
    d_data.setdefault('gathered_gold', 0)
    d_data['gathered_gold'] += reward
    
    log_event(user['user_id'], 'economy', 'dungeon_puzzle_win', reward)
    
    update_user(user['user_id'], gold=user['gold'], dungeon_data=d_data)
    text = t("dungeon.riddle.correct", reward=reward)
    await callback.message.edit_text(text, reply_markup=get_navigation_kb(d_data), parse_mode="Markdown")

async def riddle_wrong(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    track_stat(user['user_id'], 'riddles_failed', 1)
    d_data = user.get('dungeon_data', {})
    d_data['nodes'][d_data['current_node']]['puzzle_solved'] = True
    trap_dmg = 15
    user['hp'] = max(1, user['hp'] - trap_dmg)
    
    log_event(user['user_id'], 'dungeon', 'puzzle_fail_damage', -trap_dmg)
    
    update_user(user['user_id'], hp=user['hp'], dungeon_data=d_data)
    text = t("dungeon.riddle.wrong", dmg=trap_dmg)
    await callback.message.edit_text(text, reply_markup=get_navigation_kb(d_data), parse_mode="Markdown")

