import random
import datetime
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database import get_user, update_user, get_today_dungeon, get_mob_by_name, get_item, get_item_name, get_loot_table, apply_flee_penalty, apply_death_penalty
from utils.generators import generate_emoji_puzzle, generate_dungeon_graph

router = Router()

def get_navigation_kb(dungeon_data):
    current_node_id = dungeon_data["current_node"]
    graph = dungeon_data["nodes"]
    current_node = graph[current_node_id]
    buttons = []
    row = []
    type_icons = {"combat": "⚔️ Враг", "puzzle": "🧩 Загадка", "treasure": "💰 Тайник", "campfire": "🏕️ Привал", "boss": "👹 БОСС", "empty": "🕸 Пустота"}
    
    for next_id in current_node["next"]:
        next_room = graph[next_id]
        icon = type_icons.get(next_room["type"], "🚪 Дверь")
        row.append(InlineKeyboardButton(text=icon, callback_data=f"dung_go_{next_id}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row: buttons.append(row)
    buttons.append([InlineKeyboardButton(text="🏃‍♂️ Сбежать (штраф)", callback_data="dungeon_flee")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_dungeon_config(dungeon_type):
    if dungeon_type == "event": return get_today_dungeon()
    return {"name": "🗿 Руины Забытых Богов", "desc": "Скрытый под землей древний храм.", "mobs": ["temple_guard", "living_idol", "poison_slime"], "boss_id": "time_keeper", "mob_modifier": 1.0}

@router.callback_query(F.data == "town_raids")
async def show_raids_menu(callback: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚶 Соло Рейд", callback_data="dungeon_start_solo")],
        [InlineKeyboardButton(text="📅 Ивентовый Данж", callback_data="dungeon_start_event")],
        [InlineKeyboardButton(text="🔙 В лагерь", callback_data="town_back")]
    ])
    await callback.message.edit_text("⚔️ **Доска Рейдов**\nВыберите экспедицию.", reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data.startswith("dungeon_start_"))
async def enter_dungeon(callback: CallbackQuery):
    dungeon_type = callback.data.split("_")[-1]
    dungeon_data = generate_dungeon_graph(dungeon_type)
    dungeon_data["gathered_gold"] = 0
    dungeon_data["gathered_materials"] = {}
    dungeon_data["gathered_equipment"] = []
    
    update_user(callback.from_user.id, state='STATE_DUNGEON', dungeon_data=dungeon_data)
    config = get_dungeon_config(dungeon_type)
    await callback.message.edit_text(f"**{config['name']}**\n{config['desc']}\n\nВы у входа. Изучите карту.", reply_markup=get_navigation_kb(dungeon_data), parse_mode="Markdown")

@router.callback_query(F.data.startswith("dung_go_"))
async def next_room(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    if user['state'] != 'STATE_DUNGEON': return await callback.answer("Вы не в подземелье!", show_alert=True)
    next_node_id = callback.data.replace("dung_go_", "")
    dungeon_data = user['dungeon_data']
    dungeon_data["current_node"] = next_node_id
    current_room = dungeon_data["nodes"][next_node_id]
    event = current_room["type"]
    dungeon_config = get_dungeon_config(dungeon_data.get("dungeon_type", "solo"))
    
    if event in ["combat", "boss"]:
        if event == "boss":
            mob_stats = get_mob_by_name(dungeon_config.get('boss_id', 'time_keeper'))
            modifier = dungeon_config.get('mob_modifier', 1.0) * 1.5
        else:
            mob_stats = get_mob_by_name(random.choice(dungeon_config['mobs']))
            modifier = dungeon_config.get('mob_modifier', 1.0)
            
        enemy_hp = int(random.randint(mob_stats['hp_min'], mob_stats['hp_max']) * modifier)
        start_dist = "close" if mob_stats['row_pref'] == "front" else "far"
            
        combat_data = {
            "enemy_name": mob_stats['name'], "enemy_hp": enemy_hp, "enemy_max_hp": enemy_hp, 
            "dmg_min": int(mob_stats['dmg_min'] * modifier), "dmg_max": int(mob_stats['dmg_max'] * modifier), 
            "gold_min": mob_stats.get('gold_min', 5), "gold_max": mob_stats.get('gold_max', 15), "xp_reward": mob_stats.get('xp_reward', 10),
            "mob_modifier": modifier,
            "ap": 3, "distance": start_dist, "mob_pref": mob_stats['row_pref'], "mob_skills": mob_stats.get('skills', {})
        }
        update_user(user['user_id'], state='STATE_COMBAT', combat_data=combat_data, dungeon_data=dungeon_data)
        from handlers.combat import render_combat
        await render_combat(callback, user, combat_data, f"Впереди {mob_stats['name']}!")
        
    elif event == "treasure":
        location_id = f"event_{datetime.datetime.today().weekday()}" if dungeon_data.get('dungeon_type', 'solo') == "event" else "solo"
        gold_found = random.randint(20, 50)
        user['gold'] += gold_found
        dungeon_data.setdefault("gathered_gold", 0)
        dungeon_data["gathered_gold"] += gold_found
        msg = f"💰 **Тайник!** Найдено {gold_found} золота."
        inv = user['inventory']
        
        for loot in get_loot_table(location_id):
            if random.random() <= min(1.0, loot['chance'] * 2.0):
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
                msg += f"\n📦 Внутри: **{get_item_name(loot['item_id'])}** (x{qty})"
        update_user(user['user_id'], gold=user['gold'], inventory=inv, dungeon_data=dungeon_data)
        await callback.message.edit_text(f"{msg}\n\nДальше...", reply_markup=get_navigation_kb(dungeon_data), parse_mode="Markdown")
        
    elif event == "puzzle":
        puzzle = generate_emoji_puzzle()
        update_user(user['user_id'], state='STATE_PUZZLE', combat_data={"correct": puzzle["correct"]}, dungeon_data=dungeon_data)
        buttons = [[InlineKeyboardButton(text=str(opt), callback_data=f"puzzle_ans_{opt}")] for opt in puzzle["options"]]
        buttons.append([InlineKeyboardButton(text="💥 Разбить дверь (-20% ХП)", callback_data="puzzle_smash")])
        await callback.message.edit_text(puzzle["text"], reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")
        
    elif event == "campfire":
        heal = int(user['max_hp'] * 0.3)
        new_hp = min(user['max_hp'], user['hp'] + heal)
        update_user(user['user_id'], hp=new_hp, dungeon_data=dungeon_data)
        await callback.message.edit_text(f"🏕️ **Привал.** +{heal} ХП.\n\nВпереди слышен рев Босса. Готовы?", reply_markup=get_navigation_kb(dungeon_data), parse_mode="Markdown")
        
    elif event == "empty":
        update_user(user['user_id'], dungeon_data=dungeon_data)
        await callback.message.edit_text("🕸 **Пустая комната.**\n\nСмотрим карту...", reply_markup=get_navigation_kb(dungeon_data), parse_mode="Markdown")

@router.callback_query(F.data.startswith("puzzle_"))
async def solve_puzzle(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    if user['state'] != 'STATE_PUZZLE': return await callback.answer("Ошибка стейта!", show_alert=True)
    action = callback.data.replace("puzzle_", "")
    dungeon_data = user['dungeon_data']
    
    if action == "smash":
        dmg = int(user['max_hp'] * 0.20)
        if user['hp'] - dmg <= 0:
            apply_death_penalty(user['user_id'], dungeon_data)
            update_user(user['user_id'], state='STATE_TOWN', combat_data={}, dungeon_data={})
            from handlers.town import get_town_kb
            return await callback.message.edit_text("☠️ Шип ловушки убил вас... Все собранные вещи утеряны.", reply_markup=get_town_kb(), parse_mode="Markdown")
        update_user(user['user_id'], state='STATE_DUNGEON', hp=user['hp']-dmg, combat_data={})
        await callback.message.edit_text(f"💥 Вы выбили дверь! Урон: {dmg}.\nСмотрим карту...", reply_markup=get_navigation_kb(dungeon_data), parse_mode="Markdown")
            
    elif action.startswith("ans_"):
        if int(action.split("_")[1]) == user.get('combat_data', {}).get("correct"):
            heal = int(user['max_hp'] * 0.15)
            update_user(user['user_id'], state='STATE_DUNGEON', hp=min(user['max_hp'], user['hp'] + heal), combat_data={})
            await callback.message.edit_text(f"✨ **Верно!** +{heal} ХП.\nСмотрим карту...", reply_markup=get_navigation_kb(dungeon_data), parse_mode="Markdown")
        else:
            dmg = int(user['max_hp'] * 0.30)
            if user['hp'] - dmg <= 0:
                apply_death_penalty(user['user_id'], dungeon_data)
                update_user(user['user_id'], state='STATE_TOWN', combat_data={}, dungeon_data={})
                from handlers.town import get_town_kb
                return await callback.message.edit_text("☠️ Адское пламя сожгло вас... Все собранные вещи утеряны.", reply_markup=get_town_kb(), parse_mode="Markdown")
            update_user(user['user_id'], state='STATE_DUNGEON', hp=user['hp']-dmg, combat_data={})
            await callback.message.edit_text(f"❌ **Ошибка!** Урон: {dmg}!\nСмотрим карту...", reply_markup=get_navigation_kb(dungeon_data), parse_mode="Markdown")

# НОВАЯ СИСТЕМА ПОДТВЕРЖДЕНИЯ ПОБЕГА
@router.callback_query(F.data == "dungeon_flee")
async def flee_dungeon(callback: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏃‍♂️ ДА, СБЕЖАТЬ", callback_data="dungeon_flee_confirm")],
        [InlineKeyboardButton(text="🗺️ НЕТ, ИДЕМ ДАЛЬШЕ", callback_data="dungeon_flee_cancel")]
    ])
    await callback.message.edit_text("⚠️ **Вы уверены?**\nПри побеге вы потеряете часть золота и материалов из этого рейда!", reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data == "dungeon_flee_confirm")
async def flee_dungeon_confirm(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    lost_gold, lost_mats = apply_flee_penalty(user['user_id'], user.get('dungeon_data', {}))
    update_user(user['user_id'], state='STATE_TOWN', combat_data={}, dungeon_data={})
    from handlers.town import get_town_kb
    mats_str = f" и {', '.join(lost_mats)}" if lost_mats else ""
    await callback.message.edit_text(f"🏃‍♂️ Вы сбежали! Потеряно из рейда: **{lost_gold} золота**{mats_str}.", reply_markup=get_town_kb(), parse_mode="Markdown")

@router.callback_query(F.data == "dungeon_flee_cancel")
async def flee_dungeon_cancel(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    dungeon_data = user.get('dungeon_data', {})
    await callback.message.edit_text("Вы передумали бежать.\n\nКуда дальше?", reply_markup=get_navigation_kb(dungeon_data), parse_mode="Markdown")
