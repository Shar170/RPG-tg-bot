import asyncio
from aiogram import Bot, Dispatcher, BaseMiddleware, F
from aiogram.types import TelegramObject, CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from config import BOT_TOKEN
from database import init_db, seed_all, get_user, update_user, check_and_notify_regen, check_inactivity_notifications, mark_user_active, flush_logs

# ИМПОРТИРУЕМ ВСЕ ХЕНДЛЕРЫ, включая новый admin
from handlers import town, dungeon, combat, alchemy, inventory, craft, minigames, market, arena, collection, trading_post, admin
from handlers.clans import router as clans_router

# Перехватчик активности (обновляет время последнего онлайна)
class ActivityMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: TelegramObject, data: dict):
        user_id = None
        if isinstance(event, Message):
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id
            
        if user_id:
            mark_user_active(user_id)
            
        return await handler(event, data)

# Защитник от устаревших кнопок
class AntiCheeseMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: TelegramObject, data: dict):
        if isinstance(event, CallbackQuery) and event.data == "hide_notification":
            return await handler(event, data)
            
        if isinstance(event, CallbackQuery):
            # Пропускаем чит-кнопки админа через проверку "устаревших сообщений"
            if event.data.startswith("adm_"):
                return await handler(event, data)
                
            user = get_user(event.from_user.id)
            if user:
                if user.get('last_msg_id', 0) != 0 and event.message.message_id != user['last_msg_id']:
                    try:
                        await event.message.delete()
                    except:
                        pass
                    await event.answer("⚠️ Это меню устарело. Используйте актуальное сообщение ниже.", show_alert=True)
                    return 

        elif isinstance(event, Message) and event.text in ["/start", "/town"]:
            user = get_user(event.from_user.id)
            if user and user.get('state') in ['STATE_ARENA_QUEUE', 'STATE_PVP', 'STATE_FSM']:
                await event.answer("⚠️ Завершите текущее действие (бой или ввод текста)!")
                return

        return await handler(event, data)

# Фоновый воркер
async def regen_notifier_worker(bot: Bot):
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Скрыть", callback_data="hide_notification")]])
    while True:
        await asyncio.sleep(60) 
        try:
            # Сбрасываем буфер аналитики в базу каждую минуту
            flush_logs()
            
            # 1. Рассылка пушей о здоровье и энергии
            notifications = check_and_notify_regen()
            for notif in notifications:
                if notif['type'] == 'hp':
                    text = "❤️ **Здоровье полностью восстановлено!**\nВы готовы к новым экспедициям."
                else:
                    text = "⚡ **Энергия полностью восстановлена!**\nСамое время отправиться в рейд."
                
                try:
                    await bot.send_message(notif['user_id'], text, reply_markup=kb, parse_mode="Markdown")
                except Exception:
                    pass
                await asyncio.sleep(0.05)
                
            # 2. Рассылка возвращающих пушей для оффлайн-игроков
            inact_notifs = check_inactivity_notifications()
            for notif in inact_notifs:
                days = notif['days']
                if days == 2:
                    text = "🏕️ **Герой, Камария нуждается в тебе!**\nМонстры начинают подбираться к лагерю. Возвращайтесь!"
                elif days == 5:
                    text = "🔥 **Ваш костер почти погас...**\nВ подземельях накопилось много нетронутых сокровищ и лутбоксов!"
                elif days == 17:
                    text = "🛡️ **Клан и друзья скучают по вам.**\nВозвращайтесь, пока ржавчина окончательно не съела ваш меч!"
                elif days == 31:
                    text = "📜 **Спустя месяц вашего отсутствия...**\nБарды сложили о вас легенду. Но, может, это еще не конец?"
                else:
                    text = "Заходи в игру!"

                try:
                    await bot.send_message(notif['user_id'], text, reply_markup=kb, parse_mode="Markdown")
                except Exception:
                    pass
                await asyncio.sleep(0.05)

        except Exception as e:
            print(f"Ошибка в воркере: {e}")

async def main():
    init_db()
    seed_all()
    
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    
    # Регистрируем Middleware
    dp.update.outer_middleware(ActivityMiddleware())
    dp.message.outer_middleware(AntiCheeseMiddleware())
    dp.callback_query.outer_middleware(AntiCheeseMiddleware())
    
    @dp.callback_query(F.data == "hide_notification")
    async def hide_notification_cb(callback: CallbackQuery):
        try:
            await callback.message.delete()
        except:
            pass
        await callback.answer()
    
    # РЕГИСТРАЦИЯ РОУТЕРОВ
    dp.include_router(admin.router) # <--- Роутер чит-меню
    dp.include_router(town.router)
    dp.include_router(minigames.router)
    dp.include_router(dungeon.router)
    dp.include_router(combat.router)
    dp.include_router(alchemy.router)
    dp.include_router(inventory.router)
    dp.include_router(craft.router)
    dp.include_router(market.router)
    dp.include_router(arena.router)
    dp.include_router(collection.router)
    dp.include_router(trading_post.router)
    dp.include_router(clans_router)
    
    asyncio.create_task(regen_notifier_worker(bot))
    
    print("Бот успешно запущен!")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
