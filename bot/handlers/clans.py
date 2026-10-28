import json
import datetime
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from database import (
    get_user, update_user, get_clan, update_clan, 
    get_clan_by_name, get_all_clans_ranked, get_clan_members,
    get_connection, get_clan_creation_requirements, get_item_name,
    get_clan_merchant_deals, get_item_price, get_item, get_all_home_skins,
    get_medal_display, log_event  # <--- Добавлен импорт логгера
)
from i18n import t
from utils.titles import TITLE_NOVICE, get_title_display

router = Router()

class ClanStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_gold = State()
    waiting_for_gems = State()
    waiting_for_withdraw_gold = State()
    waiting_for_withdraw_gems = State()
    waiting_for_banner = State()
    waiting_for_chat_msg = State()

# --- ПРАВА ДОСТУПА ---
ROLE_RANK = {'thrall': 1, 'lindeman': 2, 'hedwing': 3}

def get_actor_clan(user: dict):
    """Возвращает клан игрока или None. «Висящий» clan_id без клана лечится."""
    clan_id = user.get('clan_id', 0)
    if not clan_id:
        return None
    clan = get_clan(clan_id)
    if not clan:
        update_user(user['user_id'], clan_id=0, clan_role='thrall')
        return None
    return clan

def role_at_least(user: dict, min_role: str) -> bool:
    return ROLE_RANK.get(user.get('clan_role'), 0) >= ROLE_RANK[min_role]

def can_manage(actor: dict, target: dict) -> bool:
    """Офицер управляет только рядовыми, глава — офицерами и рядовыми."""
    return ROLE_RANK.get(actor.get('clan_role'), 0) > ROLE_RANK.get(target.get('clan_role'), 0)


def format_clan_requirements_text(reqs: dict, short: bool = False) -> str:
    parts = []
    if reqs["min_level"] > 0:
        parts.append(
            t("clan.req.level_short", level=reqs['min_level']) if short
            else t("clan.req.level", level=reqs['min_level'])
        )
    if reqs["cost_gems"] > 0:
        parts.append(f"{reqs['cost_gems']} 💎")
    if reqs["cost_gold"] > 0:
        parts.append(f"{reqs['cost_gold']} 🪙")
        
    if not parts:
        return t("clan.req.free")
    return " + ".join(parts) if short else ", ".join(parts)

def get_clan_main_kb(user: dict):
    buttons = []
    clan_id = user.get('clan_id', 0)
    if clan_id == 0:
        reqs = get_clan_creation_requirements()
        cost_badge = format_clan_requirements_text(reqs, short=True)
        btn_label = (
            t("clan.btn.create_cost", cost=cost_badge)
            if cost_badge != t("clan.req.free")
            else t("clan.btn.create")
        )
        
        buttons.append([InlineKeyboardButton(text=t("clan.btn.search"), callback_data="clan_search_list")])
        buttons.append([InlineKeyboardButton(text=btn_label, callback_data="clan_create_start")])
    else:
        buttons.append([InlineKeyboardButton(text=t("clan.btn.my"), callback_data="clan_my_info")])
        buttons.append([InlineKeyboardButton(text=t("clan.btn.search"), callback_data="clan_search_list")])
        buttons.append([InlineKeyboardButton(text=t("clan.btn.vault"), callback_data="clan_vault_view")])
    buttons.append([InlineKeyboardButton(text=t("common.to_town"), callback_data="town_back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# --- ГЛАВНЫЙ ВХОД В КЛАНОВЫЙ ЗАЛ ---
@router.callback_query(F.data == "clan_main")
async def clan_main_menu(callback: CallbackQuery, state: FSMContext):
    if state: await state.clear()
    user = get_user(callback.from_user.id)
    clan_id = user.get('clan_id', 0)
    
    text = t("clan.main.title")
    if clan_id != 0:
        clan = get_clan(clan_id)
        banner = f"{clan.get('banner', '')} " if clan and clan.get('banner') else ""
        c_name = clan['name'] if clan else t("clan.main.unknown")
        text += t("clan.main.member", banner=banner, name=c_name)
    else:
        reqs = get_clan_creation_requirements()
        reqs_str = format_clan_requirements_text(reqs, short=False)
        text += t("clan.main.solo")
        if reqs_str != t("clan.req.free"):
            text += t("clan.main.cost", reqs=reqs_str)
        
    await callback.message.edit_text(text, reply_markup=get_clan_main_kb(user), parse_mode="Markdown")

# --- СОЗДАНИЕ КЛАНА ---
@router.callback_query(F.data == "clan_create_start")
async def clan_create_start(callback: CallbackQuery, state: FSMContext):
    user = get_user(callback.from_user.id)
    if user.get('clan_id', 0) != 0:
        return await callback.answer(t("clan.create.already"), show_alert=True)
    
    reqs = get_clan_creation_requirements()
    user_lvl = user.get('level', 1)
    user_gems = user.get('gems', 0)
    user_gold = user.get('gold', 0)
    
    if reqs["min_level"] > 0 and user_lvl < reqs["min_level"]:
        return await callback.answer(t("clan.create.level_fail", level=reqs['min_level']), show_alert=True)
    if reqs["cost_gems"] > 0 and user_gems < reqs["cost_gems"]:
        return await callback.answer(t("clan.create.gems_fail", gems=reqs['cost_gems']), show_alert=True)
    if reqs["cost_gold"] > 0 and user_gold < reqs["cost_gold"]:
        return await callback.answer(t("clan.create.gold_fail", gold=reqs['cost_gold']), show_alert=True)
        
    req_lines = []
    if reqs["min_level"] > 0: req_lines.append(t("clan.create.req_level", level=reqs['min_level']))
    if reqs["cost_gems"] > 0: req_lines.append(t("clan.create.req_gems", gems=reqs['cost_gems']))
    if reqs["cost_gold"] > 0: req_lines.append(t("clan.create.req_gold", gold=reqs['cost_gold']))
    req_display = "\n".join(req_lines) if req_lines else t("clan.create.req_none")

    await state.set_state(ClanStates.waiting_for_name)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t("common.cancel"), callback_data="clan_main")]])
    await callback.message.edit_text(
        t("clan.create.title", reqs=req_display), 
        reply_markup=kb, parse_mode="Markdown"
    )

@router.message(ClanStates.waiting_for_name)
async def clan_create_name_input(message: Message, state: FSMContext):
    if not message.text:
        return await message.answer(t("clan.create.name_text"))
    name = message.text.strip()
    user = get_user(message.from_user.id)
    reqs = get_clan_creation_requirements()
    
    if len(name) < 3 or len(name) > 20:
        return await message.answer(t("clan.create.name_len"))
    if get_clan_by_name(name):
        return await message.answer(t("clan.create.name_exists"))
        
    if reqs["min_level"] > 0 and user.get('level', 1) < reqs["min_level"]: return await message.answer(t("clan.create.level_short"))
    if reqs["cost_gems"] > 0 and user.get('gems', 0) < reqs["cost_gems"]: return await message.answer(t("clan.create.gems_short"))
    if reqs["cost_gold"] > 0 and user.get('gold', 0) < reqs["cost_gold"]: return await message.answer(t("clan.create.gold_short"))
        
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("INSERT INTO clans (name, leader_id, level, treasury, weekly_raids, total_raids, join_requests, clan_vault) VALUES (?, ?, 1, 0, 0, 0, '[]', '{\"gems\": 0, \"items\": {}}')", (name, user['user_id']))
        new_clan_id = cur.lastrowid
        conn.commit()
        
    new_gems = max(0, user.get('gems', 0) - reqs["cost_gems"])
    new_gold = max(0, user.get('gold', 0) - reqs["cost_gold"])
    update_user(user['user_id'], gems=new_gems, gold=new_gold, clan_id=new_clan_id, clan_role='hedwing')
    
    # ЛОГ: Создание клана (потеря золота/кристаллов на основание)
    log_event(user['user_id'], 'clan', 'create_clan', 0, {
        'clan_id': new_clan_id,
        'clan_name': name,
        'cost_gems': reqs["cost_gems"],
        'cost_gold': reqs["cost_gold"]
    })
    
    await state.clear()
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("clan.btn.my_clan"), callback_data="clan_my_info")],
        [InlineKeyboardButton(text=t("common.to_town"), callback_data="town_back")]
    ])
    msg = await message.answer(t("clan.create.success", name=name), reply_markup=kb, parse_mode="Markdown")
    update_user(user['user_id'], last_msg_id=msg.message_id)

# --- МОЙ КЛАН (ПРОФИЛЬ) ---
@router.callback_query(F.data == "clan_my_info")
async def show_my_clan(callback: CallbackQuery, state: FSMContext):
    if state: await state.clear()
    user = get_user(callback.from_user.id)
    clan_id = user.get('clan_id', 0)
    if clan_id == 0:
        return await callback.answer(t("clan.profile.not_member"), show_alert=True)
        
    clan = get_clan(clan_id)
    if not clan:
        update_user(user['user_id'], clan_id=0, clan_role='thrall')
        return await callback.answer(t("clan.profile.disbanded"), show_alert=True)
        
    members = get_clan_members(clan_id)
    max_m = 5 + clan['level'] * 5
    is_leader = (user['user_id'] == clan['leader_id'])
    
    role_titles = {
        'hedwing': t("clan.role.leader"),
        'lindeman': t("clan.role.officer"),
        'thrall': t("clan.role.member"),
    }
    members_text = ""
    for m in members:
        r_str = role_titles.get(m['clan_role'], t("clan.role.member"))
        members_text += t(
            "clan.member_line", role=r_str, name=m['username'], level=m['level'],
        )
        
    reqs_count = len(clan.get('join_requests', []))
    banner_str = f"{clan.get('banner', '')} " if clan.get('banner') else ""
    
    text = t(
        "clan.profile.text",
        banner=banner_str,
        name=clan['name'],
        level=clan['level'],
        raids=clan.get('total_raids', 0),
        members=len(members),
        max_members=max_m,
        members_text=members_text,
    )
    if is_leader and reqs_count > 0:
        text += t("clan.profile.requests", count=reqs_count)
        
    buttons = []
    buttons.append([InlineKeyboardButton(text=t("clan.btn.chat"), callback_data="clan_chat_view")])
    buttons.append([InlineKeyboardButton(text=t("clan.btn.homes"), callback_data="clan_homes_list")])
    
    if clan['level'] >= 5:
        buttons.append([InlineKeyboardButton(text=t("clan.btn.merchant"), callback_data="clan_merchant_view")])
        
    if is_leader:
        if clan['level'] >= 2:
            buttons.append([InlineKeyboardButton(text=t("clan.btn.banner"), callback_data="clan_set_banner_ask")])
        buttons.append([InlineKeyboardButton(text=t("clan.btn.upgrade"), callback_data="clan_upgrade_ask")])
        if reqs_count > 0:
            buttons.append([InlineKeyboardButton(text=t("clan.btn.requests", count=reqs_count), callback_data="clan_requests_view")])
        
    if user['clan_role'] in ['hedwing', 'lindeman']:
        buttons.append([InlineKeyboardButton(text=t("clan.btn.manage"), callback_data="clan_manage_list")])
        
    buttons.append([InlineKeyboardButton(text=t("clan.btn.vault"), callback_data="clan_vault_view")])
    
    if is_leader:
        buttons.append([InlineKeyboardButton(text=t("clan.btn.disband"), callback_data="clan_disband_confirm")])
    else:
        buttons.append([InlineKeyboardButton(text=t("clan.btn.leave"), callback_data="clan_leave_confirm")])
        
    buttons.append([InlineKeyboardButton(text=t("clan.btn.back"), callback_data="clan_main")])
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

# --- ДОМА СОКЛАНОВЦЕВ ---
@router.callback_query(F.data == "clan_homes_list")
async def clan_homes_list(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    if user.get('clan_id', 0) == 0: 
        return await callback.answer(t("clan.homes.none"), show_alert=True)
        
    members = get_clan_members(user['clan_id'])
    buttons = []
    for m in members:
        buttons.append([InlineKeyboardButton(text=t("clan.homes.btn", name=m['username']), callback_data=f"clan_vhome_{m['user_id']}")])
        
    buttons.append([InlineKeyboardButton(text=t("clan.homes.back"), callback_data="clan_my_info")])
    await callback.message.edit_text(t("clan.homes.title"), reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data.startswith("clan_vhome_"))
async def clan_view_home(callback: CallbackQuery):
    target_id = int(callback.data.replace("clan_vhome_", ""))
    viewer = get_user(callback.from_user.id)
    target_user = get_user(target_id)
    
    if not target_user: 
        return await callback.answer(t("clan.home.not_found"), show_alert=True)
    if not viewer or target_user.get('clan_id', 0) == 0 or target_user.get('clan_id') != viewer.get('clan_id'):
        return await callback.answer(t("clan.home.not_your_clan"), show_alert=True)
        
    home_data = target_user.get('home_data', {})
    stats = home_data.get('stats', {})
    skins = get_all_home_skins()
    skin_id = home_data.get("skin", "base")
    skin_info = skins.get(skin_id, {})
    skin_name = skin_info.get("name") or t("clan.home.default_skin")
    
    skin_desc = skin_info.get("desc", "")
    if not skin_desc or skin_desc.startswith("Убить") or skin_desc.startswith("Титул"):
        skin_desc = t("clan.home.default_desc")
        
    active_title = get_title_display(home_data.get('active_title') or TITLE_NOVICE)
    active_medal_id = home_data.get('active_medal')
    active_medal = get_medal_display(active_medal_id) if active_medal_id else t("home.no_medal")
    
    text = t(
        "clan.home.text",
        name=target_user['username'],
        skin=skin_name,
        desc=skin_desc,
        title=active_title,
        medal=active_medal,
        mobs=stats.get('mobs_killed', 0),
        bosses=stats.get('bosses_killed', 0),
        pvp=stats.get('pvp_wins', 0),
        deaths=stats.get('deaths_count', 0),
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t("clan.home.back"), callback_data="clan_homes_list")]])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

# --- СТЯГ КЛАНА ---
@router.callback_query(F.data == "clan_set_banner_ask")
async def clan_set_banner_ask(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ClanStates.waiting_for_banner)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t("common.cancel"), callback_data="clan_my_info")]])
    await callback.message.edit_text(t("clan.banner.title"), reply_markup=kb, parse_mode="Markdown")

@router.message(ClanStates.waiting_for_banner)
async def clan_set_banner_do(message: Message, state: FSMContext):
    user = get_user(message.from_user.id)
    clan = get_clan(user.get('clan_id', 0))
    
    if not clan or clan['leader_id'] != user['user_id']:
        return await message.answer(t("clan.banner.only_leader"))
        
    if not message.text:
        return await message.answer(t("clan.banner.text_only"))
    banner = message.text.strip()
    if len(banner) > 4: 
        return await message.answer(t("clan.banner.too_long"))
        
    update_clan(clan['clan_id'], banner=banner)
    await state.clear()
    
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t("clan.banner.back"), callback_data="clan_my_info")]])
    msg = await message.answer(t("clan.banner.success", banner=banner), reply_markup=kb)
    update_user(user['user_id'], last_msg_id=msg.message_id)

# --- ЧАТ КЛАНА ---
@router.callback_query(F.data == "clan_chat_view")
async def clan_chat_view(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    clan = get_clan(user.get('clan_id', 0))
    if not clan: return await callback.answer(t("clan.chat.none"), show_alert=True)
    
    chat = clan.get('chat_history', [])
    banner_str = f"{clan.get('banner', '')} " if clan.get('banner') else ""
    text = t("clan.chat.title", banner=banner_str, name=clan['name'])
    
    if not chat:
        text += t("clan.chat.empty")
    else:
        for msg in chat[-15:]: 
            text += t(
                "clan.chat.message",
                user=msg['user'], time=msg['time'], text=msg['text'],
            )
            
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("clan.chat.write"), callback_data="clan_chat_write")],
        [InlineKeyboardButton(text=t("clan.chat.refresh"), callback_data="clan_chat_view")],
        [InlineKeyboardButton(text=t("clan.chat.back"), callback_data="clan_my_info")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data == "clan_chat_write")
async def clan_chat_write(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ClanStates.waiting_for_chat_msg)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t("common.cancel"), callback_data="clan_chat_view")]])
    await callback.message.edit_text(t("clan.chat.prompt"), reply_markup=kb, parse_mode="Markdown")

@router.message(ClanStates.waiting_for_chat_msg)
async def clan_chat_receive(message: Message, state: FSMContext):
    if not message.text:
        return await message.answer(t("clan.chat.text_only"))
    user = get_user(message.from_user.id)
    clan = get_clan(user.get('clan_id', 0))
    if not clan: return
    
    chat = clan.get('chat_history', [])
    now_str = datetime.datetime.now().strftime("%H:%M")
    
    new_msg = {
        "user": user['username'],
        "text": message.text[:200], 
        "time": now_str
    }
    
    chat.append(new_msg)
    chat = chat[-50:] 
    
    update_clan(clan['clan_id'], chat_history=chat)
    await state.clear()
    
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t("clan.chat.open"), callback_data="clan_chat_view")]])
    msg = await message.answer(t("clan.chat.sent"), reply_markup=kb)
    update_user(user['user_id'], last_msg_id=msg.message_id)

# --- КЛАНОВЫЙ ТОРГОВЕЦ ---
@router.callback_query(F.data == "clan_merchant_view")
async def clan_merchant_view(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    clan = get_clan(user.get('clan_id', 0))
    
    if not clan or clan['level'] < 5:
        return await callback.answer(t("clan.merchant.level_fail"), show_alert=True)
        
    deals = get_clan_merchant_deals(clan['clan_id'])
    
    text = t("clan.merchant.title", gold=user['gold'])
    buttons = []
    
    if clan['level'] >= 20:
        text += t("clan.merchant.elite")
        buttons.append([InlineKeyboardButton(text=t("clan.merchant.to_market"), callback_data="town_market")])
    else:
        text += t("clan.merchant.intro")
        
        text += t("clan.merchant.buy_title")
        for i_id in deals.get('buy', []):
            price = max(1, int(get_item_price(i_id) * 0.7))
            item_name = get_item_name(i_id)
            text += t("clan.merchant.line", item=item_name, price=price)
            buttons.append([InlineKeyboardButton(text=t("clan.merchant.buy_btn", item=item_name), callback_data=f"c_merch_buy_{i_id}")])
            
        text += t("clan.merchant.sell_title")
        for i_id in deals.get('sell', []):
            price = get_item_price(i_id)
            item_name = get_item_name(i_id)
            text += t("clan.merchant.line", item=item_name, price=price)
            buttons.append([InlineKeyboardButton(text=t("clan.merchant.sell_btn", item=item_name), callback_data=f"c_merch_sell_{i_id}")])
            
    buttons.append([InlineKeyboardButton(text=t("clan.chat.back"), callback_data="clan_my_info")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data.startswith("c_merch_buy_"))
async def clan_merchant_buy(callback: CallbackQuery):
    i_id = callback.data.replace("c_merch_buy_", "")
    user = get_user(callback.from_user.id)
    price = max(1, int(get_item_price(i_id) * 0.7))
    
    if user['gold'] < price:
        return await callback.answer(t("clan.merchant.no_gold"), show_alert=True)
        
    item = get_item(i_id)
    inv = user['inventory']
    
    if item and item['type'] in ["weapon", "armor"]:
        inv.setdefault("backpack", []).append(i_id)
    elif item and item['type'] == "consumable":
        inv.setdefault("potions", []).append(i_id)
    else:
        inv.setdefault("materials", {})[i_id] = inv.get("materials", {}).get(i_id, 0) + 1
        
    user['gold'] -= price
    
    # ЛОГ: Покупка у кланового торговца
    log_event(user['user_id'], 'economy', 'clan_merchant_buy', -price, {'item_id': i_id})
    
    update_user(user['user_id'], gold=user['gold'], inventory=inv)
    await callback.answer(t("clan.merchant.bought", item=get_item_name(i_id), price=price), show_alert=True)
    await clan_merchant_view(callback)

@router.callback_query(F.data.startswith("c_merch_sell_"))
async def clan_merchant_sell(callback: CallbackQuery):
    i_id = callback.data.replace("c_merch_sell_", "")
    user = get_user(callback.from_user.id)
    
    inv = user['inventory']
    has_item = False
    
    if i_id in inv.get("backpack", []):
        inv["backpack"].remove(i_id)
        has_item = True
    elif inv.get("materials", {}).get(i_id, 0) > 0:
        inv["materials"][i_id] -= 1
        if inv["materials"][i_id] <= 0: del inv["materials"][i_id]
        has_item = True
    else:
        if i_id in inv.get("potions", []):
            inv["potions"].remove(i_id)
            has_item = True
        else:
            # Совместимость со старыми данными, где в potions лежало название.
            item_name = get_item_name(i_id)
            if item_name in inv.get("potions", []):
                inv["potions"].remove(item_name)
                has_item = True

    if not has_item:
        return await callback.answer(t("clan.merchant.no_item"), show_alert=True)
        
    price = get_item_price(i_id)
    user['gold'] += price
    
    # ЛОГ: Продажа клановому торговцу
    log_event(user['user_id'], 'economy', 'clan_merchant_sell', price, {'item_id': i_id})
    
    update_user(user['user_id'], gold=user['gold'], inventory=inv)
    await callback.answer(t("clan.merchant.sold", price=price), show_alert=True)
    await clan_merchant_view(callback)

# --- ПРОКАЧКА КЛАНА ---
@router.callback_query(F.data == "clan_upgrade_ask")
async def clan_upgrade_ask(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    clan = get_clan(user.get('clan_id', 0))
    
    if not clan or clan['leader_id'] != user['user_id']:
        return await callback.answer(t("clan.upgrade.only_leader"), show_alert=True)
        
    cur_lvl = clan['level']
    req_gold = 9000 + (cur_lvl * 1000)
    req_gems = 90 + (cur_lvl * 10)
    req_raids = cur_lvl * 100
    
    vault_raw = clan.get('clan_vault', '{}')
    vault = json.loads(vault_raw) if isinstance(vault_raw, str) else vault_raw
    cur_gold = clan['treasury']
    cur_gems = vault.get('gems', 0)
    cur_raids = clan.get('total_raids', 0)
    
    gold_mark = "✅" if cur_gold >= req_gold else "❌"
    gems_mark = "✅" if cur_gems >= req_gems else "❌"
    raids_mark = "✅" if cur_raids >= req_raids else "❌"
    
    text = t(
        "clan.upgrade.title",
        next_level=cur_lvl + 1,
        gold=cur_gold,
        max_gold=req_gold,
        gold_mark=gold_mark,
        gems=cur_gems,
        max_gems=req_gems,
        gems_mark=gems_mark,
        raids=cur_raids,
        max_raids=req_raids,
        raids_mark=raids_mark,
    )
    
    buttons = []
    if cur_gold >= req_gold and cur_gems >= req_gems and cur_raids >= req_raids:
        buttons.append([InlineKeyboardButton(text=t("clan.upgrade.do"), callback_data="clan_upgrade_do")])
        
    buttons.append([InlineKeyboardButton(text=t("clan.btn.back"), callback_data="clan_my_info")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data == "clan_upgrade_do")
async def clan_upgrade_do(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    clan = get_clan(user.get('clan_id', 0))
    
    if not clan or clan['leader_id'] != user['user_id']:
        return await callback.answer(t("clan.upgrade.access"), show_alert=True)
        
    cur_lvl = clan['level']
    req_gold = 9000 + (cur_lvl * 1000)
    req_gems = 90 + (cur_lvl * 10)
    req_raids = cur_lvl * 100
    
    vault_raw = clan.get('clan_vault', '{}')
    vault = json.loads(vault_raw) if isinstance(vault_raw, str) else vault_raw
    
    if clan['treasury'] < req_gold or vault.get('gems', 0) < req_gems or clan.get('total_raids', 0) < req_raids:
        return await callback.answer(t("clan.upgrade.resources"), show_alert=True)
        
    vault['gems'] -= req_gems
    new_treasury = clan['treasury'] - req_gold
    
    update_clan(clan['clan_id'], level=cur_lvl + 1, treasury=new_treasury, clan_vault=json.dumps(vault, ensure_ascii=False))
    
    # ЛОГ: Улучшение клана
    log_event(user['user_id'], 'clan', 'upgrade_clan', 0, {
        'clan_id': clan['clan_id'],
        'new_level': cur_lvl + 1,
        'cost_gold': req_gold,
        'cost_gems': req_gems
    })
    
    await callback.answer(t("clan.upgrade.success", level=cur_lvl + 1), show_alert=True)
    await show_my_clan(callback, None)

# --- УПРАВЛЕНИЕ СОСТАВОМ (Повышения / Изгнания) ---
@router.callback_query(F.data == "clan_manage_list")
async def clan_manage_list(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    clan = get_actor_clan(user)
    if not clan:
        return await callback.answer(t("clan.manage.not_in_clan"), show_alert=True)
    if user.get('clan_role') not in ['hedwing', 'lindeman']:
        return await callback.answer(t("clan.manage.no_rights"), show_alert=True)
        
    members = get_clan_members(clan['clan_id'])
    buttons = []
    for m in members:
        if m['user_id'] == user['user_id']: continue 
        role_icon = '👑' if m['clan_role'] == 'hedwing' else '⚔️' if m['clan_role'] == 'lindeman' else '🛡️'
        buttons.append([InlineKeyboardButton(text=f"{role_icon} {m['username']}", callback_data=f"clan_manage_u_{m['user_id']}")])
        
    buttons.append([InlineKeyboardButton(text=t("clan.homes.back"), callback_data="clan_my_info")])
    await callback.message.edit_text(t("clan.manage.title"), reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data.startswith("clan_manage_u_"))
async def clan_manage_user(callback: CallbackQuery):
    target_id = int(callback.data.replace("clan_manage_u_", ""))
    user = get_user(callback.from_user.id)
    clan = get_actor_clan(user)
    if not clan:
        return await callback.answer(t("clan.manage.not_in_clan"), show_alert=True)
    if user.get('clan_role') not in ['hedwing', 'lindeman']:
        return await callback.answer(t("clan.manage.no_rights"), show_alert=True)
        
    target = get_user(target_id)
    
    if not target or target.get('clan_id') != clan['clan_id']:
        return await callback.answer(t("clan.manage.not_found"), show_alert=True)
    if target['user_id'] == user['user_id']:
        return await callback.answer(t("clan.manage.self"), show_alert=True)
        
    my_role = user.get('clan_role')
    tar_role = target.get('clan_role')
    
    if not can_manage(user, target):
        return await callback.answer(t("clan.manage.no_rights_target"), show_alert=True)
        
    role_titles = {
        'hedwing': t("clan.role.plain.leader"),
        'lindeman': t("clan.role.plain.officer"),
        'thrall': t("clan.role.plain.member"),
    }
    text = t(
        "clan.manage.member_title",
        name=target['username'],
        role=role_titles.get(tar_role, t("clan.role.plain.member")),
    )
    
    buttons = []
    if my_role == 'hedwing':
        if tar_role == 'thrall':
            buttons.append([InlineKeyboardButton(text=t("clan.manage.make_officer"), callback_data=f"clan_setrole_{target_id}_lindeman")])
        elif tar_role == 'lindeman':
            buttons.append([InlineKeyboardButton(text=t("clan.manage.demote"), callback_data=f"clan_setrole_{target_id}_thrall")])
            
    buttons.append([InlineKeyboardButton(text=t("clan.manage.kick"), callback_data=f"clan_kick_{target_id}")])
    buttons.append([InlineKeyboardButton(text=t("clan.manage.back_list"), callback_data="clan_manage_list")])
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data.startswith("clan_setrole_"))
async def clan_setrole(callback: CallbackQuery):
    parts = callback.data.split("_")
    target_id, new_role = int(parts[2]), parts[3]
    user = get_user(callback.from_user.id)
    clan = get_actor_clan(user)
    
    if not clan or user.get('clan_role') != 'hedwing':
        return await callback.answer(t("clan.manage.only_leader_roles"), show_alert=True)
    if new_role not in ('thrall', 'lindeman'):
        return await callback.answer(t("clan.manage.bad_role"), show_alert=True)
    if target_id == user['user_id']:
        return await callback.answer(t("clan.manage.self_role"), show_alert=True)
        
    target = get_user(target_id)
    if not target or target.get('clan_id') != clan['clan_id']:
        return await callback.answer(t("clan.manage.not_found"), show_alert=True)
    if target.get('clan_role') == 'hedwing':
        return await callback.answer(t("clan.manage.leader_role"), show_alert=True)
        
    update_user(target_id, clan_role=new_role)
    await callback.answer(t("clan.manage.role_changed"))
    await clan_manage_list(callback)

@router.callback_query(F.data.startswith("clan_kick_"))
async def clan_kick(callback: CallbackQuery):
    target_id = int(callback.data.replace("clan_kick_", ""))
    user = get_user(callback.from_user.id)
    clan = get_actor_clan(user)
    
    if not clan:
        return await callback.answer(t("clan.manage.not_in_clan"), show_alert=True)
        
    target = get_user(target_id)
    if not target or target.get('clan_id') != clan['clan_id']:
        return await callback.answer(t("clan.manage.not_found"), show_alert=True)
    if target['user_id'] == user['user_id']:
        return await callback.answer(t("clan.manage.self_kick"), show_alert=True)
    if not can_manage(user, target):
        return await callback.answer(t("clan.manage.no_rights_short"), show_alert=True)
        
    update_user(target_id, clan_id=0, clan_role='thrall')
    await callback.answer(t("clan.manage.kicked"))
    await clan_manage_list(callback)

# --- КАЗНА И СКЛАД ---
@router.callback_query(F.data == "clan_vault_view")
async def show_clan_vault(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    user = get_user(callback.from_user.id)
    clan = get_actor_clan(user)
    if not clan:
        return await callback.answer(t("clan.manage.not_in_clan"), show_alert=True)
    vault_raw = clan.get('clan_vault', '{}')
    if isinstance(vault_raw, str):
        try: vault = json.loads(vault_raw)
        except: vault = {"gems": 0, "items": {}}
    else:
        vault = vault_raw
        
    gems_in_vault = vault.get("gems", 0)
    gold_in_vault = clan.get("treasury", 0)
    items = vault.get("items", {})
    
    text = t(
        "clan.vault.title",
        name=clan['name'], gold=gold_in_vault, gems=gems_in_vault,
    )
    if not items:
        text += t("clan.vault.empty")
    else:
        for m_id, count in items.items():
            text += t("clan.vault.item", item=get_item_name(m_id), count=count)
            
    buttons = [
        [InlineKeyboardButton(text=t("clan.btn.donate_gold"), callback_data="clan_donate_gold_ask"),
         InlineKeyboardButton(text=t("clan.btn.donate_gems"), callback_data="clan_donate_gems_ask")],
        [InlineKeyboardButton(text=t("clan.btn.donate_items"), callback_data="clan_donate_item_list")]
    ]
    
    if user.get('clan_role') in ['hedwing', 'lindeman']:
        buttons.append([
            InlineKeyboardButton(text=t("clan.btn.withdraw_gold"), callback_data="clan_withdraw_gold_ask"),
            InlineKeyboardButton(text=t("clan.btn.withdraw_gems"), callback_data="clan_withdraw_gems_ask")
        ])
        buttons.append([InlineKeyboardButton(text=t("clan.btn.withdraw_items"), callback_data="clan_withdraw_item_list")])
        
    buttons.append([InlineKeyboardButton(text=t("clan.btn.back_clan"), callback_data="clan_my_info")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data == "clan_donate_gold_ask")
async def ask_donate_gold(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ClanStates.waiting_for_gold)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t("common.cancel"), callback_data="clan_vault_view")]])
    await callback.message.edit_text(t("clan.donate.gold_prompt"), reply_markup=kb, parse_mode="Markdown")

@router.message(ClanStates.waiting_for_gold)
async def process_donate_gold(message: Message, state: FSMContext):
    if not message.text:
        return await message.answer(t("clan.donate.gold_text_only"))
    user = get_user(message.from_user.id)
    clan = get_actor_clan(user)
    if not clan:
        await state.clear()
        return await message.answer(t("clan.donate.not_in_clan"))
    try: amount = int(message.text.strip())
    except ValueError: return await message.answer(t("clan.donate.number_only"))
        
    if amount <= 0: return await message.answer(t("clan.donate.positive"))
    if user['gold'] < amount: return await message.answer(t("clan.donate.gold_not_enough", gold=user['gold']))
    
    user['gold'] -= amount
    update_user(user['user_id'], gold=user['gold'])
    
    update_clan(clan['clan_id'], treasury=clan.get('treasury', 0) + amount)
    
    # ЛОГ: Вклад в казну золотом
    log_event(user['user_id'], 'clan', 'donate_gold', -amount, {'clan_id': clan['clan_id']})
    
    await state.clear()
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t("clan.btn.to_vault"), callback_data="clan_vault_view")]])
    msg = await message.answer(t("clan.donate.gold_success", amount=amount), reply_markup=kb, parse_mode="Markdown")
    update_user(user['user_id'], last_msg_id=msg.message_id)

@router.callback_query(F.data == "clan_donate_gems_ask")
async def ask_donate_gems(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ClanStates.waiting_for_gems)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t("common.cancel"), callback_data="clan_vault_view")]])
    await callback.message.edit_text(t("clan.donate.gems_prompt"), reply_markup=kb, parse_mode="Markdown")

@router.message(ClanStates.waiting_for_gems)
async def process_donate_gems(message: Message, state: FSMContext):
    if not message.text:
        return await message.answer(t("clan.donate.gems_text_only"))
    user = get_user(message.from_user.id)
    clan = get_actor_clan(user)
    if not clan:
        await state.clear()
        return await message.answer(t("clan.donate.not_in_clan"))
    try: amount = int(message.text.strip())
    except ValueError: return await message.answer(t("clan.donate.number_only"))
        
    if amount <= 0: return await message.answer(t("clan.donate.positive"))
    if user.get('gems', 0) < amount: return await message.answer(t("clan.donate.gems_not_enough", gems=user.get('gems', 0)))
    
    user['gems'] -= amount
    update_user(user['user_id'], gems=user['gems'])
    
    vault_raw = clan.get('clan_vault', '{}')
    vault = json.loads(vault_raw) if isinstance(vault_raw, str) else vault_raw
    vault['gems'] = vault.get('gems', 0) + amount
    update_clan(clan['clan_id'], clan_vault=json.dumps(vault, ensure_ascii=False))
    
    # ЛОГ: Вклад в казну кристаллами
    log_event(user['user_id'], 'clan', 'donate_gems', -amount, {'clan_id': clan['clan_id']})
    
    await state.clear()
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t("clan.btn.to_vault"), callback_data="clan_vault_view")]])
    msg = await message.answer(t("clan.donate.gems_success", amount=amount), reply_markup=kb, parse_mode="Markdown")
    update_user(user['user_id'], last_msg_id=msg.message_id)

@router.callback_query(F.data == "clan_donate_item_list")
async def clan_donate_item_list(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    if not get_actor_clan(user):
        return await callback.answer(t("clan.manage.not_in_clan"), show_alert=True)
    materials = user['inventory'].get('materials', {})
    if not materials:
        return await callback.answer(t("clan.items.no_resources"), show_alert=True)
        
    buttons = []
    for m_id, count in list(materials.items())[:20]:
        if count > 0:
            buttons.append([InlineKeyboardButton(text=t("clan.items.donate_btn", item=get_item_name(m_id)), callback_data=f"clan_don_item_{m_id}")])
            
    buttons.append([InlineKeyboardButton(text=t("clan.items.back_vault"), callback_data="clan_vault_view")])
    await callback.message.edit_text(t("clan.items.donate_title"), reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data.startswith("clan_don_item_"))
async def clan_donate_item_do(callback: CallbackQuery):
    m_id = callback.data.replace("clan_don_item_", "")
    user = get_user(callback.from_user.id)
    clan = get_actor_clan(user)
    if not clan:
        return await callback.answer(t("clan.manage.not_in_clan"), show_alert=True)
    inv = user['inventory']
    materials = inv.get('materials', {})
    
    if materials.get(m_id, 0) < 1:
        return await callback.answer(t("clan.items.gone"), show_alert=True)
        
    materials[m_id] -= 1
    if materials[m_id] == 0: del materials[m_id]
    update_user(user['user_id'], inventory=inv)
    
    vault_raw = clan.get('clan_vault', '{}')
    vault = json.loads(vault_raw) if isinstance(vault_raw, str) else vault_raw
    items_vault = vault.setdefault('items', {})
    items_vault[m_id] = items_vault.get(m_id, 0) + 1
    
    update_clan(clan['clan_id'], clan_vault=json.dumps(vault, ensure_ascii=False))
    await callback.answer(t("clan.items.donated", item=get_item_name(m_id)))
    await clan_donate_item_list(callback)

@router.callback_query(F.data == "clan_withdraw_gold_ask")
async def ask_withdraw_gold(callback: CallbackQuery, state: FSMContext):
    user = get_user(callback.from_user.id)
    if user.get('clan_role') not in ['hedwing', 'lindeman']:
        return await callback.answer(t("clan.manage.no_rights"), show_alert=True)
        
    await state.set_state(ClanStates.waiting_for_withdraw_gold)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t("common.cancel"), callback_data="clan_vault_view")]])
    await callback.message.edit_text(t("clan.withdraw.gold_prompt"), reply_markup=kb, parse_mode="Markdown")

@router.message(ClanStates.waiting_for_withdraw_gold)
async def process_withdraw_gold(message: Message, state: FSMContext):
    if not message.text:
        return await message.answer(t("clan.withdraw.gold_text_only"))
    user = get_user(message.from_user.id)
    if user.get('clan_role') not in ['hedwing', 'lindeman']:
        return await message.answer(t("clan.manage.no_rights"))
        
    try: amount = int(message.text.strip())
    except ValueError: return await message.answer(t("clan.withdraw.number"))
    if amount <= 0: return await message.answer(t("clan.donate.positive"))

    clan = get_actor_clan(user)
    if not clan:
        await state.clear()
        return await message.answer(t("clan.donate.not_in_clan"))
    if clan.get('treasury', 0) < amount:
        return await message.answer(t("clan.withdraw.gold_not_enough", gold=clan.get('treasury', 0)))

    update_clan(clan['clan_id'], treasury=clan.get('treasury', 0) - amount)
    user['gold'] += amount
    update_user(user['user_id'], gold=user['gold'])

    # ЛОГ: Изъятие из казны золота
    log_event(user['user_id'], 'clan', 'withdraw_gold', amount, {'clan_id': clan['clan_id']})

    await state.clear()
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t("clan.btn.to_vault"), callback_data="clan_vault_view")]])
    msg = await message.answer(t("clan.withdraw.gold_success", amount=amount), reply_markup=kb, parse_mode="Markdown")
    update_user(user['user_id'], last_msg_id=msg.message_id)

@router.callback_query(F.data == "clan_withdraw_gems_ask")
async def ask_withdraw_gems(callback: CallbackQuery, state: FSMContext):
    user = get_user(callback.from_user.id)
    if user.get('clan_role') not in ['hedwing', 'lindeman']:
        return await callback.answer(t("clan.manage.no_rights"), show_alert=True)
        
    await state.set_state(ClanStates.waiting_for_withdraw_gems)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t("common.cancel"), callback_data="clan_vault_view")]])
    await callback.message.edit_text(t("clan.withdraw.gems_prompt"), reply_markup=kb, parse_mode="Markdown")

@router.message(ClanStates.waiting_for_withdraw_gems)
async def process_withdraw_gems(message: Message, state: FSMContext):
    if not message.text:
        return await message.answer(t("clan.withdraw.gems_text_only"))
    user = get_user(message.from_user.id)
    if user.get('clan_role') not in ['hedwing', 'lindeman']:
        return await message.answer(t("clan.manage.no_rights"))
        
    try: amount = int(message.text.strip())
    except ValueError: return await message.answer(t("clan.withdraw.number"))
    if amount <= 0: return await message.answer(t("clan.donate.positive"))

    clan = get_actor_clan(user)
    if not clan:
        await state.clear()
        return await message.answer(t("clan.donate.not_in_clan"))
    vault_raw = clan.get('clan_vault', '{}')
    vault = json.loads(vault_raw) if isinstance(vault_raw, str) else vault_raw
    
    if vault.get('gems', 0) < amount:
        return await message.answer(t("clan.withdraw.gems_not_enough", gems=vault.get('gems', 0)))

    vault['gems'] -= amount
    update_clan(clan['clan_id'], clan_vault=json.dumps(vault, ensure_ascii=False))
    
    user['gems'] = user.get('gems', 0) + amount
    update_user(user['user_id'], gems=user['gems'])

    # ЛОГ: Изъятие из казны кристаллов
    log_event(user['user_id'], 'clan', 'withdraw_gems', amount, {'clan_id': clan['clan_id']})

    await state.clear()
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t("clan.btn.to_vault"), callback_data="clan_vault_view")]])
    msg = await message.answer(t("clan.withdraw.gems_success", amount=amount), reply_markup=kb, parse_mode="Markdown")
    update_user(user['user_id'], last_msg_id=msg.message_id)

@router.callback_query(F.data == "clan_withdraw_item_list")
async def clan_withdraw_item_list(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    if user.get('clan_role') not in ['hedwing', 'lindeman']:
        return await callback.answer(t("clan.manage.no_rights"), show_alert=True)
        
    clan = get_actor_clan(user)
    if not clan:
        return await callback.answer(t("clan.manage.not_in_clan"), show_alert=True)
    vault = json.loads(clan.get('clan_vault', '{}')) if isinstance(clan.get('clan_vault'), str) else clan.get('clan_vault', {})
    items = vault.get('items', {})

    if not items:
        return await callback.answer(t("clan.items.vault_empty"), show_alert=True)

    buttons = []
    for m_id, count in list(items.items())[:20]:
        if count > 0:
            buttons.append([InlineKeyboardButton(text=t("clan.items.take_btn", item=get_item_name(m_id)), callback_data=f"clan_take_item_{m_id}")])

    buttons.append([InlineKeyboardButton(text=t("clan.items.back_vault"), callback_data="clan_vault_view")])
    await callback.message.edit_text(t("clan.items.take_title"), reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data.startswith("clan_take_item_"))
async def clan_take_item_do(callback: CallbackQuery):
    m_id = callback.data.replace("clan_take_item_", "")
    user = get_user(callback.from_user.id)
    if user.get('clan_role') not in ['hedwing', 'lindeman']:
        return await callback.answer(t("clan.manage.no_rights"), show_alert=True)

    clan = get_actor_clan(user)
    if not clan:
        return await callback.answer(t("clan.manage.not_in_clan"), show_alert=True)
    vault_raw = clan.get('clan_vault', '{}')
    vault = json.loads(vault_raw) if isinstance(vault_raw, str) else vault_raw
    items_vault = vault.setdefault('items', {})

    if items_vault.get(m_id, 0) < 1:
        return await callback.answer(t("clan.items.vault_gone"), show_alert=True)

    items_vault[m_id] -= 1
    if items_vault[m_id] == 0: del items_vault[m_id]

    update_clan(clan['clan_id'], clan_vault=json.dumps(vault, ensure_ascii=False))

    inv = user['inventory']
    materials = inv.setdefault('materials', {})
    materials[m_id] = materials.get(m_id, 0) + 1
    update_user(user['user_id'], inventory=inv)

    await callback.answer(t("clan.items.taken", item=get_item_name(m_id)))
    await clan_withdraw_item_list(callback)

# --- ПОДМЕНЮ ПОИСКА КЛАНОВ ---
@router.callback_query(F.data == "clan_search_list")
async def show_clans_list(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    clans = get_all_clans_ranked()
    
    if not clans:
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t("clan.btn.back"), callback_data="clan_main")]])
        return await callback.message.edit_text(t("clan.search.empty"), reply_markup=kb, parse_mode="Markdown")
        
    text = t("clan.search.title")
    buttons = []
    for c in clans[:10]:
        rank_icon = "🥇" if c['rank'] == 1 else "🥈" if c['rank'] == 2 else "🥉" if c['rank'] == 3 else f"#{c['rank']}"
        banner = f"{c['banner']} " if c.get('banner') else ""
        text += t(
            "clan.search.line",
            rank=rank_icon, banner=banner, name=c['name'], level=c['level'],
            avg=c['avg_level'], members=c['members_count'],
            max_members=c['max_members'], free=c['free_slots'],
        )
        buttons.append([InlineKeyboardButton(
            text=t(
                "clan.search.btn",
                rank=rank_icon, banner=banner, name=c['name'], free=c['free_slots'],
            ),
            callback_data=f"clan_view_{c['clan_id']}",
        )])
        
    buttons.append([InlineKeyboardButton(text=t("clan.btn.back"), callback_data="clan_main")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data.startswith("clan_view_"))
async def view_clan_card(callback: CallbackQuery, clan_id: int = None):
    if clan_id is None:
        clan_id = int(callback.data.replace("clan_view_", ""))
    user = get_user(callback.from_user.id)
    clans = get_all_clans_ranked()
    
    clan_info = next((c for c in clans if c['clan_id'] == clan_id), None)
    if not clan_info: return await callback.answer(t("clan.card.not_found"), show_alert=True)
        
    rank_icon = "🥇" if clan_info['rank'] == 1 else "🥈" if clan_info['rank'] == 2 else "🥉" if clan_info['rank'] == 3 else f"#{clan_info['rank']}"
    banner = f"{clan_info['banner']} " if clan_info.get('banner') else ""
    
    text = t(
        "clan.card.title",
        banner=banner, name=clan_info['name'], rank=rank_icon,
        level=clan_info['level'], avg=clan_info['avg_level'],
        members=clan_info['members_count'], max_members=clan_info['max_members'],
        free=clan_info['free_slots'],
    )
    
    buttons = []
    if user.get('clan_id', 0) == 0:
        if clan_info['free_slots'] > 0:
            if user['user_id'] in clan_info['join_requests']:
                buttons.append([InlineKeyboardButton(text=t("clan.card.pending"), callback_data="clan_noop")])
            else:
                buttons.append([InlineKeyboardButton(text=t("clan.card.apply"), callback_data=f"clan_apply_{clan_id}")])
        else:
            buttons.append([InlineKeyboardButton(text=t("clan.card.no_slots"), callback_data="clan_noop")])
            
    buttons.append([InlineKeyboardButton(text=t("clan.card.back_list"), callback_data="clan_search_list")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data == "clan_noop")
async def clan_noop(callback: CallbackQuery):
    await callback.answer()

@router.callback_query(F.data.startswith("clan_apply_"))
async def apply_to_clan(callback: CallbackQuery):
    clan_id = int(callback.data.replace("clan_apply_", ""))
    user = get_user(callback.from_user.id)
    
    if user.get('clan_id', 0) != 0: return await callback.answer(t("clan.create.already"), show_alert=True)
    clan = get_clan(clan_id)
    if not clan: return await callback.answer(t("clan.card.not_found"), show_alert=True)
    
    max_m = 5 + clan['level'] * 5
    if len(get_clan_members(clan_id)) >= max_m:
        return await callback.answer(t("clan.card.no_slots_apply"), show_alert=True)
        
    reqs = clan.get('join_requests', [])
    if user['user_id'] not in reqs:
        reqs.append(user['user_id'])
        update_clan(clan_id, join_requests=reqs)
        await callback.answer(t("clan.card.applied"), show_alert=True)
    else:
        await callback.answer(t("clan.card.already_applied"), show_alert=True)
        
    await view_clan_card(callback, clan_id)

@router.callback_query(F.data == "clan_requests_view")
async def view_clan_requests(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    clan = get_clan(user.get('clan_id', 0))
    if not clan or clan['leader_id'] != user['user_id']:
        return await callback.answer(t("clan.requests.only_leader"), show_alert=True)
        
    reqs = clan.get('join_requests', [])
    if not reqs:
        return await callback.message.edit_text(t("clan.requests.none"), reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t("clan.banner.back"), callback_data="clan_my_info")]]))
        
    buttons = []
    text = t("clan.requests.title")
    for applicant_id in reqs[:8]:
        app_user = get_user(applicant_id)
        if app_user:
            text += t("clan.requests.line", name=app_user['username'], level=app_user.get('level', 1))
            buttons.append([
                InlineKeyboardButton(text=t("clan.requests.accept", name=app_user['username']), callback_data=f"clan_accept_{applicant_id}"),
                InlineKeyboardButton(text="❌", callback_data=f"clan_reject_{applicant_id}")
            ])
            
    buttons.append([InlineKeyboardButton(text=t("clan.btn.back"), callback_data="clan_my_info")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data.startswith("clan_accept_"))
async def accept_clan_request(callback: CallbackQuery):
    app_id = int(callback.data.replace("clan_accept_", ""))
    user = get_user(callback.from_user.id)
    clan_id = user.get('clan_id', 0)
    clan = get_clan(clan_id)
    
    if not clan or clan['leader_id'] != user['user_id']: return await callback.answer(t("clan.upgrade.access"), show_alert=True)
    max_m = 5 + clan['level'] * 5
    members = get_clan_members(clan_id)
    if len(members) >= max_m: return await callback.answer(t("clan.requests.no_slots"), show_alert=True)
        
    reqs = clan.get('join_requests', [])
    if app_id not in reqs:
        return await callback.answer(t("clan.requests.stale"), show_alert=True)
        
    applicant = get_user(app_id)
    if not applicant:
        reqs.remove(app_id)
        update_clan(clan_id, join_requests=reqs)
        return await callback.answer(t("clan.requests.applicant_missing"), show_alert=True)
    if applicant.get('clan_id', 0) != 0:
        reqs.remove(app_id)
        update_clan(clan_id, join_requests=reqs)
        return await callback.answer(t("clan.requests.already_in_clan"), show_alert=True)
        
    reqs.remove(app_id)
    update_clan(clan_id, join_requests=reqs)
        
    update_user(app_id, clan_id=clan_id, clan_role='thrall')
    await callback.answer(t("clan.requests.accepted"))
    await view_clan_requests(callback)

@router.callback_query(F.data.startswith("clan_reject_"))
async def reject_clan_request(callback: CallbackQuery):
    app_id = int(callback.data.replace("clan_reject_", ""))
    user = get_user(callback.from_user.id)
    clan_id = user.get('clan_id', 0)
    clan = get_clan(clan_id)
    
    if clan and clan['leader_id'] == user['user_id']:
        reqs = clan.get('join_requests', [])
        if app_id in reqs:
            reqs.remove(app_id)
            update_clan(clan_id, join_requests=reqs)
    await callback.answer(t("clan.requests.rejected"))
    await view_clan_requests(callback)

# --- ПОКИНУТЬ / РАСПУСТИТЬ КЛАН ---
@router.callback_query(F.data == "clan_leave_confirm")
async def clan_leave_confirm(callback: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("clan.leave.yes"), callback_data="clan_leave_do")],
        [InlineKeyboardButton(text=t("common.cancel"), callback_data="clan_my_info")]
    ])
    await callback.message.edit_text(t("clan.leave.confirm"), reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data == "clan_leave_do")
async def clan_leave_do(callback: CallbackQuery, state: FSMContext):
    user = get_user(callback.from_user.id)
    clan_id = user.get('clan_id', 0)
    clan = get_clan(clan_id)
    
    if not clan_id:
        return await callback.answer(t("clan.leave.not_member"), show_alert=True)
    
    if clan and clan['leader_id'] == user['user_id']:
        return await callback.answer(t("clan.leave.leader_cannot_leave"), show_alert=True)
        
    update_user(user['user_id'], clan_id=0, clan_role='thrall')
    await callback.answer(t("clan.leave.done"), show_alert=True)
    await clan_main_menu(callback, state)

@router.callback_query(F.data == "clan_disband_confirm")
async def clan_disband_confirm(callback: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("clan.disband.yes"), callback_data="clan_disband_do")],
        [InlineKeyboardButton(text=t("common.cancel"), callback_data="clan_my_info")]
    ])
    await callback.message.edit_text(t("clan.disband.confirm"), reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data == "clan_disband_do")
async def clan_disband_do(callback: CallbackQuery, state: FSMContext):
    user = get_user(callback.from_user.id)
    clan_id = user.get('clan_id', 0)
    clan = get_clan(clan_id)
    
    if not clan or clan['leader_id'] != user['user_id']:
        return await callback.answer(t("clan.disband.only_leader"), show_alert=True)
        
    with get_connection() as conn:
        cur = conn.cursor()
        # Обновляем всех игроков, состоящих в этом клане, превращая их в "одиночек"
        cur.execute("UPDATE users SET clan_id = 0, clan_role = 'thrall' WHERE clan_id = ?", (clan_id,))
        # Удаляем запись о клане
        cur.execute("DELETE FROM clans WHERE clan_id = ?", (clan_id,))
        conn.commit()
        
    await callback.answer(t("clan.disband.done"), show_alert=True)
    await clan_main_menu(callback, state)
