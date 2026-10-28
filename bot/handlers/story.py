import json
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database import (
    get_connection, get_user, update_user, get_story_node, get_item,
    get_story_choices, get_available_stories, get_unlocked_titles, get_clan, get_item_name,
    get_medal_display, award_medal, sync_medals, track_stat
)
from handlers.town import get_town_kb
from handlers.combat import render_combat
from data.story_names import choice_text, node_text, story_title
from i18n import t
from utils.titles import TITLE_NOVICE, get_title_display, normalize_title

router = Router()


def _requirements_error(user: dict, reqs: dict) -> str:
    """Проверяем все требования и при показе кнопки, и при её нажатии."""
    progress = user.get('story_progress', {})
    flags = progress.get('flags', {})
    inv = user.get('inventory', {})
    items = (inv.get('backpack', []) + inv.get('potions', []) + inv.get('artifacts', [])
             + [key for key, count in inv.get('materials', {}).items() if count > 0])
    names = set(items)
    for item_id in items:
        item = get_item(item_id)
        if item:
            names.add(item['name'])
    if reqs.get('req_item') and reqs['req_item'] not in names:
        return t('story.locked.no_item')
    if reqs.get('req_flag') and not flags.get(reqs['req_flag']):
        return t('story.locked.not_done')
    if any(not flags.get(flag) for flag in reqs.get('req_flags_all', [])):
        return t('story.locked.no_clues')
    if user.get('level', 1) < reqs.get('req_level', 0):
        return t('story.locked.level', level=reqs['req_level'])
    if user.get('gold', 0) < reqs.get('req_gold', 0):
        return t('story.locked.gold', gold=reqs['req_gold'])
    if reqs.get('req_hp_full') and user.get('hp', 0) < user.get('max_hp', 100):
        return t('story.locked.full_hp')
    if user.get('hp', 0) / max(1, user.get('max_hp', 1)) < reqs.get('req_hp_pct', 0):
        return t('story.locked.hp_pct', pct=int(reqs['req_hp_pct'] * 100))
    home = user.get('home_data', {})
    if reqs.get('req_title') and normalize_title(reqs['req_title']) not in get_unlocked_titles(home):
        return t('story.locked.no_title')
    if reqs.get('req_medal') and reqs['req_medal'] not in home.get('medals', []):
        return t('story.locked.no_medal')
    if reqs.get('req_clan') or reqs.get('req_clan_level'):
        clan = get_clan(user.get('clan_id', 0)) if user.get('clan_id') else None
        if not clan:
            return t('story.locked.need_clan')
        if clan['level'] < reqs.get('req_clan_level', 0):
            return t('story.locked.clan_level', level=reqs['req_clan_level'])
    return ''


def _apply_effects(user: dict, effects: dict) -> bool:
    """Применяет эффекты только если все списания можно выполнить."""
    inv = user.setdefault('inventory', {})
    gold_cost = effects.get('take_gold', 0)
    if gold_cost < 0 or user.get('gold', 0) < gold_cost:
        return False
    item = effects.get('take_item')
    found = None
    if item:
        for category in ('potions', 'backpack', 'artifacts'):
            for item_id in inv.get(category, []):
                data = get_item(item_id)
                if item_id == item or (data and data['name'] == item):
                    found = (category, item_id)
                    break
            if found:
                break
        if not found:
            for item_id, count in inv.get('materials', {}).items():
                data = get_item(item_id)
                if count > 0 and (item_id == item or (data and data['name'] == item)):
                    found = ('materials', item_id)
                    break
        if not found:
            return False
    if found:
        category, item_id = found
        if category == 'materials':
            inv[category][item_id] -= 1
            if inv[category][item_id] <= 0:
                del inv[category][item_id]
        else:
            inv[category].remove(item_id)
    user['gold'] = user.get('gold', 0) - gold_cost + effects.get('give_gold', 0)
    flags = user.setdefault('story_progress', {}).setdefault('flags', {})
    if effects.get('set_flag'):
        flags[effects['set_flag']] = True
    if effects.get('clear_flag'):
        flags.pop(effects['clear_flag'], None)
    hp = user.get('hp', 1)
    max_hp = user.get('max_hp', 100)
    hp -= int(max_hp * effects.get('take_hp_pct', 0)) + effects.get('take_hp', 0)
    hp += int(max_hp * effects.get('heal_pct', 0))
    user['hp'] = max(1, min(max_hp, hp))
    for entry in effects.get('give_items', []):
        item_id, kind, qty = entry['id'], entry['type'], entry.get('qty', 1)
        if kind in ('weapon', 'armor'):
            inv.setdefault('backpack', []).extend([item_id] * qty)
        elif kind in ('artifact', 'potion'):
            inv.setdefault('artifacts' if kind == 'artifact' else 'potions', []).extend([item_id] * qty)
        elif kind == 'material':
            materials = inv.setdefault('materials', {})
            materials[item_id] = materials.get(item_id, 0) + qty
    return True


def _current_story_node(user: dict):
    progress = user.get('story_progress', {})
    story_id = progress.get('current_story')
    return story_id, progress.get('active_nodes', {}).get(story_id)

async def navigate_to_node(callback: CallbackQuery, user: dict, next_node: str):
    if next_node == "town":
        user.get('story_progress', {}).pop('current_story', None)
        update_user(user['user_id'], state='STATE_TOWN', story_progress=user['story_progress'])
        return await callback.message.edit_text(t("story.returned_town"), reply_markup=get_town_kb(user))
        
    if next_node.startswith("complete_"):
        st_id = next_node.replace("complete_", "")
        progress = user.get('story_progress', {})
        if isinstance(progress, str): progress = json.loads(progress)
        
        if 'completed_stories' not in progress:
            progress['completed_stories'] = []
        newly_completed = st_id not in progress['completed_stories']
        if newly_completed:
            progress['completed_stories'].append(st_id)

        if st_id == 'arc2_ice_prison':
            progress.setdefault('flags', {})['a2_arc2_complete'] = True
        progress.pop('current_story', None)
            
        if 'active_nodes' in progress and st_id in progress['active_nodes']:
            del progress['active_nodes'][st_id]
            
        update_user(user['user_id'], story_progress=progress, state='STATE_TOWN')

        medal_msg = ""
        if newly_completed:
            track_stat(user['user_id'], 'stories_completed', 1)
            story_medal = f"story_{st_id}"
            if award_medal(user['user_id'], story_medal):
                medal_msg = t("story.medal_received", medal=get_medal_display(story_medal))
            sync_medals(user['user_id'])

        return await callback.message.edit_text(
            t("story.completed") + medal_msg,
            reply_markup=get_town_kb(user), 
            parse_mode="Markdown"
        )

    await render_story_node(callback, user, next_node)

@router.callback_query(F.data == "town_story_enter")
async def story_menu(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    stories = get_available_stories(user['user_id'])
    
    if not stories:
        return await callback.answer(t("story.no_stories"), show_alert=True)
        
    text = t("story.menu_title")
    buttons = []
    
    progress = user.get('story_progress', {})
    if isinstance(progress, str): progress = json.loads(progress)
        
    active_nodes = progress.get('active_nodes', {})
    completed_stories = progress.get('completed_stories', [])
    
    for st in stories:
        if st['id'] in active_nodes:
            prefix = t("story.continue")
        elif st['id'] in completed_stories:
            prefix = t("story.restart")
        else:
            prefix = t("story.start")
            
        buttons.append([InlineKeyboardButton(
            text=f"{prefix}{story_title(st['id'], st['title'])}",
            callback_data=f"story_select:{st['id']}",
        )])
        
    buttons.append([InlineKeyboardButton(text=t("common.to_town"), callback_data="town_back")])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

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
        return await callback.answer(t("story.not_found"), show_alert=True)
        
    if story_id in active_nodes:
        node_id = active_nodes[story_id]
    else:
        node_id = selected_story['start_node_id']
        
    await navigate_to_node(callback, user, node_id)

async def render_story_node(callback: CallbackQuery, user: dict, node_id: str):
    # Combat handlers may have just persisted HP and state using a newer value.
    user = get_user(user['user_id']) or user
    node = get_story_node(node_id)
    if not node:
        return await callback.message.edit_text(t("story.node_not_found"), reply_markup=get_town_kb(user))
    
    progress = user.get('story_progress', {})
    if isinstance(progress, str): progress = json.loads(progress)
        
    if 'active_nodes' not in progress:
        progress['active_nodes'] = {}
    if 'flags' not in progress:
        progress['flags'] = {}
    # Старые игроки уже могли завершить II арку до появления этого флага.
    if 'arc2_ice_prison' in progress.get('completed_stories', []):
        progress['flags']['a2_arc2_complete'] = True

    story_id = None
    with get_connection() as conn:
        row = conn.cursor().execute("SELECT story_id FROM story_chapters WHERE id = ?", (node['chapter_id'],)).fetchone()
        if row: story_id = row[0]
            
    if story_id:
        progress['active_nodes'][story_id] = node_id
        progress['current_story'] = story_id

    # Эффекты текста применяются один раз, чтобы повторный показ не выдавал
    # бесконечные предметы и не наносил повторный урон.
    if node['node_type'] == 'text':
        effects = {k: v for k, v in node['extra_data'].items() if k != 'next_node_id'}
        applied = progress.setdefault('applied_node_effects', [])
        if effects and node_id not in applied:
            if _apply_effects(user, effects):
                applied.append(node_id)
            else:
                return await callback.answer(t('story.requirements_failed'), show_alert=True)

    update_user(user['user_id'], story_progress=progress, state='STATE_STORY',
                hp=user['hp'], gold=user['gold'], inventory=user['inventory'])
    
    home_data = user.get('home_data', {})
    active_title_id = home_data.get('active_title') or TITLE_NOVICE
    active_medal_id = home_data.get('active_medal')
    active_title = get_title_display(active_title_id)
    active_medal = get_medal_display(active_medal_id) if active_medal_id else t("home.no_medal")
    unlocked_titles = get_unlocked_titles(home_data)
    unlocked_medals = home_data.get('medals', [])
    
    clan_name = t("story.no_clan")
    clan_level = 0
    if user.get('clan_id', 0) != 0:
        clan = get_clan(user['clan_id'])
        if clan:
            clan_name = clan['name']
            clan_level = clan['level']
            
    raw_text = node_text(node_id, node['text'])
    replacements = {
        "{username}": user.get('username') or t("story.default_player"),
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
    
    if node['node_type'] == 'combat':
        mob_id = node['extra_data'].get('mob_id', 'temple_guard')
        mob_modifier = float(node['extra_data'].get('mob_modifier', 1.0))
        
        from database import get_mob_by_name 
        mob = get_mob_by_name(mob_id) 
        
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
        return await render_combat(
            callback, user, combat_data,
            t("story.combat_intro", name=mob['name']),
        )

    elif node['node_type'] == 'reward':
        claimed = progress.setdefault('claimed_rewards', [])
        
        if node_id not in claimed:
            gold = node['extra_data'].get('gold', 0)
            xp = node['extra_data'].get('xp', 0)
            give_items = node['extra_data'].get('give_items', [])
            
            user['gold'] += gold
            user['xp'] = user.get('xp', 0) + xp
            if node['extra_data'].get('take_hp_pct'):
                user['hp'] = max(1, user['hp'] - int(user['max_hp'] * node['extra_data']['take_hp_pct']))
            
            lvl_msg = ""
            if xp > 0:
                while user['xp'] >= user.get('level', 1) * 100:
                    user['xp'] -= user.get('level', 1) * 100
                    user['level'] = user.get('level', 1) + 1
                    user['max_hp'] = user.get('max_hp', 100) + 15
                    user['hp'] = user['max_hp']
                    lvl_msg += t("story.new_level", level=user['level'])
            
            inv = user.get('inventory', {})
            items_msg = ""
            for item in give_items:
                i_id = item['id']
                i_type = item['type']
                i_qty = item.get('qty', 1)
                
                if i_type in ['weapon', 'armor']:
                    for _ in range(i_qty): inv.setdefault('backpack', []).append(i_id)
                elif i_type == 'artifact':
                    for _ in range(i_qty): inv.setdefault('artifacts', []).append(i_id)
                elif i_type == 'potion':
                    for _ in range(i_qty): inv.setdefault('potions', []).append(i_id)
                elif i_type == 'material':
                    inv.setdefault('materials', {})[i_id] = inv.setdefault('materials', {}).get(i_id, 0) + i_qty
                    
                items_msg += t("story.item_received", item=get_item_name(i_id), qty=i_qty)

            claimed.append(node_id)
            progress['claimed_rewards'] = claimed
            update_user(
                user['user_id'], 
                gold=user['gold'], xp=user['xp'], level=user['level'], 
                hp=user['hp'], max_hp=user['max_hp'], inventory=inv, story_progress=progress
            )
            sync_medals(user['user_id'])
            
            reward_text = ""
            if gold > 0: reward_text += t("story.reward_gold", gold=gold)
            if xp > 0: reward_text += t("story.reward_xp", xp=xp)
            reward_text += lvl_msg + items_msg
            
            text = f"{raw_text}\n{reward_text}"
        else:
            text = raw_text + t("story.reward_claimed")
            
        next_node = node['extra_data'].get('next_node_id')
        choices = get_story_choices(node_id)
        buttons = [[InlineKeyboardButton(text=choice_text(node_id, c['text']), callback_data=f"story_choice:{c['id']}")]
                   for c in choices if not _requirements_error(user, c['req_cond'])]
        if next_node:
            buttons.append([InlineKeyboardButton(text=t("story.next"), callback_data=f"story_goto:{next_node}")])
        buttons.append([InlineKeyboardButton(text=t("story.exit_town"), callback_data="town_back")])
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        return await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

    choices = get_story_choices(node_id)
    buttons = []
    for c in choices:
        fail_reason = _requirements_error(user, c['req_cond'])
        choice_label = choice_text(node_id, c['text'])
        if not fail_reason:
            buttons.append([InlineKeyboardButton(text=choice_label, callback_data=f"story_choice:{c['id']}")])
        else:
            buttons.append([InlineKeyboardButton(
                text=t("story.locked_format", reason=fail_reason, text=choice_label),
                callback_data="story_locked",
            )])

    buttons.append([InlineKeyboardButton(text=t("story.exit_town"), callback_data="town_back")])
    
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(raw_text, reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data == "story_locked")
async def handle_locked_choice(callback: CallbackQuery):
    await callback.answer(t("story.requirements_failed"), show_alert=True)

def _valid_target(story_id: str, target: str) -> bool:
    if target == 'town' or target == f'complete_{story_id}':
        return True
    with get_connection() as conn:
        row = conn.execute(
            "SELECT c.story_id FROM story_nodes n JOIN story_chapters c ON c.id=n.chapter_id WHERE n.id=?",
            (target,),
        ).fetchone()
    return bool(row and row[0] == story_id)


@router.callback_query(F.data.startswith("story_goto:"))
async def handle_story_goto(callback: CallbackQuery):
    next_node = callback.data.split(":", 1)[1]
    user = get_user(callback.from_user.id)
    story_id, current = _current_story_node(user)
    node = get_story_node(current) if current else {}
    if (user.get('state') != 'STATE_STORY' or not story_id or
            node.get('node_type') != 'reward' or
            node.get('extra_data', {}).get('next_node_id') != next_node or
            not _valid_target(story_id, next_node)):
        return await callback.answer(t("story.requirements_failed"), show_alert=True)
    user['story_progress']['active_nodes'][story_id] = next_node
    update_user(user['user_id'], story_progress=user['story_progress'])
    await navigate_to_node(callback, user, next_node)


@router.callback_query(F.data.startswith("story_choice:"))
async def handle_story_choice(callback: CallbackQuery):
    try:
        choice_id = int(callback.data.split(":", 1)[1])
    except (ValueError, IndexError):
        return await callback.answer(t("story.requirements_failed"), show_alert=True)
    user = get_user(callback.from_user.id)
    story_id, current = _current_story_node(user)
    with get_connection() as conn:
        row = conn.execute(
            "SELECT node_id, req_cond, action_data, next_node_id FROM story_choices WHERE id = ?",
            (choice_id,),
        ).fetchone()
    if not row or not story_id or user.get('state') != 'STATE_STORY' or row[0] != current:
        return await callback.answer(t("story.requirements_failed"), show_alert=True)
    reqs, effects, next_node = json.loads(row[1]), json.loads(row[2]), row[3]
    if _requirements_error(user, reqs) or not _valid_target(story_id, next_node):
        return await callback.answer(t("story.requirements_failed"), show_alert=True)

    progress = user['story_progress']
    claimed = progress.setdefault('claimed_choice_rewards', [])
    already_completed_arc1 = (choice_id == 223 and
                              'arc1_adventurer' in progress.get('completed_stories', []))
    if str(choice_id) in claimed or already_completed_arc1:
        effects.pop('give_gold', None)
        effects.pop('give_items', None)
    elif effects.get('give_gold') or effects.get('give_items'):
        claimed.append(str(choice_id))
    if not _apply_effects(user, effects):
        return await callback.answer(t("story.requirements_failed"), show_alert=True)
    # Persist the transition with the effects before yielding to Telegram.
    progress['active_nodes'][story_id] = next_node
    update_user(user['user_id'], hp=user['hp'], gold=user['gold'],
                inventory=user['inventory'], story_progress=progress)
    await navigate_to_node(callback, user, next_node)
