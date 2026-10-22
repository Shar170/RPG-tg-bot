"""Пользовательские настройки: выбор языка интерфейса."""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command

from database import get_user, update_user
from i18n import t, set_language, normalize_lang, DEFAULT_LANG
from handlers.town import generate_town_text, get_town_kb

router = Router()


def _language_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("language.ru"), callback_data="lang_set:ru")],
        [InlineKeyboardButton(text=t("language.en"), callback_data="lang_set:en")],
    ])


@router.message(Command("language"))
async def cmd_language(message: Message):
    user = get_user(message.from_user.id)
    if user and not user.get("language"):
        update_user(user["user_id"], language=DEFAULT_LANG)

    text = t("language.title", current=t("language.name")) + "\n\n" + t("language.choose")
    await message.answer(text, reply_markup=_language_kb(), parse_mode="Markdown")


@router.callback_query(F.data.startswith("lang_set:"))
async def cb_set_language(callback: CallbackQuery):
    lang = normalize_lang(callback.data.split(":", 1)[1])
    user = get_user(callback.from_user.id)
    if not user:
        return await callback.answer()

    update_user(user["user_id"], language=lang)
    # Контекст текущего update переключаем сразу, чтобы ответ был на новом языке.
    set_language(lang)

    fresh = get_user(callback.from_user.id) or user
    if fresh.get("state") == "STATE_TOWN":
        text = generate_town_text(fresh)
        try:
            await callback.message.edit_text(
                text, reply_markup=get_town_kb(fresh), parse_mode="Markdown"
            )
            update_user(fresh["user_id"], last_msg_id=callback.message.message_id)
        except Exception:
            pass
    else:
        text = t("language.title", current=t("language.name")) + "\n\n" + t(
            "language.set", language=t("language.name")
        )
        try:
            await callback.message.edit_text(text, reply_markup=_language_kb(), parse_mode="Markdown")
        except Exception:
            pass

    await callback.answer(t("language.set", language=t("language.name")))
