from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def setup_profile_kb() -> InlineKeyboardMarkup:
    """
    Основная клавиатура для настройки профиля.
    """
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="Начать",
            callback_data="profile_set_role"
        )
    )

    return builder.as_markup()


def institution_list_kb() -> InlineKeyboardMarkup:
    """
    Клавиатура для работы с учебными заведениями.
    """
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="🔍 Найти заведение",
            callback_data="institution_search"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="📋 Посмотреть все доступные",
            callback_data="institution_show_all"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="↩️ Назад",
            callback_data="profile_back"
        )
    )

    return builder.as_markup()
