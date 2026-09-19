# handlers/combat.py
import random
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database import get_user, update_user, get_item

router = Router()

def get_combat_kb(ap: int, player_row: str):
    buttons = []
    buttons.append([InlineKeyboardButton(text="🗡️ Удар (2 ОД)" if ap >= 2 else "❌ Удар (нужно 2 ОД)", callback_data="combat_act_attack")])
    move_text = "🏃 Назад (1 ОД)" if player_row == "front" else "⚔️ Вперед (1 ОД)"
    buttons.append([InlineKeyboardButton(text=move_text if ap >= 1 else "❌ Смена ряда (1 ОД)", callback_data="combat_act_move")])
    buttons.append([
        InlineKeyboardButton(text="🧪 Зелье (1 ОД)", callback_data="combat_act_potion"),
        InlineKeyboardButton(text="⏳ Завершить ход", callback_data="combat_act_end_turn")
    ])
    buttons.append([InlineKeyboardButton(text="💨 Сбежать", callback_data="combat_act_flee")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

@router.callback_query(F.data == "combat_act_attack")
async def combat_attack(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    combat = user['combat_data']
    if combat.get('ap', 0) < 2: return await callback.answer("Недостаточно ОД!", show_alert=True)
        
    combat['ap'] -= 2
    
    # Расчет урона игрока на основе оружия в инвентаре
    inv = user['inventory']
    weapon_id = inv.get("equipment", {}).get("weapon")
    weapon_dmg = get_item(weapon_id)['stats'].get('dmg', 0) if weapon_id else 0
    base_dmg = random.randint(5, 8)
    
    raw_dmg = base_dmg + weapon_dmg
    dmg = int(raw_dmg * (0.5 if combat['player_row'] == "back" else 1.0))
    
    combat['enemy_hp'] -= dmg
    
    if combat['enemy_hp'] <= 0:
        update_user(user['user_id'], state='STATE_DUNGEON', combat_data={})
        from handlers.dungeon import get_navigation_kb
        
        if not user['dungeon_data']["nodes"][user['dungeon_data']["current_node"]]["next"]:
            from handlers.town import get_town_kb
            update_user(user['user_id'], state='STATE_TOWN')
            return await callback.message.edit_text("🏆 **Рейд завершен!** Босс мертв.", reply_markup=get_town_kb(), parse_mode="Markdown")
        else:
            return await callback.message.edit_text(f"🎉 **Враг повержен!** Урон: {dmg}.\nКуда дальше?", reply_markup=get_navigation_kb(user['dungeon_data']), parse_mode="Markdown")
        
    update_user(user['user_id'], combat_data=combat)
    await render_combat(callback, user, combat, f"Вы нанесли {dmg} урона!")

@router.callback_query(F.data == "combat_act_move")
async def combat_move(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    combat = user['combat_data']
    if combat.get('ap', 0) < 1: return await callback.answer("Недостаточно ОД!", show_alert=True)
        
    combat['ap'] -= 1
    combat['player_row'] = "back" if combat['player_row'] == "front" else "front"
    update_user(user['user_id'], combat_data=combat)
    await render_combat(callback, user, combat, "Позиция изменена.")

@router.callback_query(F.data == "combat_act_end_turn")
async def combat_end_turn(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    combat = user['combat_data']
    
    # Расчет защиты игрока на основе надетой брони
    inv = user['inventory']
    armor_id = inv.get("equipment", {}).get("armor")
    armor_def = get_item(armor_id)['stats'].get('def', 0) if armor_id else 0
    
    raw_dmg = random.randint(combat['dmg_min'], combat['dmg_max'])
    row_dmg = int(raw_dmg * 0.6) if combat['player_row'] == "back" else raw_dmg
    
    # Поглощение урона броней (минимум 1 урон проходит всегда)
    monster_dmg = max(1, row_dmg - armor_def)
    new_hp = user['hp'] - monster_dmg
    
    if new_hp <= 0:
        if "khmer_amulet" in inv.get("artifacts", []):
            inv["artifacts"].remove("khmer_amulet")
            new_hp = int(user['max_hp'] * 0.25)
            combat['ap'] = 3
            update_user(user['user_id'], hp=new_hp, inventory=inv, combat_data=combat)
            await callback.answer("⚡ Амулет Жизни рассыпался и спас вас!", show_alert=True)
            return await render_combat(callback, user, combat, "Амулет спас вам жизнь!")
        else:
            update_user(user['user_id'], state='STATE_TOWN', hp=user['max_hp'], combat_data={})
            from handlers.town import get_town_kb
            return await callback.message.edit_text("☠️ **Вы пали в бою...** Лут потерян.", reply_markup=get_town_kb(), parse_mode="Markdown")
            
    combat['ap'] = 3
    update_user(user['user_id'], hp=new_hp, combat_data=combat)
    absorbed = min(armor_def, row_dmg - 1) if row_dmg > 1 else 0
    await render_combat(callback, user, combat, f"Враг ударил на {monster_dmg} урона! (Броня поглотила {absorbed})")

@router.callback_query(F.data == "combat_act_potion")
async def combat_use_potion(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    combat = user['combat_data']
    inv = user['inventory']
    
    if combat.get('ap', 0) < 1:
        return await callback.answer("Недостаточно ОД!", show_alert=True)
        
    heal_idx = -1
    potions = inv.get("potions", [])
    for i, p in enumerate(potions):
        if "Хил" in p or "рагу" in p.lower():
            heal_idx = i
            break
            
    if heal_idx == -1:
        return await callback.answer("У вас нет зелий исцеления!", show_alert=True)
        
    used_item = potions.pop(heal_idx)
    combat['ap'] -= 1
    
    heal = int(user['max_hp'] * 0.35)
    new_hp = min(user['max_hp'], user['hp'] + heal)
    
    update_user(user['user_id'], hp=new_hp, inventory=inv, combat_data=combat)
    user['hp'] = new_hp
    
    await render_combat(callback, user, combat, f"Вы использовали [{used_item}] и восстановили {heal} ХП!")

async def render_combat(callback: CallbackQuery, user: dict, combat: dict, log_msg: str):
    row_name = "Авангард 🛡️" if combat['player_row'] == "front" else "Арьергард 🏹"
    ap_icons = "🟢 " * combat['ap'] + "⚪ " * (3 - combat['ap'])
    text = (f"⚔️ **Бой: {combat['enemy_name']}**\n"
            f"❤️ Враг: {combat['enemy_hp']}/{combat['enemy_max_hp']} HP\n━━━━━━━━━━━━━━\n"
            f"👤 Вы: {user['hp']}/{user['max_hp']} HP | Ряд: {row_name}\n"
            f"⚡ ОД: {ap_icons}\n\n💬 *{log_msg}*")
    await callback.message.edit_text(text, reply_markup=get_combat_kb(combat['ap'], combat['player_row']), parse_mode="Markdown")

@router.callback_query(F.data == "combat_act_flee")
async def combat_flee(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    update_user(user['user_id'], state='STATE_TOWN', combat_data={})
    from handlers.town import get_town_kb
    await callback.message.edit_text("🏃‍♂️ Вы сбежали из боя в лагерь!", reply_markup=get_town_kb(), parse_mode="Markdown")
