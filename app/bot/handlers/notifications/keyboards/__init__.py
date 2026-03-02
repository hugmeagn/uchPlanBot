"""
Клавиатуры для уведомлений
"""
from typing import List
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_notifications_main_keyboard(show_back: bool = True) -> InlineKeyboardMarkup:
    """
    Главное меню уведомлений
    """
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="🔔 Показать уведомления", callback_data="notifications_list"),
        InlineKeyboardButton(text="⚙️ Настройки", callback_data="notifications_settings"),
        width=2
    )

    builder.row(
        InlineKeyboardButton(text="🗑 Очистить все", callback_data="notif_clear_all"),
        width=1
    )

    if show_back:
        builder.row(
            InlineKeyboardButton(text="◀️ В главное меню", callback_data="back_to_menu"),
            width=1
        )

    return builder.as_markup()


def get_notifications_list_keyboard(
    notifications: List,
    current_page: int,
    total_pages: int
) -> InlineKeyboardMarkup:
    """
    Клавиатура со списком уведомлений и пагинацией
    """
    builder = InlineKeyboardBuilder()

    # Кнопки для каждого уведомления
    for notif in notifications[:5]:
        status_emoji = "✅" if notif.status == "sent" or notif.status == "delivered" else "📌"
        title = notif.title[:25] + "..." if len(notif.title) > 25 else notif.title

        builder.row(
            InlineKeyboardButton(
                text=f"{status_emoji} {title}",
                callback_data=f"notif_read_{notif.id}"
            )
        )

    # Кнопки пагинации
    if total_pages > 1:
        pagination_buttons = []

        if current_page > 0:
            pagination_buttons.append(
                InlineKeyboardButton(
                    text="◀️",
                    callback_data=f"notifications_page_{current_page - 1}"
                )
            )

        pagination_buttons.append(
            InlineKeyboardButton(
                text=f"{current_page + 1}/{total_pages}",
                callback_data="notifications_current"
            )
        )

        if current_page < total_pages - 1:
            pagination_buttons.append(
                InlineKeyboardButton(
                    text="▶️",
                    callback_data=f"notifications_page_{current_page + 1}"
                )
            )

        builder.row(*pagination_buttons)

    # Кнопки действий
    builder.row(
        InlineKeyboardButton(text="🗑 Очистить все", callback_data="notif_clear_all"),
        InlineKeyboardButton(text="⚙️ Настройки", callback_data="notifications_settings"),
        width=2
    )

    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="notifications_main"),
        InlineKeyboardButton(text="🏠 Меню", callback_data="back_to_menu"),
        width=2
    )

    return builder.as_markup()


def get_notification_settings_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура настроек уведомлений"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="🔔 Включить", callback_data="notif_on"),
        InlineKeyboardButton(text="🔕 Выключить", callback_data="notif_off"),
        width=2
    )

    builder.row(
        InlineKeyboardButton(text="⏰ Напоминания о парах", callback_data="notif_reminders"),
        InlineKeyboardButton(text="📊 Статистика", callback_data="notif_stats"),
        width=2
    )

    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="notifications_main"),
        InlineKeyboardButton(text="🏠 Меню", callback_data="back_to_menu"),
        width=2
    )

    return builder.as_markup()


def get_notification_actions_keyboard(notification_id: str) -> InlineKeyboardMarkup:
    """Клавиатура действий с уведомлением"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="✅ Прочитано", callback_data=f"notif_read_{notification_id}"),
        InlineKeyboardButton(text="🗑 Удалить", callback_data=f"notif_delete_{notification_id}"),
        width=2
    )

    builder.row(
        InlineKeyboardButton(text="◀️ К списку", callback_data="notifications_list"),
        width=1
    )

    return builder.as_markup()
