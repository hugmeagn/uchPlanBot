"""
Клавиатуры для расписания
"""
from .base import create_menu_keyboard
from ..utils.vk_utils import create_text_button


def get_schedule_menu_keyboard() -> str:
    """Главное меню расписания"""
    return create_menu_keyboard([
        [
            create_text_button("📅 Сегодня", {"callback": "schedule:today"}, "primary"),
            create_text_button("📅 Завтра", {"callback": "schedule:tomorrow"}, "primary"),
        ],
        [
            create_text_button("📅 Текущая неделя", {"callback": "schedule:week_current"}, "secondary"),
        ],
        [
            create_text_button("📅 Следующая неделя", {"callback": "schedule:week_next"}, "secondary"),
        ],
        [
            create_text_button("↩️ Назад", {"callback": "back_to_menu"}, "secondary"),
        ],
    ])


def get_schedule_day_keyboard(current_date_str: str, show_today: bool = True) -> str:
    """Клавиатура навигации по дням"""
    rows = []

    from datetime import datetime, timedelta
    current_date = datetime.strptime(current_date_str, "%Y-%m-%d")
    yesterday = current_date - timedelta(days=1)
    tomorrow = current_date + timedelta(days=1)

    nav_row = []
    nav_row.append(
        create_text_button("◀️ Вчера", {"callback": f"schedule:date:{yesterday.strftime('%Y-%m-%d')}"}, "secondary")
    )

    if show_today:
        nav_row.append(
            create_text_button("📅 Сегодня", {"callback": "schedule:today"}, "primary")
        )

    nav_row.append(
        create_text_button("Завтра ▶️", {"callback": f"schedule:date:{tomorrow.strftime('%Y-%m-%d')}"}, "secondary")
    )

    rows.append(nav_row)

    rows.append([
        create_text_button("📅 На неделю", {"callback": "schedule:week_current"}, "secondary"),
        create_text_button("📅 След. неделя", {"callback": "schedule:week_next"}, "secondary"),
    ])

    rows.append([
        create_text_button("↩️ К меню расписания", {"callback": "schedule:main"}, "secondary"),
    ])

    rows.append([
        create_text_button("🏠 Главное меню", {"callback": "back_to_menu"}, "secondary"),
    ])

    from ..utils.vk_utils import create_keyboard
    return create_keyboard(rows, one_time=True)
