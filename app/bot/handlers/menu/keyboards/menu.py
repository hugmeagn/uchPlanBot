"""
Основные меню и навигационные клавиатуры.
"""
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder


def main_menu_kb() -> InlineKeyboardMarkup:
    """
    Основное меню бота с добавленным планировщиком
    """
    builder = InlineKeyboardBuilder()

    # Первый ряд: План на сегодня (НОВЫЙ!)
    builder.row(
        InlineKeyboardButton(
            text="🌅 План на сегодня",
            callback_data="menu_plan_today"
        ),
        width=1
    )

    # Второй ряд: Расписание
    builder.row(
        InlineKeyboardButton(
            text="📚 Расписание",
            callback_data="menu_schedule"
        ),
        width=1
    )

    # Третий ряд: Задачи
    builder.row(
        InlineKeyboardButton(
            text="📋 Мои задачи",
            callback_data="menu_tasks"
        ),
        InlineKeyboardButton(
            text="➕ Добавить задачу",
            callback_data="menu_add_task"
        ),
        width=2
    )

    # Четвертый ряд: Статистика и уведомления
    builder.row(
        InlineKeyboardButton(
            text="📊 Статистика задач",
            callback_data="menu_task_stats"
        ),
        InlineKeyboardButton(
            text="🔔 Уведомления",
            callback_data="menu_notifications"
        ),
        width=2
    )

    # Пятый ряд: Быстрые фильтры
    builder.row(
        InlineKeyboardButton(
            text="⏰ На сегодня",
            callback_data="menu_today"
        ),
        InlineKeyboardButton(
            text="⚠️ Просроченные",
            callback_data="menu_overdue"
        ),
        width=2
    )

    # Шестой ряд: Настройки и помощь
    builder.row(
        InlineKeyboardButton(
            text="⚙️ Настройки профиля",
            callback_data="menu_settings"
        ),
        InlineKeyboardButton(
            text="ℹ️ Помощь",
            callback_data="menu_help"
        ),
        width=2
    )

    return builder.as_markup()


def back_to_menu_kb() -> InlineKeyboardMarkup:
    """
    Клавиатура с кнопкой возврата в главное меню.
    """
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="↩️ В главное меню", callback_data="back_to_menu")
    )

    return builder.as_markup()
