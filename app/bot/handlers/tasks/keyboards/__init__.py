"""
Клавиатуры для задач
"""
from typing import List
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from services.tasks.service import Task, TaskStatus


def get_tasks_main_keyboard(show_back: bool = True) -> InlineKeyboardMarkup:
    """
    Главное меню задач
    """
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="📋 Список задач", callback_data="tasks_list"),
        InlineKeyboardButton(text="📊 Статистика", callback_data="tasks_stats")
    )

    builder.row(
        InlineKeyboardButton(text="➕ Новая задача", callback_data="tasks_new"),
        InlineKeyboardButton(text="⏰ На сегодня", callback_data="tasks_today")
    )

    builder.row(
        InlineKeyboardButton(text="⚠️ Просроченные", callback_data="tasks_overdue"),
        width=1
    )

    if show_back:
        builder.row(
            InlineKeyboardButton(text="◀️ В главное меню", callback_data="back_to_menu"),
            width=1
        )

    return builder.as_markup()


async def get_tasks_pagination_keyboard(
    tasks: List[Task],
    current_page: int,
    total_pages: int
) -> InlineKeyboardMarkup:
    """
    Клавиатура со списком задач и пагинацией
    """
    builder = InlineKeyboardBuilder()

    # Кнопки для каждой задачи
    for task in tasks[:5]:  # Показываем не больше 5 задач
        status_emoji = "✅" if task.status == TaskStatus.COMPLETED else "📌"
        title = task.title[:25] + "..." if len(task.title) > 25 else task.title

        builder.row(
            InlineKeyboardButton(
                text=f"{status_emoji} {title}",
                callback_data=f"task_view_{task.id}"
            )
        )

    # Кнопки пагинации
    if total_pages > 1:
        pagination_buttons = []

        if current_page > 0:
            pagination_buttons.append(
                InlineKeyboardButton(
                    text="◀️",
                    callback_data=f"tasks_page_{current_page - 1}"
                )
            )

        pagination_buttons.append(
            InlineKeyboardButton(
                text=f"{current_page + 1}/{total_pages}",
                callback_data="tasks_current"
            )
        )

        if current_page < total_pages - 1:
            pagination_buttons.append(
                InlineKeyboardButton(
                    text="▶️",
                    callback_data=f"tasks_page_{current_page + 1}"
                )
            )

        builder.row(*pagination_buttons)

    # Кнопки действий
    builder.row(
        InlineKeyboardButton(text="➕ Новая", callback_data="tasks_new"),
        InlineKeyboardButton(text="📊 Статистика", callback_data="tasks_stats"),
        width=2
    )

    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="tasks_main"),
        InlineKeyboardButton(text="🏠 Меню", callback_data="back_to_menu"),
        width=2
    )

    return builder.as_markup()


def get_task_detail_keyboard(task_id: str, is_completed: bool = False) -> InlineKeyboardMarkup:
    """
    Клавиатура для детального просмотра задачи
    """
    builder = InlineKeyboardBuilder()

    if not is_completed:
        builder.row(
            InlineKeyboardButton(text="✅ Выполнено", callback_data=f"task_done_{task_id}"),
            InlineKeyboardButton(text="⏰ Напомнить", callback_data=f"task_postpone_{task_id}")
        )

    builder.row(
        InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"task_edit_{task_id}"),
        InlineKeyboardButton(text="🗑 Удалить", callback_data=f"task_delete_{task_id}"),
        width=2
    )

    builder.row(
        InlineKeyboardButton(text="◀️ К списку", callback_data="tasks_list"),
        InlineKeyboardButton(text="🏠 Меню", callback_data="back_to_menu"),
        width=2
    )

    return builder.as_markup()


def get_priority_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура для выбора приоритета"""
    builder = ReplyKeyboardBuilder()
    builder.add(
        KeyboardButton(text="Низкий"),
        KeyboardButton(text="Средний"),
        KeyboardButton(text="Высокий"),
        KeyboardButton(text="Критичный")
    )
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)


def get_category_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура для выбора категории"""
    builder = ReplyKeyboardBuilder()
    categories = [
        "📚 Учеба",
        "🏠 Домашнее задание",
        "📝 Экзамен",
        "💼 Проект",
        "👤 Личное",
        "📦 Другое"
    ]
    for name in categories:
        builder.add(KeyboardButton(text=name))
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)


def get_confirm_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура подтверждения"""
    builder = ReplyKeyboardBuilder()
    builder.add(
        KeyboardButton(text="✅ Да, создать"),
        KeyboardButton(text="❌ Отмена")
    )
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)
