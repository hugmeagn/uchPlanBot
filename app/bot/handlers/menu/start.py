import logging

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.handlers.menu.keyboards.menu import main_menu_kb
from bot.handlers.profile.keyboards.setup import setup_profile_kb
from models.user import User
from bot.utils.user_data import format_user

logger = logging.getLogger(__name__)
router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """
    Обработчик команды /start.
    Проверяет, есть ли пользователь в базе и показывает соответствующее меню.
    """

    try:
        # Пытаемся найти пользователя
        user = await User.get_or_none(telegram_id=message.from_user.id)

        if user:
            # Профиль полностью настроен - показываем главное меню
            await message.answer(
                f"👋 Привет, {user.first_name}!\n"
                f"Добро пожаловать обратно в UchPlan!\n\n"
                f"📊 Ваш профиль:\n" +
                await format_user(user) +
                f"Выберите действие:",
                reply_markup=main_menu_kb()
            )
        else:
            # Новый пользователь

            await message.answer(
                "👋 Добро пожаловать в UchPlan!\n\n"
                "Я помогу вам:\n"
                "📅 Следить за расписанием занятий\n"
                "✅ Управлять учебными задачами\n"
                "⏰ Получать напоминания о парах и дедлайнах\n\n"
                "Для начала давайте настроим ваш профиль:",
                reply_markup=setup_profile_kb()
            )
            await state.set_state("profile_setup")

    except Exception as e:
        logger.error(f"Ошибка в команде /start:", exc_info=True)
        await message.answer(
            "😔 Произошла ошибка. Попробуйте еще раз или обратитесь к администратору."
        )
