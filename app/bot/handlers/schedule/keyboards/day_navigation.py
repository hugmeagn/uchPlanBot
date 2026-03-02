from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime, timedelta


def get_day_navigation_keyboard(
        current_date: datetime,
        show_today: bool = True
) -> InlineKeyboardMarkup:
    """
    Клавиатура для навигации по дням (вчера/сегодня/завтра).

    :param current_date: Текущая отображаемая дата
    :param show_today: Показывать ли кнопку "Сегодня"
    """
    builder = InlineKeyboardBuilder()

    # Форматируем даты для callback
    yesterday = current_date - timedelta(days=1)
    tomorrow = current_date + timedelta(days=1)

    # Кнопки навигации
    nav_buttons = []

    nav_buttons.append(
        InlineKeyboardButton(
            text="◀️ Вчера",
            callback_data=f"schedule:date:{yesterday.strftime('%Y-%m-%d')}"
        )
    )

    if show_today:
        nav_buttons.append(
            InlineKeyboardButton(
                text="📅 Сегодня",
                callback_data="schedule:today"
            )
        )

    nav_buttons.append(
        InlineKeyboardButton(
            text="Завтра ▶️",
            callback_data=f"schedule:date:{tomorrow.strftime('%Y-%m-%d')}"
        )
    )

    builder.row(*nav_buttons, width=3 if show_today else 2)

    # Кнопки для смены режима просмотра
    builder.row(
        InlineKeyboardButton(
            text="📅 На неделю",
            callback_data="schedule:week_current"
        ),
        InlineKeyboardButton(
            text="📅 На след. неделю",
            callback_data="schedule:week_next"
        ),
        width=2
    )

    # Кнопка возврата в меню выбора периода
    builder.row(
        InlineKeyboardButton(text="◀️ К выбору периода", callback_data="schedule:main"),
        InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu"),
        width=2
    )

    return builder.as_markup()


def get_week_navigation_keyboard(week_type: str = "current") -> InlineKeyboardMarkup:
    """
    Клавиатура для навигации по неделям.

    :param week_type: "current" или "next"
    """
    builder = InlineKeyboardBuilder()

    if week_type == "current":
        builder.row(
            InlineKeyboardButton(text="📅 На сегодня", callback_data="schedule:today"),
            InlineKeyboardButton(text="📅 На завтра", callback_data="schedule:tomorrow"),
            width=2
        )
        builder.row(
            InlineKeyboardButton(text="📅 На след. неделю", callback_data="schedule:week_next"),
            width=1
        )
    else:
        builder.row(
            InlineKeyboardButton(text="📅 На тек. неделю", callback_data="schedule:week_current"),
            width=1
        )

    builder.row(
        InlineKeyboardButton(text="◀️ К выбору периода", callback_data="schedule:main"),
        InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu"),
        width=2
    )

    return builder.as_markup()
