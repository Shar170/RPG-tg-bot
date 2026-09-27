from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from database import get_user, update_user, get_connection, get_player_max_energy, roll_card, give_item

router = Router()

# Ваш Telegram ID
ADMIN_ID = 243702559

def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID

def get_admin_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❤️ Фулл ХП", callback_data="adm_hp"),
         InlineKeyboardButton(text="⚡ Фулл Энергия", callback_data="adm_en")],
        [InlineKeyboardButton(text="💰 +10k Золота", callback_data="adm_gold"),
         InlineKeyboardButton(text="💎 +1,000 Алмазов", callback_data="adm_gems")],
        [InlineKeyboardButton(text="✨ +10k XP (Level Up)", callback_data="adm_xp")],
        [InlineKeyboardButton(text="🎴 Дать 5 Карт", callback_data="adm_cards"),
         InlineKeyboardButton(text="📦 Дать Эпик шмот/ресы", callback_data="adm_items")],
        [InlineKeyboardButton(text="🔄 Сбросить КД и Дейлики", callback_data="adm_reset")],
        [InlineKeyboardButton(text="💣 ФУЛЛ СБРОС АККАУНТА", callback_data="adm_wipe_ask")]
    ])

@router.message(Command("admin", "cheat"))
async def cmd_admin(message: Message):
    if not is_admin(message.from_user.id):
        return # Игнорируем простых смертных
    await message.answer("🛠 **Панель Разработчика**", reply_markup=get_admin_kb(), parse_mode="Markdown")

@router.callback_query(F.data.startswith("adm_"))
async def admin_callbacks(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return await callback.answer("⛔ Отказано в доступе.", show_alert=True)
        
    action = callback.data.replace("adm_", "")
    user = get_user(callback.from_user.id)
    
    # Защита от краша, если админ уже удалил аккаунт, но жмет кнопки
    if not user and action not in ["wipe_ask", "wipe_cancel", "wipe_do"]:
        return await callback.answer("Сначала напишите /start", show_alert=True)
    
    if action == "hp":
        update_user(user['user_id'], hp=user['max_hp'])
        await callback.answer("❤️ ХП полностью восстановлено!")
        
    elif action == "en":
        max_e = get_player_max_energy(user.get('level', 1))
        update_user(user['user_id'], energy=max_e)
        await callback.answer("⚡ Энергия полностью восстановлена!")
        
    elif action == "gold":
        update_user(user['user_id'], gold=user['gold'] + 10000)
        await callback.answer("💰 Выдано 10,000 Золота!")
        
    elif action == "gems":
        update_user(user['user_id'], gems=user.get('gems', 0) + 1000)
        await callback.answer("💎 Выдано 1,000 Алмазов!")
        
    elif action == "xp":
        user['xp'] += 10000
        lvl_up = 0
        # Прокручиваем уровни, если XP хватает на несколько сразу
        while user['xp'] >= user.get('level', 1) * 100:
            user['xp'] -= user.get('level', 1) * 100
            user['level'] += 1
            user['max_hp'] += 15
            lvl_up += 1
        user['hp'] = user['max_hp']
        update_user(user['user_id'], xp=user['xp'], level=user['level'], max_hp=user['max_hp'], hp=user['hp'])
        await callback.answer(f"✨ +10,000 XP! Получено уровней: {lvl_up}")
        
    elif action == "cards":
        msg = "🎴 **Выданы тестовые карты:**\n"
        for _ in range(5):
            c = roll_card(user['user_id'])
            if c: msg += f"{c['emoji']} {c['name']} ({c['rarity']})\n"
        await callback.message.answer(msg, parse_mode="Markdown")
        await callback.answer()
        
    elif action == "items":
        give_item(user['user_id'], "god_slayer", "weapon", 1)
        give_item(user['user_id'], "titan_fortress", "armor", 1)
        give_item(user['user_id'], "epic_token", "material", 20)
        inv = user.get('inventory', {})
        inv.setdefault("potions", []).extend(["Сытное рагу"] * 10)
        inv.setdefault("potions", []).extend(["Зелье: Хил"] * 10)
        update_user(user['user_id'], inventory=inv)
        await callback.answer("📦 Выдана топ-экипировка, 20 эпик токенов и 20 зелий!")
        
    elif action == "reset":
        # Сбрасываем таймеры и квесты
        update_user(
            user['user_id'], 
            last_energy_time=0, 
            last_hp_time=0, 
            quests_data={}, 
            notified_hp=0, 
            notified_energy=0,
            pity_counter=0
        )
        await callback.answer("🔄 Таймеры сброшены! Дейлики можно взять заново.")
        
    elif action == "wipe_ask":
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💥 ДА, УДАЛИТЬ МОЙ АККАУНТ", callback_data="adm_wipe_do")],
            [InlineKeyboardButton(text="❌ ОТМЕНА", callback_data="adm_wipe_cancel")]
        ])
        await callback.message.edit_text(
            "⚠️ **ВЫ УВЕРЕНЫ?**\n"
            "Это **ПОЛНОСТЬЮ** удалит вашего персонажа из базы данных (золото, уровни, инвентарь, карточки). "
            "Вам придется писать `/start` заново.", 
            reply_markup=kb, parse_mode="Markdown"
        )
        
    elif action == "wipe_cancel":
        await callback.message.edit_text("🛠 **Панель Разработчика**", reply_markup=get_admin_kb(), parse_mode="Markdown")
        
    elif action == "wipe_do":
        with get_connection() as conn:
            cur = conn.cursor()
            # Жесткое удаление всех следов админа
            cur.execute("DELETE FROM users WHERE user_id = ?", (ADMIN_ID,))
            cur.execute("DELETE FROM user_cards WHERE user_id = ?", (ADMIN_ID,))
            cur.execute("DELETE FROM user_boxes WHERE user_id = ?", (ADMIN_ID,))
            cur.execute("DELETE FROM arena_queue WHERE user_id = ?", (ADMIN_ID,))
            
            # Если админ был лидером клана - снимаем его с должности
            cur.execute("UPDATE clans SET leader_id = 0 WHERE leader_id = ?", (ADMIN_ID,))
            conn.commit()
            
        await callback.message.edit_text("✅ **Аккаунт полностью уничтожен.** \n\nНапишите `/start` для создания нового персонажа.", parse_mode="Markdown")
