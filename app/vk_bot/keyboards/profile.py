"""
Клавиатуры для настройки профиля
"""
from .base import create_menu_keyboard
from ..utils.vk_utils import create_text_button


def get_profile_setup_keyboard() -> str:
    """Клавиатура начала настройки профиля"""
    return create_menu_keyboard([
        [create_text_button("🚀 Начать настройку", {"callback": "profile_set_role"}, "positive")]
    ])


def get_role_selection_keyboard() -> str:
    """Клавиатура выбора роли"""
    return create_menu_keyboard([
        [create_text_button("🎓 Студент", {"callback": "role_student"}, "primary")],
        [create_text_button("👨‍🏫 Преподаватель", {"callback": "role_teacher"}, "primary")],
        [create_text_button("↩️ Назад", {"callback": "profile_back"}, "secondary")]
    ])


def get_institution_search_keyboard() -> str:
    """Клавиатура поиска учебного заведения"""
    return create_menu_keyboard([
        [create_text_button("🔍 Найти заведение", {"callback": "institution_search"}, "primary")],
        [create_text_button("📋 Список заведений", {"callback": "institution_show_all"}, "secondary")],
        [create_text_button("↩️ Назад", {"callback": "profile_back"}, "secondary")]
    ])


def get_skip_keyboard(skip_callback: str = "skip") -> str:
    """Клавиатура с кнопкой Пропустить"""
    return create_menu_keyboard([
        [create_text_button("⏭️ Пропустить", {"callback": skip_callback}, "secondary")]
    ])
