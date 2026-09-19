# handlers/dungeon.py
import random
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database import get_user, update_user, get_today_dungeon, get_mob_by_name
from utils.generators import generate_emoji_puzzle, generate_dungeon_graph

router = Router()

def get_navigation_kb(dungeon_data):
    """Строит кнопки навигации на основе текущего узла графа"""
    current_node_id = dungeon_data["current_node"]
    graph = dungeon_data["nodes"]
    current_node = graph[current_node_id]
    
    buttons = []
    row = []
    
    type_icons = {
        "combat": "⚔️ Враг",
        "puzzle": "🧩 Загадка",
        "treasure": "💰 Тайник",
        "campfire": "🏕️ Привал",
        "boss": "👹 БОСС"
    }
    
    for next_id in current_node["next"]:
        next_room = graph[next_id]
        icon = type_icons.get(next_room["type"], "🚪 Дверь")
        row.append(InlineKeyboardButton(text=icon, callback_data=f"dung_go_{next_id}"))
        
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
        
    buttons.append([InlineKeyboardButton(text="🏃‍♂️ Сбежать с лутом", callback_data="dungeon_flee")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_dungeon_config(dungeon_type):
    """Возвращает нужных мобов и лут в зависимости от типа данжа"""
    if dungeon_type == "event":
        return get_today_dungeon()
    else:
        # Дефолтный соло-данж (Ацтекские/Кхмерские мотивы)
        return {
            "name": "🗿 Руины Забытых Богов",
            "desc": "Скрытый под землей древний храм. Влажный воздух пропитан запахом мха, а каменные плиты под ногами таят механизмы.",
            "mobs": ["Храмовый Страж", "Оживший Идол", "Токсичный Слизень"],
            "loot": "iron_ingot",
            "loot_name": "Железный слиток"
        }

# --- 1. ДОСКА РЕЙДОВ (МЕНЮ) ---
@router.callback_query(F.data == "town_raids")
async def show_raids_menu(callback: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚶 Соло Рейд", callback_data="dungeon_start_solo")],
        [InlineKeyboardButton(text="👥 Групповой Рейд", callback_data="dungeon_start_group")],
        [InlineKeyboardButton(text="📅 Ивентовый Данж (Событие дня)", callback_data="dungeon_start_event")],
        [InlineKeyboardButton(text="🔙 В лагерь", callback_data="town_back")]
    ])
    await callback.message.edit_text(
        "⚔️ **Доска Рейдов**\nВыберите тип экспедиции. Будьте готовы ко всему.", 
        reply_markup=kb, parse_mode="Markdown"
    )

# --- 2. ВХОД В ПОДЗЕМЕЛЬЕ ---
@router.callback_query(F.data.startswith("dungeon_start_"))
async def enter_dungeon(callback: CallbackQuery):
    dungeon_type = callback.data.split("_")[-1]
    
    if dungeon_type == "group":
        return await callback.answer("Групповые рейды в разработке! Собираем лобби...", show_alert=True)
        
    # Генерируем граф и сохраняем тип данжа
    dungeon_data = generate_dungeon_graph(dungeon_type)
    update_user(callback.from_user.id, state='STATE_DUNGEON', dungeon_data=dungeon_data)
    
    config = get_dungeon_config(dungeon_type)
    
    text = (f"**{config['name']}**\n{config['desc']}\n\n"
            f"Вы стоите у входа. Впереди разветвление туннелей. Изучите карту на дверях.")
            
    await callback.message.edit_text(text, reply_markup=get_navigation_kb(dungeon_data), parse_mode="Markdown")

# --- 3. ШАГ ПО ГРАФУ (СЛЕДУЮЩАЯ КОМНАТА) ---
@router.callback_query(F.data.startswith("dung_go_"))
async def next_room(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    if user['state'] != 'STATE_DUNGEON':
        return await callback.answer("Вы не в подземелье!", show_alert=True)
        
    next_node_id = callback.data.replace("dung_go_", "")
    dungeon_data = user['dungeon_data']
    
    # Обновляем позицию игрока на карте
    dungeon_data["current_node"] = next_node_id
    current_room = dungeon_data["nodes"][next_node_id]
    event = current_room["type"]
    
    dungeon_config = get_dungeon_config(dungeon_data.get("dungeon_type", "solo"))
    
    if event == "combat" or event == "boss":
        if event == "boss":
            enemy_name = "ДРЕВНИЙ ХРАНИТЕЛЬ" 
            enemy_hp = 200
            dmg_min, dmg_max = 30, 45
        else:
            enemy_name = random.choice(dungeon_config['mobs']) 
            mob_stats = get_mob_by_name(enemy_name)
            enemy_hp = random.randint(mob_stats['hp_min'], mob_stats['hp_max'])
            dmg_min, dmg_max = mob_stats['dmg_min'], mob_stats['dmg_max']
            
        combat_data = {
            "enemy_name": enemy_name,
            "enemy_hp": enemy_hp, "enemy_max_hp": enemy_hp,
            "dmg_min": dmg_min, "dmg_max": dmg_max,
            "ap": 3, "player_row": "front"
        }
        
        update_user(user['user_id'], state='STATE_COMBAT', combat_data=combat_data, dungeon_data=dungeon_data)
        from handlers.combat import render_combat
        await render_combat(callback, user, combat_data, f"Из тени появляется {enemy_name}!")
        
    elif event == "treasure":
        if random.choice([True, False]):
            gold = random.randint(15, 40)
            update_user(user['user_id'], gold=user['gold'] + gold, dungeon_data=dungeon_data)
            msg = f"💰 **Тайник!** Вы нашли {gold} золота."
        else:
            inv = user['inventory']
            materials = inv.setdefault("materials", {})
            loot_id = dungeon_config['loot']
            materials[loot_id] = materials.get(loot_id, 0) + 1
            update_user(user['user_id'], inventory=inv, dungeon_data=dungeon_data)
            msg = f"✨ **Редкая находка!** Вы добыли: **{dungeon_config['loot_name']}**."
            
        await callback.message.edit_text(f"{msg}\n\nСмотрим карту дальше...", reply_markup=get_navigation_kb(dungeon_data), parse_mode="Markdown")
        
    elif event == "puzzle":
        puzzle = generate_emoji_puzzle()
        update_user(user['user_id'], state='STATE_PUZZLE', combat_data={"correct": puzzle["correct"]}, dungeon_data=dungeon_data)
        
        buttons = []
        row = []
        for opt in puzzle["options"]:
            row.append(InlineKeyboardButton(text=str(opt), callback_data=f"puzzle_ans_{opt}"))
            if len(row) == 2:
                buttons.append(row)
                row = []
        buttons.append([InlineKeyboardButton(text="💥 Разбить дверь (-20% ХП)", callback_data="puzzle_smash")])
        await callback.message.edit_text(puzzle["text"], reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")
        
    elif event == "campfire":
        heal = int(user['max_hp'] * 0.3)
        new_hp = min(user['max_hp'], user['hp'] + heal)
        update_user(user['user_id'], hp=new_hp, dungeon_data=dungeon_data)
        msg = f"🏕️ **Привал.** Вы отдохнули у костра и восстановили {heal} ХП.\n\nВпереди слышен рев Босса. Готовы?"
        await callback.message.edit_text(msg, reply_markup=get_navigation_kb(dungeon_data), parse_mode="Markdown")

# --- 4. РЕШЕНИЕ ГОЛОВОЛОМОК ---
@router.callback_query(F.data.startswith("puzzle_"))
async def solve_puzzle(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    if user['state'] != 'STATE_PUZZLE': 
        return await callback.answer("Ошибка стейта! Вы сейчас не решаете загадку.", show_alert=True)
        
    action = callback.data.replace("puzzle_", "")
    correct_ans = user.get('combat_data', {}).get("correct")
    dungeon_data = user['dungeon_data']
    
    if action == "smash":
        dmg = int(user['max_hp'] * 0.20)
        new_hp = user['hp'] - dmg
        
        if new_hp <= 0:
            update_user(user['user_id'], state='STATE_TOWN', hp=user['max_hp'], combat_data={})
            from handlers.town import get_town_kb
            return await callback.message.edit_text(
                "☠️ Вы ударили в дверь с плеча. Сработал скрытый шип и пронзил вас...",
                reply_markup=get_town_kb(), parse_mode="Markdown"
            )
        else:
            update_user(user['user_id'], state='STATE_DUNGEON', hp=new_hp, combat_data={})
            await callback.message.edit_text(
                f"💥 Вы выбили дверь с ноги! Осколки камня нанесли вам {dmg} урона.\n"
                f"❤️ Текущее ХП: {new_hp}/{user['max_hp']}\n\nСмотрим карту дальше...",
                reply_markup=get_navigation_kb(dungeon_data), parse_mode="Markdown"
            )
            
    elif action.startswith("ans_"):
        player_ans = int(action.split("_")[1])
        
        if player_ans == correct_ans:
            heal = int(user['max_hp'] * 0.15)
            new_hp = min(user['max_hp'], user['hp'] + heal)
            
            update_user(user['user_id'], state='STATE_DUNGEON', hp=new_hp, combat_data={})
            await callback.message.edit_text(
                f"✨ **Верно!** Механизм тихо щелкнул. Из ниши вырвался целебный газ (+{heal} ХП).\n"
                f"Путь свободен. Смотрим карту дальше...",
                reply_markup=get_navigation_kb(dungeon_data), parse_mode="Markdown"
            )
        else:
            dmg = int(user['max_hp'] * 0.30)
            new_hp = user['hp'] - dmg
            
            if new_hp <= 0:
                update_user(user['user_id'], state='STATE_TOWN', hp=user['max_hp'], combat_data={})
                from handlers.town import get_town_kb
                return await callback.message.edit_text(
                    "☠️ Неверный ответ. Из стен вырвалось адское пламя и сожгло вас дотла...",
                    reply_markup=get_town_kb(), parse_mode="Markdown"
                )
            else:
                update_user(user['user_id'], state='STATE_DUNGEON', hp=new_hp, combat_data={})
                await callback.message.edit_text(
                    f"❌ **Ошибка!** Магическая руна вспыхнула, обжигая вас на {dmg} урона!\n"
                    f"❤️ Текущее ХП: {new_hp}/{user['max_hp']}\n\nДверь со скрипом отворилась. Смотрим карту дальше...",
                    reply_markup=get_navigation_kb(dungeon_data), parse_mode="Markdown"
                )

# --- 5. ПОБЕГ ---
@router.callback_query(F.data == "dungeon_flee")
async def flee_dungeon(callback: CallbackQuery):
    update_user(callback.from_user.id, state='STATE_TOWN')
    from handlers.town import get_town_kb
    await callback.message.edit_text(
        "🏃‍♂️ Вы благополучно сбежали из подземелья на поверхность. Лут сохранен.", 
        reply_markup=get_town_kb(), parse_mode="Markdown"
    )
