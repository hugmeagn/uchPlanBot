from typing import Any

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def role_selection_kb() -> InlineKeyboardMarkup:
    """
    Клавиатура для выбора роли пользователя.
    """
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="🎓 Студент",
            callback_data="role_student"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="👨‍🏫 Преподаватель",
            callback_data="role_teacher"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="↩️ Назад",
            callback_data="profile_back"
        )
    )

    return builder.as_markup()


def institution_selection_kb(
    institutions: list[dict[str, Any]] | None = None
) -> InlineKeyboardMarkup:
    """
    Клавиатура для выбора учебного заведения.
    """
    builder = InlineKeyboardBuilder()

    if institutions:
        for inst in institutions:
            builder.row(
                InlineKeyboardButton(
                    text=inst.get("name", "Неизвестно"),
                    callback_data=f"institution_{inst.get('id', 0)}"
                )
            )
    else:
        demo_institutions = [
            {"id": 1, "name": "🏛️ Магнитогорский политехнический колледж"},
            {"id": 2, "name": "🎓 Магнитогорский государственный университет"},
            {"id": 3, "name": "🔧 Магнитогорский строительный колледж"},
            {"id": 4, "name": "💼 Магнитогорский торгово-экономический колледж"},
        ]

        for inst in demo_institutions:
            builder.row(
                InlineKeyboardButton(
                    text=inst["name"],
                    callback_data=f"institution_{inst['id']}"
                )
            )

    builder.row(
        InlineKeyboardButton(
            text="🔍 Найти своё заведение",
            callback_data="institution_search"
        )
    )

    builder.row(
        InlineKeyboardButton(
            text="↩️ Назад",
            callback_data="profile_back"
        )
    )

    return builder.as_markup()
