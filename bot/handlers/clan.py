import sqlite3
import json
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command, CommandObject
from database import get_user, update_user, get_connection, get_clan, get_clan_by_name, update_clan, get_clan_members, get_item_name, get_item

router = Router()

ROLE_NAMES = {"hedwing": "👑 Хедвинг (Глава)", "lindeman": "🎖 Линдеман (Офицер)", "thrall": "⚔️ Трелл (Рядовой)"}

@router.callback_query(F.data == "clan_main")
async def clan_menu(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    if user['clan_id'] == 0:
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 В лагерь", callback_data="town_back")]])
        text = ("🛡️ **Клановый Зал**\n\nВы не состоите в клане.\n\n"
                "🔹 **Создать клан:** Введите команду `/createclan [Название]` (Требуется 50 ур. и 100 💎)\n"
                "🔹 **Найти клан:** Введите `/searchclan [Название]` чтобы подать заявку.")
        return await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        
    clan = get_clan(user['clan_id'])
    role_name = ROLE_NAMES.get(user['clan_role'], "Трелл")
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Состав клана", callback_data="clan_members"), InlineKeyboardButton(text="🔥 Co-op Рейд", callback_data="clan_coop")],
        [InlineKeyboardButton(text="📦 Склад (Общак)", callback_data="clan_vault")],
        [InlineKeyboardButton(text="🚪 Покинуть клан", callback_data="clan_leave")],
        [InlineKeyboardButton(text="🔙 В лагерь", callback_data="town_back")]
    ])
    
    if user['clan_role'] in ['hedwing', 'lindeman']:
        kb.inline_keyboard.insert(0, [InlineKeyboardButton(text=f"✉️ Заявки ({len(clan['join_requests'])})", callback_data="clan_requests")])
        
    text = (f"🛡️ **Клан: {clan['name']}** (Уровень {clan['level']})\n\n"
            f"👤 Ваше звание: **{role_name}**\n"
            f"🏆 Рейдов за неделю: {clan['weekly_raids']}\n"
            f"💰 Казна: {clan['treasury']}\n\n"
            f"💡 *Склад позволяет обмениваться золотом и вещами с соклановцами.*")
            
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

@router.message(Command("createclan"))
async def create_clan(message: Message, command: CommandObject):
    user = get_user(message.from_user.id)
    if user['clan_id'] != 0: return await message.answer("Вы уже состоите в клане!")
    if user['level'] < 50: return await message.answer("Для создания клана нужен 50 уровень!")
    if user['gems'] < 100: return await message.answer("Для создания клана нужно 100 💎 Алмазов!")
    
    clan_name = command.args
    if not clan_name or len(clan_name) < 3: return await message.answer("Укажите название клана (минимум 3 символа)!\nПример: `/createclan Волки`", parse_mode="Markdown")
    if get_clan_by_name(clan_name): return await message.answer("Клан с таким названием уже существует!")
        
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO clans (name, leader_id) VALUES (?, ?)", (clan_name, user['user_id']))
        clan_id = cursor.lastrowid
        conn.commit()
        
    update_user(user['user_id'], gems=user['gems'] - 100, clan_id=clan_id, clan_role="hedwing")
    await message.answer(f"🎉 **Клан «{clan_name}» успешно создан!**", parse_mode="Markdown")

@router.message(Command("searchclan"))
async def search_clan(message: Message, command: CommandObject):
    user = get_user(message.from_user.id)
    if user['clan_id'] != 0: return await message.answer("Вы уже состоите в клане!")
    clan_name = command.args
    if not clan_name: return await message.answer("Использование: `/searchclan [Название]`", parse_mode="Markdown")
    
    clan = get_clan_by_name(clan_name)
    if not clan: return await message.answer("Клан не найден.")
    
    reqs = clan['join_requests']
    if user['user_id'] in reqs: return await message.answer("Вы уже подали заявку в этот клан.")
        
    reqs.append(user['user_id'])
    update_clan(clan['clan_id'], join_requests=reqs)
    await message.answer(f"📨 Заявка на вступление в **{clan['name']}** отправлена руководству!", parse_mode="Markdown")

@router.callback_query(F.data == "clan_requests")
async def show_requests(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    if user['clan_role'] not in ['hedwing', 'lindeman']: return
    
    clan = get_clan(user['clan_id'])
    reqs = clan['join_requests']
    
    if not reqs:
        return await callback.message.edit_text("✉️ Список заявок пуст.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="clan_main")]]))
        
    text = "✉️ **Заявки на вступление:**\n\n"
    buttons = []
    
    for r_id in reqs[:5]:
        r_user = get_user(r_id)
        if r_user and r_user['clan_id'] == 0:
            text += f"👤 **{r_user['username']}** ({r_user['level']} ур.)\n"
            buttons.append([
                InlineKeyboardButton(text=f"✅ {r_user['username']}", callback_data=f"clan_req_acc_{r_id}"),
                InlineKeyboardButton(text=f"❌ {r_user['username']}", callback_data=f"clan_req_rej_{r_id}")
            ])
            
    buttons.append([InlineKeyboardButton(text="🔙 В меню клана", callback_data="clan_main")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data.startswith("clan_req_"))
async def process_request(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    if user['clan_role'] not in ['hedwing', 'lindeman']: return
    
    action = callback.data.split("_")[2]
    target_id = int(callback.data.split("_")[3])
    
    clan = get_clan(user['clan_id'])
    reqs = clan.get('join_requests', [])
    
    if target_id in reqs:
        reqs.remove(target_id)
        update_clan(clan['clan_id'], join_requests=reqs)
        
        if action == "acc":
            target_user = get_user(target_id)
            if target_user and target_user['clan_id'] == 0:
                update_user(target_id, clan_id=clan['clan_id'], clan_role="thrall")
                await callback.answer(f"Игрок принят в клан!")
            else:
                await callback.answer("Игрок уже в другом клане!")
        else:
            await callback.answer("Заявка отклонена.")
            
    await show_requests(callback)

@router.callback_query(F.data == "clan_members")
async def show_members(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    members = get_clan_members(user['clan_id'])
    text = "👥 **Состав Клана**\n\n"
    for m in members:
        role = ROLE_NAMES.get(m['clan_role'], "Трелл")
        status = "В рейде ⚔️" if m['state'] in ['STATE_DUNGEON', 'STATE_COMBAT'] else "В лагере 🏕"
        text += f"• **{m['username']}** (ID: `{m['user_id']}`) | {m['level']} ур. | {role} | {status}\n"
        
    buttons = []
    if user['clan_role'] in ['hedwing', 'lindeman']:
        buttons.append([InlineKeyboardButton(text="⚙️ Управление составом", callback_data="clan_manage_list")])
    buttons.append([InlineKeyboardButton(text="🔙 Клан", callback_data="clan_main")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data == "clan_manage_list")
async def clan_manage_list(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    if user['clan_role'] not in ['hedwing', 'lindeman']: return
    members = get_clan_members(user['clan_id'])
    buttons = []
    for m in members:
        if m['user_id'] != user['user_id']:
            role = "👑" if m['clan_role'] == 'hedwing' else "🎖" if m['clan_role'] == 'lindeman' else "⚔️"
            buttons.append([InlineKeyboardButton(text=f"{role} {m['username']}", callback_data=f"clan_manage_user_{m['user_id']}")])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="clan_members")])
    await callback.message.edit_text("⚙️ **Управление кланом**\nКого будем судить?", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data.startswith("clan_manage_user_"))
async def clan_manage_user(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    if user['clan_role'] not in ['hedwing', 'lindeman']: return
    target_id = int(callback.data.replace("clan_manage_user_", ""))
    target = get_user(target_id)
    if not target or target['clan_id'] != user['clan_id']: return await callback.answer("Игрок не найден!", show_alert=True)
        
    buttons = []
    if user['clan_role'] == 'hedwing' and target['clan_role'] != 'hedwing':
        if target['clan_role'] == 'thrall': buttons.append([InlineKeyboardButton(text="🎖 Повысить до Офицера", callback_data=f"clan_act_promote_{target_id}")])
        elif target['clan_role'] == 'lindeman':
            buttons.append([InlineKeyboardButton(text="👑 Передать Лидерство", callback_data=f"clan_act_transfer_{target_id}")])
            buttons.append([InlineKeyboardButton(text="⬇️ Понизить до Рядового", callback_data=f"clan_act_demote_{target_id}")])
        buttons.append([InlineKeyboardButton(text="🥾 Изгнать из клана", callback_data=f"clan_act_kick_{target_id}")])
    elif user['clan_role'] == 'lindeman' and target['clan_role'] == 'thrall':
        buttons.append([InlineKeyboardButton(text="🥾 Изгнать из клана", callback_data=f"clan_act_kick_{target_id}")])
        
    buttons.append([InlineKeyboardButton(text="🔙 Отмена", callback_data="clan_manage_list")])
    text = f"⚙️ **Управление:** {target['username']}\nТекущее звание: {ROLE_NAMES.get(target['clan_role'])}"
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data.startswith("clan_act_"))
async def clan_action_user(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    action = callback.data.split("_")[2]
    target_id = int(callback.data.split("_")[3])
    target = get_user(target_id)
    if not target or target['clan_id'] != user['clan_id']: return await callback.answer("Ошибка!", show_alert=True)
    
    if action == "promote" and user['clan_role'] == 'hedwing':
        update_user(target_id, clan_role="lindeman")
        await callback.answer(f"{target['username']} стал Офицером!")
    elif action == "demote" and user['clan_role'] == 'hedwing':
        update_user(target_id, clan_role="thrall")
        await callback.answer(f"{target['username']} разжалован в Рядовые!")
    elif action == "transfer" and user['clan_role'] == 'hedwing':
        with get_connection() as conn:
            conn.execute("UPDATE clans SET leader_id=? WHERE clan_id=?", (target_id, user['clan_id']))
            conn.commit()
        update_user(target_id, clan_role="hedwing")
        update_user(user['user_id'], clan_role="lindeman")
        await callback.answer(f"Лидерство передано {target['username']}!")
        return await clan_menu(callback)
    elif action == "kick":
        update_user(target_id, clan_id=0, clan_role="thrall")
        await callback.answer(f"{target['username']} изгнан из клана!")
        
    await clan_manage_list(callback)

@router.callback_query(F.data == "clan_leave")
async def clan_leave(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    if user['clan_role'] == 'hedwing':
        members = get_clan_members(user['clan_id'])
        if len(members) > 1: return await callback.answer("Вы глава! Изгоните всех или передайте лидерство перед уходом.", show_alert=True)
    update_user(user['user_id'], clan_id=0, clan_role="thrall")
    await callback.answer("Вы покинули клан.", show_alert=True)
    await clan_menu(callback)

@router.callback_query(F.data == "clan_vault")
async def open_clan_vault(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    clan = get_clan(user['clan_id'])
    vault = json.loads(clan.get('clan_vault', '{"gold": 0, "items": {}}'))
    
    text = f"📦 **Склад клана {clan['name']}**\n\n💰 Золото в общаке: **{vault.get('gold', 0)} 🪙**\n\n**Вещи на складе:**\n"
    items = vault.get('items', {})
    if not items: text += "Склад пуст.\n"
    else:
        for i_id, count in items.items(): text += f" • {get_item_name(i_id)} (x{count})\n"
            
    text += ("\n💡 **Инструкция по обмену:**\n"
             "Положить золото: `/put gold 100`\n"
             "Взять золото: `/take gold 50`\n"
             "Положить вещь: `/put item_id 1`\n"
             "Взять вещь: `/take item_id 1`\n\n"
             "Прямая передача: `/give [ID] [item_id/gold] [кол-во]`")
             
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="clan_main")]])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

@router.message(Command("put"))
async def put_to_vault(message: Message, command: CommandObject):
    user = get_user(message.from_user.id)
    if user['clan_id'] == 0: return await message.answer("Вы не в клане!")
    try: item_id, amount_str = command.args.split(); amount = int(amount_str)
    except: return await message.answer("Формат: `/put gold 100` или `/put iron_ingot 5`", parse_mode="Markdown")
    
    clan = get_clan(user['clan_id'])
    vault = json.loads(clan.get('clan_vault', '{"gold": 0, "items": {}}'))
    inv = user['inventory']
    
    if item_id == "gold":
        if user['gold'] < amount: return await message.answer("Недостаточно золота!")
        user['gold'] -= amount
        vault["gold"] = vault.get("gold", 0) + amount
    else:
        if inv.get("materials", {}).get(item_id, 0) >= amount:
            inv["materials"][item_id] -= amount
            if inv["materials"][item_id] == 0: del inv["materials"][item_id]
        elif item_id in inv.get("backpack", []):
            amount = 1
            inv["backpack"].remove(item_id)
        else: return await message.answer("У вас нет этого предмета!")
        vault.setdefault("items", {})[item_id] = vault.get("items", {}).get(item_id, 0) + amount
        
    update_user(user['user_id'], gold=user['gold'], inventory=inv)
    update_clan(clan['clan_id'], clan_vault=json.dumps(vault, ensure_ascii=False))
    await message.answer(f"📦 Вы положили на склад {amount}x {get_item_name(item_id) if item_id != 'gold' else 'Золото'}!")

@router.message(Command("take"))
async def take_from_vault(message: Message, command: CommandObject):
    user = get_user(message.from_user.id)
    if user['clan_id'] == 0: return await message.answer("Вы не в клане!")
    try: item_id, amount_str = command.args.split(); amount = int(amount_str)
    except: return await message.answer("Формат: `/take gold 100` или `/take iron_ingot 5`", parse_mode="Markdown")
    
    clan = get_clan(user['clan_id'])
    vault = json.loads(clan.get('clan_vault', '{"gold": 0, "items": {}}'))
    inv = user['inventory']
    
    if item_id == "gold":
        if vault.get("gold", 0) < amount: return await message.answer("На складе нет столько золота!")
        vault["gold"] -= amount
        user['gold'] += amount
    else:
        if vault.get("items", {}).get(item_id, 0) < amount: return await message.answer("На складе нет этого предмета!")
        vault["items"][item_id] -= amount
        if vault["items"][item_id] <= 0: del vault["items"][item_id]
        
        item_db = get_item(item_id)
        if item_db and item_db['type'] in ['weapon', 'armor']: inv.setdefault("backpack", []).append(item_id)
        else: inv.setdefault("materials", {})[item_id] = inv.setdefault("materials", {}).get(item_id, 0) + amount

    update_user(user['user_id'], gold=user['gold'], inventory=inv)
    update_clan(clan['clan_id'], clan_vault=json.dumps(vault, ensure_ascii=False))
    await message.answer(f"📦 Вы взяли со склада {amount}x {get_item_name(item_id) if item_id != 'gold' else 'Золото'}!")

@router.message(Command("give"))
async def trade_item(message: Message, command: CommandObject):
    user = get_user(message.from_user.id)
    if user['clan_id'] == 0: return await message.answer("Для обмена нужно состоять в клане.")
    try:
        target_id_str, item_id, amount_str = command.args.split()
        target_id, amount = int(target_id_str), int(amount_str)
    except: return await message.answer("Использование: `/give [ID_Игрока] [item_id] [кол-во]`", parse_mode="Markdown")
        
    target_user = get_user(target_id)
    if not target_user or target_user['clan_id'] != user['clan_id']: return await message.answer("Игрок не найден в вашем клане!")
        
    u_inv, t_inv = user['inventory'], target_user['inventory']
    
    if item_id == "gold":
        if user['gold'] < amount: return await message.answer("Недостаточно золота!")
        user['gold'] -= amount
        target_user['gold'] += amount
        update_user(user['user_id'], gold=user['gold'])
        update_user(target_user['user_id'], gold=target_user['gold'])
        return await message.answer(f"💰 Вы успешно передали {amount} Золота игроку {target_user['username']}!")
    
    if u_inv.get("materials", {}).get(item_id, 0) >= amount:
        u_inv["materials"][item_id] -= amount
        if u_inv["materials"][item_id] == 0: del u_inv["materials"][item_id]
        t_inv.setdefault("materials", {})[item_id] = t_inv.setdefault("materials", {}).get(item_id, 0) + amount
    elif item_id in u_inv.get("backpack", []):
        amount = 1 
        u_inv["backpack"].remove(item_id)
        t_inv.setdefault("backpack", []).append(item_id)
    else: return await message.answer(f"У вас нет предмета `{item_id}` в достаточном количестве.", parse_mode="Markdown")
        
    update_user(user['user_id'], inventory=u_inv)
    update_user(target_user['user_id'], inventory=t_inv)
    await message.answer(f"📦 Вы успешно передали {amount}x {get_item_name(item_id)} игроку {target_user['username']}!")

@router.callback_query(F.data == "clan_coop")
async def clan_coop_menu(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    members = get_clan_members(user['clan_id'])
    active_raiders = [m for m in members if m['state'] == 'STATE_COMBAT' and m['user_id'] != user['user_id']]
    
    text = "🔥 **Помощь в рейде (Co-op)**\nЗдесь показаны соклановцы, которые прямо сейчас сражаются с врагом.\n\n"
    buttons = []
    if active_raiders:
        for r in active_raiders: buttons.append([InlineKeyboardButton(text=f"Ворваться к {r['username']}", callback_data=f"coop_join_{r['user_id']}")])
    else: text += "Никто из соклановцев сейчас не ведет бой."
        
    buttons.append([InlineKeyboardButton(text="🔙 Клан", callback_data="clan_main")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")
