"""
Клавиатуры для задач
"""
from .base import create_menu_keyboard
from ..utils.vk_utils import create_text_button, create_keyboard


def get_tasks_menu_keyboard() -> str:
    """Главное меню задач"""
    return create_menu_keyboard([
        [
            create_text_button("📋 Список задач", {"callback": "tasks_list"}, "primary"),
            create_text_button("📊 Статистика", {"callback": "tasks_stats"}, "secondary"),
        ],
        [
            create_text_button("➕ Новая задача", {"callback": "tasks_new"}, "positive"),
            create_text_button("⏰ На сегодня", {"callback": "tasks_today"}, "secondary"),
        ],
        [
            create_text_button("⚠️ Просроченные", {"callback": "tasks_overdue"}, "negative"),
        ],
        [
            create_text_button("↩️ Назад", {"callback": "back_to_menu"}, "secondary"),
        ],
    ])


def get_task_detail_keyboard(task_id: str, is_completed: bool = False) -> str:
    """Клавиатура детального просмотра задачи"""
    rows = []

    if not is_completed:
        rows.append([
            create_text_button("✅ Выполнено", {"callback": f"task_done_{task_id}"}, "positive"),
            create_text_button("⏰ Напомнить", {"callback": f"task_postpone_{task_id}"}, "primary"),
        ])

    rows.append([
        create_text_button("✏️ Редактировать", {"callback": f"task_edit_{task_id}"}, "secondary"),
        create_text_button("🗑 Удалить", {"callback": f"task_delete_{task_id}"}, "negative"),
    ])

    rows.append([
        create_text_button("◀️ К списку", {"callback": "tasks_list"}, "secondary"),
        create_text_button("🏠 Меню", {"callback": "back_to_menu"}, "secondary"),
    ])

    return create_keyboard(rows, one_time=True)


def get_priority_keyboard() -> str:
    """Клавиатура выбора приоритета"""
    return create_menu_keyboard([
        [create_text_button("⚪ Низкий", {"callback": "priority_low"}, "secondary")],
        [create_text_button("🟡 Средний", {"callback": "priority_medium"}, "primary")],
        [create_text_button("🟠 Высокий", {"callback": "priority_high"}, "positive")],
        [create_text_button("🔴 Критичный", {"callback": "priority_critical"}, "negative")],
        [create_text_button("↩️ Назад", {"callback": "tasks_main"}, "secondary")],
    ])


def get_category_keyboard() -> str:
    """Клавиатура выбора категории"""
    return create_menu_keyboard([
        [create_text_button("📚 Учеба", {"callback": "category_study"}, "primary")],
        [create_text_button("🏠 Домашнее задание", {"callback": "category_homework"}, "primary")],
        [create_text_button("📝 Экзамен", {"callback": "category_exam"}, "positive")],
        [create_text_button("💼 Проект", {"callback": "category_project"}, "primary")],
        [create_text_button("👤 Личное", {"callback": "category_personal"}, "secondary")],
        [create_text_button("📦 Другое", {"callback": "category_other"}, "secondary")],
        [create_text_button("↩️ Назад", {"callback": "tasks_main"}, "secondary")],
    ])
