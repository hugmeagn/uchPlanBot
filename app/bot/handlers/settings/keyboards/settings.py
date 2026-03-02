"""
Клавиатуры для настроек профиля.
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def settings_kb() -> InlineKeyboardMarkup:
    """
    Клавиатура настроек профиля.
    """
    builder = InlineKeyboardBuilder()

    # builder.row(
    #     InlineKeyboardButton(text="👤 Изменить профиль", callback_data="settings_profile"),
    #     InlineKeyboardButton(text="🔔 Уведомления", callback_data="settings_notifications")
    # )
    # builder.row(
    #     InlineKeyboardButton(text="🏫 Изменить заведение", callback_data="settings_institution"),
    #     InlineKeyboardButton(text="👥 Изменить группу", callback_data="settings_group")
    # )
    builder.row(
        InlineKeyboardButton(text="🗑️ Удалить данные", callback_data="settings_delete_data"),
        InlineKeyboardButton(text="↩️ В меню", callback_data="back_to_menu")
    )

    return builder.as_markup()


def notification_settings_kb(notifications_enabled: bool = True) -> InlineKeyboardMarkup:
    """
    Клавиатура настроек уведомлений.
    """
    builder = InlineKeyboardBuilder()

    status_text = "🔔 Включены" if notifications_enabled else "🔕 Выключены"
    toggle_text = "🔕 Выключить" if notifications_enabled else "🔔 Включить"
    toggle_callback = "notifications_disable" if notifications_enabled else "notifications_enable"

    builder.row(
        InlineKeyboardButton(
            text=f"Статус: {status_text}",
            callback_data="notifications_status"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=toggle_text,
            callback_data=toggle_callback
        ),
        InlineKeyboardButton(
            text="⏰ Настроить время",
            callback_data="notifications_time"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="↩️ Назад к настройкам",
            callback_data="settings_back"
        )
    )

    return builder.as_markup()


def timezone_selection_kb() -> InlineKeyboardMarkup:
    """
    Клавиатура для выбора часового пояса.
    """
    builder = InlineKeyboardBuilder()

    timezones = [
        ("🇷🇺 Москва (MSK)", "Europe/Moscow"),
        ("🇷🇺 Калининград (UTC+2)", "Europe/Kaliningrad"),
        ("🇷🇺 Самара (UTC+4)", "Europe/Samara"),
        ("🇷🇺 Екатеринбург (YEKT)", "Asia/Yekaterinburg"),
        ("🇷🇺 Омск (UTC+6)", "Asia/Omsk"),
        ("🇷🇺 Красноярск (UTC+7)", "Asia/Krasnoyarsk"),
        ("🇷🇺 Иркутск (UTC+8)", "Asia/Irkutsk"),
        ("🇷🇺 Якутск (UTC+9)", "Asia/Yakutsk"),
        ("🇷🇺 Владивосток (UTC+10)", "Asia/Vladivostok"),
        ("🇷🇺 Магадан (UTC+11)", "Asia/Magadan"),
        ("🇷🇺 Камчатка (UTC+12)", "Asia/Kamchatka"),
    ]

    for tz_name, tz_value in timezones:
        builder.row(
            InlineKeyboardButton(
                text=tz_name,
                callback_data=f"timezone_{tz_value}"
            )
        )

    builder.row(
        InlineKeyboardButton(text="↩️ Назад", callback_data="edit_profile_back")
    )

    return builder.as_markup()


def delete_confirmation_kb() -> InlineKeyboardMarkup:
    """
    Клавиатура для подтверждения удаления данных.
    """
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="✅ Да, удалить всё", callback_data="delete_confirm_all"),
        InlineKeyboardButton(text="🗑️ Удалить только задачи", callback_data="delete_confirm_tasks")
    )
    builder.row(
        InlineKeyboardButton(text="🗑️ Удалить только расписание", callback_data="delete_confirm_schedule"),
        InlineKeyboardButton(text="❌ Отменить", callback_data="delete_cancel")
    )

    return builder.as_markup()
