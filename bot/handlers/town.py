# handlers/town.py
import json
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from database import get_user, update_user, get_connection

router = Router()

def get_town_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚔️ Доска Рейдов", callback_data="town_raids")],
        [InlineKeyboardButton(text="🎒 Инвентарь", callback_data="inv_open"),
         InlineKeyboardButton(text="🧪 Алхимия", callback_data="town_alchemy")],
        [InlineKeyboardButton(text="🏡 Мой Дом", callback_data="town_home")]
    ])

@router.message(Command("start"))
async def start_game(message: Message):
    user = get_user(message.from_user.id)
    if not user:
        with get_connection() as conn:
            cursor = conn.cursor()
            
            # Выдаем стартовый набор экипировки и еды
            inv = json.dumps({
                "potions": ["Сытное рагу (Курица и Кабачки)", "Зелье: Хил", "Зелье: Хил"],
                "materials": {},
                "artifacts": ["khmer_amulet"],
                "equipment": {"weapon": "wood_sword", "armor": "leather_armor"},
                "backpack": []
            }, ensure_ascii=False)
            
            home = json.dumps({"trophies": [], "cosmetics": "Котелок с рагу"}, ensure_ascii=False)
            
            cursor.execute(
                "INSERT INTO users (user_id, username, state, hp, max_hp, gold, inventory, home_data) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (message.from_user.id, message.from_user.username, 'STATE_TOWN', 100, 100, 50, inv, home)
            )
            conn.commit()
    else:
        update_user(message.from_user.id, state='STATE_TOWN')
    
    await message.answer(
        "🏰 **Центральный Лагерь**\nЗдесь безопасно. Вы можете торговать, крафтить или отправиться в рейд.",
        reply_markup=get_town_kb(), parse_mode="Markdown"
    )

@router.callback_query(F.data == "town_home")
async def show_home(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    home_data = user['home_data']
    
    text = (f"🏡 **Дом игрока {user['username']}**\n\n"
            f"🏺 **Уют:** {home_data.get('cosmetics', 'Пусто')}\n"
            f"🏆 **Трофеи:** В разработке...\n\n"
            f"Отличное место, чтобы собраться с мыслями.")
            
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="town_back")]])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data == "town_back")
async def back_to_town(callback: CallbackQuery):
    await callback.message.edit_text("🏰 **Центральный Лагерь**", reply_markup=get_town_kb(), parse_mode="Markdown")
