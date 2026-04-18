"""
Клавиатуры для VK бота
"""
from .base import (
    create_menu_keyboard,
    create_back_keyboard,
    create_pagination_keyboard,
    create_confirm_keyboard,
    create_settings_keyboard,
    create_empty_keyboard
)

from .menu import get_main_menu_keyboard
from .profile import get_profile_setup_keyboard, get_role_selection_keyboard
from .schedule import get_schedule_menu_keyboard
from .tasks import get_tasks_menu_keyboard

__all__ = [
    'create_menu_keyboard',
    'create_back_keyboard',
    'create_pagination_keyboard',
    'create_confirm_keyboard',
    'create_settings_keyboard',
    'create_empty_keyboard',
    'get_main_menu_keyboard',
    'get_profile_setup_keyboard',
    'get_role_selection_keyboard',
    'get_schedule_menu_keyboard',
    'get_tasks_menu_keyboard',
]
