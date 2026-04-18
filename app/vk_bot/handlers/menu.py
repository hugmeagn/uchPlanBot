"""
Хендлеры главного меню
"""
import logging
from typing import Optional

from ..vk_api.client import VkMessage
from ..keyboards.menu import get_main_menu_keyboard, get_help_keyboard
from ..keyboards.base import create_back_keyboard
from ..handlers import router
from models.user import User
from ..utils.vk_utils import format_message
from bot.utils.user_data import format_user as format_user_info

logger = logging.getLogger(__name__)


@router.command("start")
async def cmd_start(message: VkMessage, state: Optional[str], data: dict):
    """Обработчик команды /start"""
    vk = data['vk']
    user_id = message.from_id

    try:
        user = await User.get_or_none(vk_id=user_id)

        if user:
            # Существующий пользователь
            await user.fetch_related('institution')
            user_info = await format_user_info(user)

            text = (
                f"👋 Привет, {user.first_name}!\n"
                f"Добро пожаловать обратно в UchPlan!\n\n"
                f"📊 Ваш профиль:\n{user_info}\n"
                f"Выберите действие:"
            )
        else:
            # Новый пользователь
            from .profile import start_profile_setup
            await start_profile_setup(message, state, data)
            return

        await vk.send_message(
            peer_id=user_id,
            text=format_message(text),
            keyboard=get_main_menu_keyboard()
        )

    except Exception as e:
        logger.error(f"Error in start command: {e}", exc_info=True)
        await vk.send_message(
            peer_id=user_id,
            text="❌ Произошла ошибка. Попробуйте позже."
        )


@router.command("menu")
@router.callback("back_to_menu")
async def show_main_menu(message: VkMessage, state: Optional[str], data: dict):
    """Показать главное меню"""
    vk = data['vk']
    fsm = data['fsm']
    user_id = message.from_id

    # Очищаем состояние
    await fsm.clear(user_id)

    text = (
        "🏠 **Главное меню**\n\n"
        "Выберите действие:"
    )

    await vk.send_message(
        peer_id=user_id,
        text=format_message(text),
        keyboard=get_main_menu_keyboard()
    )


@router.command("help")
@router.callback("menu_help")
async def show_help(message: VkMessage, state: Optional[str], data: dict):
    """Показать помощь"""
    vk = data['vk']
    user_id = message.from_id

    help_text = (
        "🆘 **Помощь по использованию UchPlan**\n\n"
        "📋 **Основные команды:**\n"
        "• /start - Запустить бота\n"
        "• /menu - Главное меню\n"
        "• /help - Показать это сообщение\n"
        "• /profile - Настроить профиль\n"
        "• /schedule - Расписание\n"
        "• /tasks - Управление задачами\n"
        "• /plan - План на сегодня\n\n"

        "🎯 **Основные функции:**\n"
        "• **Расписание** - Просмотр пар на день/неделю\n"
        "• **Задачи** - Добавление и отслеживание дедлайнов\n"
        "• **Уведомления** - Напоминания о парах и дедлайнах\n"
        "• **План дня** - AI-помощник планирует ваш день\n\n"

        "🔧 **Если что-то не работает:**\n"
        "1. Проверьте настройки профиля (/profile)\n"
        "2. Убедитесь, что выбрано правильное учебное заведение\n"
        "3. Если проблема осталась - напишите разработчику"
    )

    await vk.send_message(
        peer_id=user_id,
        text=format_message(help_text),
        keyboard=get_help_keyboard()
    )


@router.message()
async def default_message_handler(message: VkMessage, state: Optional[str], data: dict):
    """Обработчик по умолчанию для сообщений без состояния"""
    vk = data['vk']
    user_id = message.from_id

    await vk.send_message(
        peer_id=user_id,
        text=format_message(
            "Используйте кнопки меню или команды:\n"
            "/menu - главное меню\n"
            "/help - помощь"
        ),
        keyboard=get_main_menu_keyboard()
    )
