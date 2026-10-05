import json
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database import (
    get_connection, get_user, update_user, get_story_node, 
    get_story_choices, get_available_stories, get_unlocked_titles, get_clan, get_item_name
)
from handlers.town import get_town_kb
from handlers.combat import render_combat

router = Router()

# --- ЕДИНЫЙ МАРШРУТИЗАТОР ПЕРЕХОДОВ ---
async def navigate_to_node(callback: CallbackQuery, user: dict, next_node: str):
    if next_node == "town":
        update_user(user['user_id'], state='STATE_TOWN')
        return await callback.message.edit_text("Вы вернулись в лагерь.", reply_markup=get_town_kb(user))
        
    if next_node.startswith("complete_"):
        st_id = next_node.replace("complete_", "")
        progress = user.get('story_progress', {})
        if isinstance(progress, str): progress = json.loads(progress)
        
        if 'completed_stories' not in progress:
            progress['completed_stories'] = []
        if st_id not in progress['completed_stories']:
            progress['completed_stories'].append(st_id)
            
        if 'active_nodes' in progress and st_id in progress['active_nodes']:
            del progress['active_nodes'][st_id]
            
        update_user(user['user_id'], story_progress=progress, state='STATE_TOWN')
        return await callback.message.edit_text(
            "🎉 **Сюжет завершен!**\nТеперь вы можете переиграть его в меню, но сюжетные награды повторно не выдаются.", 
            reply_markup=get_town_kb(user), 
            parse_mode="Markdown"
        )

    await render_story_node(callback, user, next_node)


# --- МЕНЮ ВЫБОРА СЮЖЕТОВ ---
@router.callback_query(F.data == "town_story_enter")
async def story_menu(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    stories = get_available_stories(user['user_id'])
    
    if not stories:
        return await callback.answer("Пока нет доступных сюжетов.", show_alert=True)
        
    text = "📖 **Сюжетные архивы**\n\nВыберите историю для прохождения:"
    buttons = []
    
    progress = user.get('story_progress', {})
    if isinstance(progress, str): progress = json.loads(progress)
        
    active_nodes = progress.get('active_nodes', {})
    completed_stories = progress.get('completed_stories', [])
    
    for st in stories:
        if st['id'] in active_nodes:
            prefix = "▶️ ПРОДОЛЖИТЬ: "
        elif st['id'] in completed_stories:
            prefix = "🔄 ПЕРЕИГРАТЬ: "
        else:
            prefix = "📘 НАЧАТЬ: "
            
        buttons.append([InlineKeyboardButton(text=f"{prefix}{st['title']}", callback_data=f"story_select:{st['id']}")])
        
    buttons.append([InlineKeyboardButton(text="🔙 В лагерь", callback_data="town_back")])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")


# --- ВХОД В КОНКРЕТНУЮ ИСТОРИЮ ---
@router.callback_query(F.data.startswith("story_select:"))
async def enter_story_arc(callback: CallbackQuery):
    story_id = callback.data.split(":")[1]
    user = get_user(callback.from_user.id)
    
    progress = user.get('story_progress', {})
    if isinstance(progress, str): progress = json.loads(progress)
        
    active_nodes = progress.get('active_nodes', {})
    stories = get_available_stories(user['user_id'])
    selected_story = next((s for s in stories if s['id'] == story_id), None)
    
    if not selected_story:
        return await callback.answer("Сюжет не найден!", show_alert=True)
        
    if story_id in active_nodes:
        node_id = active_nodes[story_id]
    else:
        node_id = selected_story['start_node_id']
        
    await render_story_node(callback, user, node_id)


# --- ОТРИСОВКА УЗЛА И ДИНАМИЧЕСКИЕ ПРОВЕРКИ ---
async def render_story_node(callback: CallbackQuery, user: dict, node_id: str):
    node = get_story_node(node_id)
    if not node:
        return await callback.message.edit_text("Сюжетный узел не найден.", reply_markup=get_town_kb(user))
    
    progress = user.get('story_progress', {})
    if isinstance(progress, str): progress = json.loads(progress)
        
    if 'active_nodes' not in progress:
        progress['active_nodes'] = {}
    if 'flags' not in progress:
        progress['flags'] = {}

    story_id = None
    with get_connection() as conn:
        row = conn.cursor().execute("SELECT story_id FROM story_chapters WHERE id = ?", (node['chapter_id'],)).fetchone()
        if row: story_id = row[0]
            
    if story_id:
        progress['active_nodes'][story_id] = node_id
        
    update_user(user['user_id'], story_progress=progress, state='STATE_STORY')
    
    # === 1. ПОДГОТОВКА ДЛЯ ФОРМАТИРОВАНИЯ ===
    home_data = user.get('home_data', {})
    active_title = home_data.get('active_title', 'Новичок')
    active_medal = home_data.get('active_medal', 'Нет медалей')
    unlocked_titles = get_unlocked_titles(home_data)
    unlocked_medals = home_data.get('medals', [])
    
    clan_name = "Без клана"
    clan_level = 0
    if user.get('clan_id', 0) != 0:
        clan = get_clan(user['clan_id'])
        if clan:
            clan_name = clan['name']
            clan_level = clan['level']
            
    raw_text = node['text']
    replacements = {
        "{username}": user.get('username', 'Игрок'),
        "{level}": str(user.get('level', 1)),
        "{hp}": str(user.get('hp', 100)),
        "{max_hp}": str(user.get('max_hp', 100)),
        "{gold}": str(user.get('gold', 0)),
        "{title}": active_title,
        "{medal}": active_medal,
        "{clan}": clan_name
    }
    for k, v in replacements.items():
        raw_text = raw_text.replace(k, str(v))
    
    # === 2. ОБРАБОТКА ТИПОВ УЗЛОВ ===
    if node['node_type'] == 'combat':
        mob_id = node['extra_data'].get('mob_id', 'temple_guard')
        mob_modifier = float(node['extra_data'].get('mob_modifier', 1.0))
        
        from database import get_mob_by_name 
        mob = get_mob_by_name(mob_id) 
        
        # Динамический скейл характеристик по модификатору
        max_hp = max(1, int(mob['hp_max'] * mob_modifier))
        dmg_min = max(1, int(mob['dmg_min'] * mob_modifier))
        dmg_max = max(1, int(mob['dmg_max'] * mob_modifier))
        
        combat_data = {
            "is_story": True,
            "win_node": node['extra_data'].get('win_node'),
            "lose_node": node['extra_data'].get('lose_node'),
            "enemy_id": mob['mob_id'],
            "enemy_name": mob['name'],
            "enemy_hp": max_hp,
            "enemy_max_hp": max_hp,
            "dmg_min": dmg_min,
            "dmg_max": dmg_max,
            "mob_pref": mob['row_pref'],
            "mob_skills": mob['skills'],
            "mob_modifier": mob_modifier,
            "ap": 3,
            "distance": "close"
        }
        update_user(user['user_id'], state='STATE_COMBAT', combat_data=combat_data)
        return await render_combat(callback, user, combat_data, f"⚔️ {mob['name']} преграждает путь по сюжету!")

    elif node['node_type'] == 'reward':
        claimed = progress.setdefault('claimed_rewards', [])
        
        if node_id not in claimed:
            gold = node['extra_data'].get('gold', 0)
            xp = node['extra_data'].get('xp', 0)
            give_items = node['extra_data'].get('give_items', [])
            
            user['gold'] += gold
            user['xp'] = user.get('xp', 0) + xp
            
            lvl_msg = ""
            if xp > 0:
                while user['xp'] >= user.get('level', 1) * 100:
                    user['xp'] -= user.get('level', 1) * 100
                    user['level'] = user.get('level', 1) + 1
                    user['max_hp'] = user.get('max_hp', 100) + 15
                    user['hp'] = user['max_hp']
                    lvl_msg += f"\n🎉 **НОВЫЙ УРОВЕНЬ! ({user['level']})**"
            
            inv = user.get('inventory', {})
            items_msg = ""
            for item in give_items:
                i_id = item['id']
                i_type = item['type']
                i_qty = item.get('qty', 1)
                
                if i_type in ['weapon', 'armor']:
                    for _ in range(i_qty): inv.setdefault('backpack', []).append(i_id)
                elif i_type == 'potion':
                    for _ in range(i_qty): inv.setdefault('potions', []).append(i_id)
                elif i_type == 'material':
                    inv.setdefault('materials', {})[i_id] = inv.setdefault('materials', {}).get(i_id, 0) + i_qty
                    
                items_msg += f"\n✨ Получено: **{get_item_name(i_id)}** (x{i_qty})"

            claimed.append(node_id)
            progress['claimed_rewards'] = claimed
            update_user(
                user['user_id'], 
                gold=user['gold'], xp=user['xp'], level=user['level'], 
                hp=user['hp'], max_hp=user['max_hp'], inventory=inv, story_progress=progress
            )
            
            reward_text = ""
            if gold > 0: reward_text += f"\n💰 Получено: {gold} золота."
            if xp > 0: reward_text += f"\n🌟 Получено: {xp} XP."
            reward_text += lvl_msg + items_msg
            
            text = f"{raw_text}\n{reward_text}"
        else:
            text = f"{raw_text}\n\n*(Награда уже была получена при прошлом прохождении)*"
            
        next_node = node['extra_data'].get('next_node_id')
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Далее ➡️", callback_data=f"story_goto:{next_node}")]
        ])
        return await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

    # === 3. КНОПКИ И ПРОВЕРКИ УСЛОВИЙ ===
    choices = get_story_choices(node_id)
    buttons = []
    flags = progress.get('flags', {})
    inv = user.get('inventory', {})
    
    all_items = inv.get('backpack', []) + inv.get('potions', []) + list(inv.get('materials', {}).keys())

    for c in choices:
        can_click = True
        fail_reason = ""
        reqs = c['req_cond']
        
        if 'req_item' in reqs and reqs['req_item'] not in all_items:
            can_click, fail_reason = False, "❌ Нет предмета"
        elif 'req_flag' in reqs and reqs['req_flag'] not in flags:
            can_click, fail_reason = False, "❌ Не выполнено"
        elif 'req_level' in reqs and user.get('level', 1) < reqs['req_level']:
            can_click, fail_reason = False, f"❌ Ур. {reqs['req_level']}+"
        elif 'req_hp_full' in reqs and reqs['req_hp_full']:
            if user.get('hp', 0) < user.get('max_hp', 100):
                can_click, fail_reason = False, "❌ Нужно полное здоровье"
        elif 'req_hp_pct' in reqs:
            pct = user.get('hp', 0) / user.get('max_hp', 1)
            if pct < reqs['req_hp_pct']:
                can_click, fail_reason = False, f"❌ Здоровье < {int(reqs['req_hp_pct'] * 100)}%"
        elif 'req_title' in reqs and reqs['req_title'] not in unlocked_titles:
            can_click, fail_reason = False, "❌ Нет титула"
        elif 'req_medal' in reqs and reqs['req_medal'] not in unlocked_medals:
            can_click, fail_reason = False, "❌ Нет медали"
        elif 'req_clan' in reqs and reqs['req_clan'] and user.get('clan_id', 0) == 0:
            can_click, fail_reason = False, "❌ Нужен клан"
        elif 'req_clan_level' in reqs:
            if user.get('clan_id', 0) == 0:
                can_click, fail_reason = False, "❌ Нужен клан"
            elif clan_level < reqs['req_clan_level']:
                can_click, fail_reason = False, f"❌ Клан Ур. {reqs['req_clan_level']}+"

        if can_click:
            buttons.append([InlineKeyboardButton(text=c['text'], callback_data=f"story_choice:{c['id']}")])
        else:
            buttons.append([InlineKeyboardButton(text=f"{fail_reason} | {c['text']}", callback_data="story_locked")])
            
    buttons.append([InlineKeyboardButton(text="🏕 Выйти в лагерь", callback_data="town_back")])
    
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(raw_text, reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data == "story_locked")
async def handle_locked_choice(callback: CallbackQuery):
    await callback.answer("Требования для этого действия не выполнены!", show_alert=True)

@router.callback_query(F.data.startswith("story_goto:"))
async def handle_story_goto(callback: CallbackQuery):
    next_node = callback.data.split(":")[1]
    user = get_user(callback.from_user.id)
    await navigate_to_node(callback, user, next_node)

@router.callback_query(F.data.startswith("story_choice:"))
async def handle_story_choice(callback: CallbackQuery):
    choice_id = int(callback.data.split(":")[1])
    user = get_user(callback.from_user.id)
    
    with get_connection() as conn:
        row = conn.cursor().execute("SELECT action_data, next_node_id FROM story_choices WHERE id = ?", (choice_id,)).fetchone()
    
    action_data = json.loads(row[0])
    next_node = row[1]
    
    progress = user.get('story_progress', {})
    if isinstance(progress, str): progress = json.loads(progress)
    inv = user.get('inventory', {})
    need_update = False
    flags = progress.setdefault('flags', {})
    
    if 'take_item' in action_data:
        item = action_data['take_item']
        if item in inv.get('potions', []): inv['potions'].remove(item)
        elif item in inv.get('backpack', []): inv['backpack'].remove(item)
        elif item in inv.get('materials', {}): 
            inv['materials'][item] -= 1
            if inv['materials'][item] <= 0: del inv['materials'][item]
        need_update = True
        
    if 'set_flag' in action_data:
        flags[action_data['set_flag']] = True
        need_update = True
        
    if 'clear_flag' in action_data:
        flag_to_clear = action_data['clear_flag']
        if flag_to_clear in flags:
            del flags[flag_to_clear]
            need_update = True
            
    if 'give_gold' in action_data:
        user['gold'] += action_data['give_gold']
        need_update = True
        
    if 'give_items' in action_data:
        for item in action_data['give_items']:
            i_id = item['id']
            i_type = item['type']
            i_qty = item.get('qty', 1)
            
            if i_type in ['weapon', 'armor']:
                for _ in range(i_qty): inv.setdefault('backpack', []).append(i_id)
            elif i_type == 'potion':
                for _ in range(i_qty): inv.setdefault('potions', []).append(i_id)
            elif i_type == 'material':
                inv.setdefault('materials', {})[i_id] = inv.setdefault('materials', {}).get(i_id, 0) + i_qty
        need_update = True
        
    if need_update:
        progress['flags'] = flags
        update_user(user['user_id'], gold=user['gold'], inventory=inv, story_progress=progress)
        
    await navigate_to_node(callback, user, next_node)

