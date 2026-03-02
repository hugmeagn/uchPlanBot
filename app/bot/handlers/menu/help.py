# app/bot/handlers/menu/help.py

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from bot.handlers.menu.keyboards.common import back_button_kb

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("help"))
@router.message(F.text == "ℹ️ Помощь")
async def cmd_help_message(message: Message):
    """
    Обработчик для сообщений (команда /help или текст)
    """
    await show_help(message)


@router.callback_query(F.data == "menu_help")
async def cmd_help_callback(callback: CallbackQuery):
    """
    Обработчик для callback (нажатие на кнопку в меню)
    """
    # Сначала отвечаем на callback, чтобы убрать "часики" на кнопке
    await callback.answer()
    # Затем показываем помощь
    await show_help(callback.message)


async def show_help(message: Message):
    """
    Общая функция для отображения помощи
    """
    help_text = (
        "🆘 **Помощь по использованию UchPlan**\n\n"
        "📋 **Основные команды:**\n"
        "• /start - Запустить бота\n"
        "• /help - Показать это сообщение\n"
        "• /profile - Настроить профиль\n"
        "• /schedule - Показать расписание\n"
        "• /tasks - Управление задачами\n\n"

        "🎯 **Основные функции:**\n"
        "• **Расписание** - Просмотр пар на день/неделю/месяц\n"
        "• **Задачи** - Добавление и отслеживание дедлайнов\n"
        "• **Уведомления** - Напоминания о начале пар и дедлайнах\n"
        "• **Профиль** - Настройка учебного заведения и группы\n\n"

        "📱 **Главное меню:**\n"
        "Используйте кнопки меню для быстрого доступа к функциям.\n\n"

        "🔧 **Если что-то не работает:**\n"
        "1. Проверьте настройки профиля (/profile)\n"
        "2. Убедитесь, что вы выбрали правильное учебное заведение\n"
        "3. Если проблема осталась - напишите разработчику"
    )

    await message.answer(
        help_text,
        reply_markup=back_button_kb(),
    )
