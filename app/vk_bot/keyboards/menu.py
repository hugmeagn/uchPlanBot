"""
Клавиатуры главного меню
"""
from .base import create_menu_keyboard
from ..utils.vk_utils import create_text_button, create_callback_button


def get_main_menu_keyboard() -> str:
    """
    Основное меню бота
    """
    buttons = [
        # Первый ряд
        [
            create_text_button("🌅 План на сегодня", {"callback": "menu_plan_today"}, "positive"),
        ],
        # Второй ряд
        [
            create_text_button("📚 Расписание", {"callback": "menu_schedule"}, "primary"),
        ],
        # Третий ряд
        [
            create_text_button("📋 Мои задачи", {"callback": "menu_tasks"}, "primary"),
            create_text_button("➕ Добавить задачу", {"callback": "menu_add_task"}, "secondary"),
        ],
        # Четвертый ряд
        [
            create_text_button("📊 Статистика", {"callback": "menu_task_stats"}, "secondary"),
            create_text_button("🔔 Уведомления", {"callback": "menu_notifications"}, "secondary"),
        ],
        # Пятый ряд
        [
            create_text_button("⏰ На сегодня", {"callback": "menu_today"}, "secondary"),
            create_text_button("⚠️ Просроченные", {"callback": "menu_overdue"}, "negative"),
        ],
        # Шестой ряд
        [
            create_text_button("⚙️ Настройки", {"callback": "menu_settings"}, "secondary"),
            create_text_button("ℹ️ Помощь", {"callback": "menu_help"}, "secondary"),
        ],
    ]

    return create_menu_keyboard(buttons)


def get_help_keyboard() -> str:
    """Клавиатура для помощи"""
    from .base import create_back_keyboard
    return create_back_keyboard("back_to_menu")
