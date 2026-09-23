import asyncio
from aiogram import Bot, Dispatcher, BaseMiddleware
from aiogram.types import TelegramObject, CallbackQuery, Message
from config import BOT_TOKEN
from database import init_db, seed_all, get_user, update_user

# Импортируем все хендлеры
from handlers import town, dungeon, combat, alchemy, inventory, craft, minigames, market, arena
from handlers.clans import router as clans_router

# Глобальный защитник от "чизинга" старыми кнопками
class AntiCheeseMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: TelegramObject, data: dict):
        if isinstance(event, CallbackQuery):
            user = get_user(event.from_user.id)
            if user:
                # Если у нас записан ID активного сообщения, и клик пришел не из него
                if user.get('last_msg_id', 0) != 0 and event.message.message_id != user['last_msg_id']:
                    try:
                        await event.message.delete() # Удаляем читерское старое сообщение
                    except:
                        pass
                    await event.answer("⚠️ Это меню устарело. Используйте актуальное сообщение ниже.", show_alert=True)
                    return # Блокируем дальнейшее выполнение

        elif isinstance(event, Message) and event.text in ["/start", "/town"]:
            user = get_user(event.from_user.id)
            # Блокируем вызов нового меню, если игрок в очереди или в ПВП
            if user and user.get('state') in ['STATE_ARENA_QUEUE', 'STATE_PVP']:
                await event.answer("⚔️ Вы находитесь на Арене! Завершите бой или отмените поиск.")
                return

        return await handler(event, data)


async def main():
    init_db()
    seed_all()
    
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    
    # Подключаем защиту от чизинга на все callback'и и сообщения
    dp.message.outer_middleware(AntiCheeseMiddleware())
    dp.callback_query.outer_middleware(AntiCheeseMiddleware())
    
    dp.include_router(town.router)
    dp.include_router(minigames.router)
    dp.include_router(dungeon.router)
    dp.include_router(combat.router)
    dp.include_router(alchemy.router)
    dp.include_router(inventory.router)
    dp.include_router(craft.router)
    dp.include_router(market.router)
    dp.include_router(arena.router) # НОВОЕ: Модуль Арены
    dp.include_router(clans_router)
    
    print("Бот успешно запущен!")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

