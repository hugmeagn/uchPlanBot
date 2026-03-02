"""
Общие и вспомогательные клавиатуры.
"""
from typing import Optional
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def back_button_kb(back_callback: str = "back_to_menu") -> InlineKeyboardMarkup:
    """
    Простая клавиатура с кнопкой "Назад".
    """
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="↩️ Назад", callback_data=back_callback)
    )

    return builder.as_markup()


def cancel_button_kb() -> InlineKeyboardMarkup:
    """
    Клавиатура с кнопкой "Отмена".
    """
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")
    )

    return builder.as_markup()


def pagination_kb(
        current_page: int,
        total_pages: int,
        prefix: str = "page"
) -> Optional[InlineKeyboardMarkup]:
    """
    Универсальная клавиатура пагинации.
    """
    if total_pages <= 1:
        return None

    builder = InlineKeyboardBuilder()

    buttons = []

    if current_page > 0:
        buttons.append(
            InlineKeyboardButton(
                text="⬅️",
                callback_data=f"{prefix}_{current_page - 1}"
            )
        )

    buttons.append(
        InlineKeyboardButton(
            text=f"{current_page + 1}/{total_pages}",
            callback_data=f"{prefix}_current"
        )
    )

    if current_page < total_pages - 1:
        buttons.append(
            InlineKeyboardButton(
                text="➡️",
                callback_data=f"{prefix}_{current_page + 1}"
            )
        )

    builder.row(*buttons)

    return builder.as_markup()


def confirmation_kb(confirm_text: str = "✅ Подтвердить") -> InlineKeyboardMarkup:
    """
    Клавиатура подтверждения действия.
    """
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text=confirm_text, callback_data="confirm"),
        InlineKeyboardButton(text="❌ Отменить", callback_data="cancel")
    )

    return builder.as_markup()


def skip_button_kb(skip_callback: str = "skip") -> InlineKeyboardMarkup:
    """
    Клавиатура с кнопкой "Пропустить".
    """
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="⏭️ Пропустить", callback_data=skip_callback)
    )

    return builder.as_markup()


def refresh_button_kb() -> InlineKeyboardMarkup:
    """
    Клавиатура с кнопкой "Обновить".
    """
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="🔄 Обновить", callback_data="refresh")
    )

    return builder.as_markup()


def close_button_kb() -> InlineKeyboardMarkup:
    """
    Клавиатура с кнопкой "Закрыть".
    """
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="❌ Закрыть", callback_data="close")
    )

    return builder.as_markup()
