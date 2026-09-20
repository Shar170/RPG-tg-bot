import asyncio
from aiogram import Bot, Dispatcher
from config import BOT_TOKEN
from database import init_db, seed_all
from handlers import town, dungeon, combat, alchemy, inventory, craft

async def main():
    init_db()
    seed_all() 
    
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    
    dp.include_router(town.router)
    dp.include_router(dungeon.router)
    dp.include_router(combat.router)
    dp.include_router(alchemy.router)
    dp.include_router(inventory.router)
    dp.include_router(craft.router)
    
    print("Сервер запущен. Бот активен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

