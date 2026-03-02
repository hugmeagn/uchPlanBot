# app/bot/handlers/profile/profile.py

"""
Обработчики настройки и управления профилем пользователя.
"""
import logging
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from models.user import User
from bot.utils.user_data import format_user

from bot.handlers.menu.keyboards.common import back_button_kb
from bot.handlers.settings.keyboards.settings import settings_kb

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("profile"))
@router.message(F.text == "⚙️ Настройки профиля")
async def cmd_profile_message(message: Message):
    """
    Обработчик для сообщений (команда /profile или текст)
    """
    logger.info(f"Profile command from user {message.from_user.id}")
    await show_profile(message.from_user.id, message)


@router.callback_query(F.data == "menu_settings")
async def cmd_profile_callback(callback: CallbackQuery):
    """
    Обработчик для callback (нажатие на кнопку в меню)
    """
    # ВАЖНО: В callback всегда используем callback.from_user.id
    user_id = callback.from_user.id
    logger.info(f"Profile callback from user {user_id}")

    # Сначала отвечаем на callback, чтобы убрать "часики" на кнопке
    await callback.answer()

    # Затем показываем профиль, используя ID из callback
    await show_profile(user_id, callback.message)


async def show_profile(user_id: int, message: Message):
    """
    Общая функция для отображения профиля

    Args:
        user_id: ID пользователя Telegram
        message: Сообщение для ответа
    """
    logger.info(f"Looking for user with telegram_id: {user_id} (type: {type(user_id)})")

    # Пробуем найти пользователя
    user = await User.get_or_none(telegram_id=user_id)

    if not user:
        # Если не нашли, пробуем найти по строке
        user = await User.get_or_none(telegram_id=str(user_id))

    if not user:
        logger.warning(f"User not found: {user_id}")

        # Проверим, есть ли вообще пользователи в БД
        all_users = await User.all()
        logger.info(f"Total users in DB: {len(all_users)}")
        for u in all_users:
            logger.info(f"DB user: id={u.id}, telegram_id={u.telegram_id} (type: {type(u.telegram_id)})")

        await message.answer(
            "❌ **Профиль не найден!**\n\n"
            f"Ваш Telegram ID: `{user_id}`\n\n"
            "Возможные причины:\n"
            "• Вы еще не запускали бота командой /start\n"
            "• Произошла ошибка при регистрации\n\n"
            "**Решение:**\n"
            "Нажмите /start чтобы создать новый профиль",
            parse_mode="Markdown",
            reply_markup=back_button_kb()
        )
        return

    logger.info(f"User found: {user.id}, role={user.role}, group={user.group}")

    await message.answer(
        f"⚙️ **Настройки профиля**\n\n"
        f"Текущие данные:\n" +
        await format_user(user) +
        f"Выберите, что хотите изменить:",
        parse_mode="Markdown",
        reply_markup=settings_kb(),
    )


async def unconfigured_profile(message: Message):
    await message.answer(
        "❌ Сначала настройте профиль!\n"
        "Используйте команду /profile или нажмите '⚙️ Настройки профиля'",
        reply_markup=back_button_kb()
    )
