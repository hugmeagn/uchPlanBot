from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_schedule_main_keyboard() -> InlineKeyboardMarkup:
    """
    Главное меню расписания с выбором периода.
    """
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="📅 Сегодня", callback_data="schedule:today"),
        InlineKeyboardButton(text="📅 Завтра", callback_data="schedule:tomorrow"),
        width=2
    )

    builder.row(
        InlineKeyboardButton(text="📅 Текущая неделя", callback_data="schedule:week_current"),
        width=1
    )

    builder.row(
        InlineKeyboardButton(text="📅 Следующая неделя", callback_data="schedule:week_next"),
        width=1
    )

    builder.row(
        InlineKeyboardButton(text="◀️ В главное меню", callback_data="main_menu"),
        width=1
    )

    return builder.as_markup()


def get_error_keyboard() -> InlineKeyboardMarkup:
    """
    Клавиатура для сообщений об ошибке.
    """
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="🔄 Попробовать снова", callback_data="schedule:main"),
        InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu"),
        width=2
    )

    return builder.as_markup()
