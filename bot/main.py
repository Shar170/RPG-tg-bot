import asyncio
from weakref import WeakValueDictionary
from aiogram import Bot, Dispatcher, BaseMiddleware, F
from aiogram.types import (
    TelegramObject, Update, CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton,
    BotCommand, BotCommandScopeDefault,
)
from config import BOT_TOKEN
from database import (
    init_db, seed_all, get_user, update_user, check_and_notify_regen,
    check_inactivity_notifications, mark_user_active, track_daily_visit,
    flush_logs, get_user_language,
)
from i18n import (
    t, set_language, reset_language, DEFAULT_LANG,
)

# ИМПОРТИРУЕМ ВСЕ ХЕНДЛЕРЫ, включая новый story
from handlers import (
    town, dungeon, combat, alchemy, inventory, craft, minigames, market,
    arena, collection, trading_post, admin, story, settings,
)
from handlers.clans import router as clans_router

def _inner_event(event: TelegramObject) -> TelegramObject:
    """На уровне dp.update приходит Update, внутри него — Message/CallbackQuery."""
    if isinstance(event, Update):
        try:
            return event.event
        except Exception:
            return event
    return event


class UserActionLockMiddleware(BaseMiddleware):
    """Serialize a player's updates, including duplicate callbacks.

    A single bot process must own polling; this lock does not span processes.
    """
    def __init__(self):
        self._locks = WeakValueDictionary()

    async def __call__(self, handler, event: TelegramObject, data: dict):
        user = getattr(_inner_event(event), 'from_user', None)
        if not user:
            return await handler(event, data)
        lock = self._locks.get(user.id)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[user.id] = lock
        async with lock:
            return await handler(event, data)

# Язык текущего update. Должен регистрироваться первым (самый внешний слой).
class LanguageMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: TelegramObject, data: dict):
        inner = _inner_event(event)
        from_user = getattr(inner, "from_user", None)
        lang = DEFAULT_LANG
        if from_user:
            lang = get_user_language(from_user.id) or DEFAULT_LANG

        token = set_language(lang)
        try:
            return await handler(event, data)
        finally:
            reset_language(token)

# Перехватчик активности (обновляет время последнего онлайна)
class ActivityMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: TelegramObject, data: dict):
        inner = _inner_event(event)
        user_id = None
        if isinstance(inner, Message) and inner.from_user:
            user_id = inner.from_user.id
        elif isinstance(inner, CallbackQuery):
            user_id = inner.from_user.id
            
        if user_id:
            mark_user_active(user_id)
            try:
                track_daily_visit(user_id)
            except Exception as exc:
                # Визит не должен ломать обработку update.
                print(f"Ошибка учёта ежедневного визита: {exc}")
            
        return await handler(event, data)

# Защитник от устаревших кнопок
class AntiCheeseMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: TelegramObject, data: dict):
        if isinstance(event, CallbackQuery) and event.data == "hide_notification":
            return await handler(event, data)
            
        if isinstance(event, CallbackQuery):
            # Пропускаем чит-кнопки админа и переключатель языка:
            # они могут приходить из отдельного сообщения /language.
            if event.data and (event.data.startswith("adm_") or event.data.startswith("lang_set:")):
                return await handler(event, data)
                
            user = get_user(event.from_user.id)
            if user:
                if user.get('last_msg_id', 0) != 0 and event.message and event.message.message_id != user['last_msg_id']:
                    try:
                        await event.message.delete()
                    except:
                        pass
                    await event.answer(t("anti_cheese.stale"), show_alert=True)
                    return 

        elif isinstance(event, Message) and event.text in ["/start", "/town"]:
            user = get_user(event.from_user.id)
            if user and user.get('state') in ['STATE_ARENA_QUEUE', 'STATE_PVP', 'STATE_FSM']:
                await event.answer(t("anti_cheese.busy"))
                return

        return await handler(event, data)

def _hide_notification_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t("notify.hide", lang=lang), callback_data="hide_notification")
    ]])

# Фоновый воркер
async def regen_notifier_worker(bot: Bot):
    while True:
        await asyncio.sleep(60) 
        try:
            # Сбрасываем буфер аналитики в базу каждую минуту
            flush_logs()
            
            # 1. Рассылка пушей о здоровье и энергии
            notifications = check_and_notify_regen()
            for notif in notifications:
                lang = get_user_language(notif['user_id']) or DEFAULT_LANG
                if notif['type'] == 'hp':
                    text = t("notify.hp_restored", lang=lang)
                else:
                    text = t("notify.energy_restored", lang=lang)
                
                try:
                    await bot.send_message(notif['user_id'], text, reply_markup=_hide_notification_kb(lang), parse_mode="Markdown")
                except Exception:
                    pass
                await asyncio.sleep(0.05)
                
            # 2. Рассылка возвращающих пушей для оффлайн-игроков
            inact_notifs = check_inactivity_notifications()
            for notif in inact_notifs:
                lang = get_user_language(notif['user_id']) or DEFAULT_LANG
                days = notif['days']
                if days == 2:
                    text = t("notify.inactive_2", lang=lang)
                elif days == 5:
                    text = t("notify.inactive_5", lang=lang)
                elif days == 17:
                    text = t("notify.inactive_17", lang=lang)
                elif days == 31:
                    text = t("notify.inactive_31", lang=lang)
                else:
                    text = t("notify.inactive_other", lang=lang)

                try:
                    await bot.send_message(notif['user_id'], text, reply_markup=_hide_notification_kb(lang), parse_mode="Markdown")
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
    
    # Регистрируем Middleware. Language — самым внешним слоем.
    dp.update.outer_middleware(UserActionLockMiddleware())
    dp.update.outer_middleware(LanguageMiddleware())
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
    dp.include_router(story.router) # <--- СЮЖЕТНЫЙ РОУТЕР
    dp.include_router(settings.router)
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

    # Список команд для обоих языков
    try:
        for lang in ("ru", "en"):
            await bot.set_my_commands(
                [
                    BotCommand(command="start", description=t("cmd.start", lang=lang)),
                    BotCommand(command="town", description=t("cmd.town", lang=lang)),
                    BotCommand(command="online", description=t("cmd.online", lang=lang)),
                    BotCommand(command="language", description=t("language.command", lang=lang)),
                ],
                scope=BotCommandScopeDefault(),
                language_code=lang,
            )
    except Exception as exc:
        print(f"Не удалось обновить список команд: {exc}")
    
    print("Бот успешно запущен!")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

