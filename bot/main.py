import asyncio
from aiogram import Bot, Dispatcher
from config import BOT_TOKEN
from database import init_db, seed_all

# Импортируем все хендлеры, ВКЛЮЧАЯ MINIGAMES
from handlers import town, dungeon, combat, alchemy, inventory, craft, minigames 
from handlers.clans import router as clans_router


async def main():
    init_db()
    seed_all()
    
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    
    dp.include_router(town.router)
    dp.include_router(minigames.router) # НОВОЕ
    dp.include_router(dungeon.router)
    dp.include_router(combat.router)
    dp.include_router(alchemy.router)
    dp.include_router(inventory.router)
    dp.include_router(craft.router)
    dp.include_router(clans_router)
    
    print("Бот успешно запущен!")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
