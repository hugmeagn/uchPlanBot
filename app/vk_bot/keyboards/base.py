"""
Базовые функции для создания VK клавиатур
"""
import json
from typing import List, Dict, Any, Optional

from ..utils.vk_utils import (
    create_keyboard,
    create_text_button,
    create_callback_button,
    create_link_button,
    get_priority_color
)


def create_menu_keyboard(buttons: List[List[Dict[str, Any]]]) -> str:
    """
    Создает клавиатуру меню

    Args:
        buttons: Список рядов кнопок (уже сформированных)
    """
    return create_keyboard(buttons, one_time=False)


def create_back_keyboard(back_callback: str = "back_to_menu") -> str:
    """Создает клавиатуру с кнопкой Назад"""
    return create_keyboard([
        [create_text_button("↩️ Назад", {"callback": back_callback}, "secondary")]
    ], one_time=True)


def create_pagination_keyboard(
    current_page: int,
    total_pages: int,
    prefix: str = "page",
    show_back: bool = True
) -> str:
    """
    Создает клавиатуру с пагинацией
    """
    rows = []

    if total_pages > 1:
        pagination_row = []

        if current_page > 0:
            pagination_row.append(
                create_text_button("◀️", {"callback": f"{prefix}_{current_page - 1}"}, "secondary")
            )

        pagination_row.append(
            create_text_button(
                f"{current_page + 1}/{total_pages}",
                {"callback": "page_current"},
                "primary"
            )
        )

        if current_page < total_pages - 1:
            pagination_row.append(
                create_text_button("▶️", {"callback": f"{prefix}_{current_page + 1}"}, "secondary")
            )

        rows.append(pagination_row)

    if show_back:
        rows.append([create_text_button("↩️ Назад", {"callback": "back_to_menu"}, "secondary")])

    return create_keyboard(rows, one_time=True)


def create_confirm_keyboard(
    confirm_callback: str = "confirm",
    cancel_callback: str = "cancel"
) -> str:
    """Создает клавиатуру подтверждения"""
    return create_keyboard([
        [
            create_text_button("✅ Да", {"callback": confirm_callback}, "positive"),
            create_text_button("❌ Нет", {"callback": cancel_callback}, "negative")
        ]
    ], one_time=True)


def create_settings_keyboard(notifications_enabled: bool = True) -> str:
    """Создает клавиатуру настроек"""
    rows = []

    status_text = "🔔 Уведомления: ВКЛ" if notifications_enabled else "🔕 Уведомления: ВЫКЛ"
    toggle_callback = "toggle_notifications"

    rows.append([
        create_text_button(
            status_text,
            {"callback": toggle_callback},
            "primary" if notifications_enabled else "secondary"
        )
    ])

    rows.append([
        create_text_button("🗑️ Удалить данные", {"callback": "delete_data"}, "negative")
    ])

    rows.append([
        create_text_button("↩️ Назад", {"callback": "back_to_menu"}, "secondary")
    ])

    return create_keyboard(rows, one_time=False)


def create_empty_keyboard() -> str:
    """Создает пустую клавиатуру"""
    return json.dumps({"buttons": [], "one_time": True})


def create_inline_keyboard(buttons: List[List[Dict[str, Any]]]) -> str:
    """Создает инлайн клавиатуру"""
    return create_keyboard(buttons, inline=True)
