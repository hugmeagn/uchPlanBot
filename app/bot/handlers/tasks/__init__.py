# app/bot/handlers/tasks/__init__.py

"""
Пакет обработчиков для задач
"""
import logging
from aiogram import Router
from aiogram.filters import Command, StateFilter

from .handlers import (
    task_callback_handler,
    cmd_task_create,
    task_title_handler,
    task_description_handler,
    task_deadline_handler,
    task_priority_handler,
    task_category_handler,
    task_confirm_handler,
    CreateTask  # Импортируем класс состояний
)
from .keyboards import (
    get_tasks_main_keyboard,
    get_tasks_pagination_keyboard,
    get_task_detail_keyboard
)

logger = logging.getLogger(__name__)

# Создаем роутер
router = Router()

# Регистрируем команду для создания задачи
router.message.register(cmd_task_create, Command("newtask"))

# Регистрируем callback хендлер (они обрабатывают нажатия на кнопки, не сообщения)
router.callback_query.register(task_callback_handler)

# ВАЖНО: Регистрируем FSM хендлеры ТОЛЬКО для соответствующих состояний!
router.message.register(task_title_handler, StateFilter(CreateTask.title))
router.message.register(task_description_handler, StateFilter(CreateTask.description))
router.message.register(task_deadline_handler, StateFilter(CreateTask.deadline))
router.message.register(task_priority_handler, StateFilter(CreateTask.priority))
router.message.register(task_category_handler, StateFilter(CreateTask.category))
router.message.register(task_confirm_handler, StateFilter(CreateTask.confirm))

# Экспортируем функции для использования в menu.py
__all__ = [
    'router',
    'show_tasks_list',
    'show_task_stats',
    'show_today_tasks',
    'show_overdue_tasks',
    'start_task_creation'
]

# Импортируем функции для экспорта
from .handlers import (
    show_tasks_list,
    show_task_stats,
    show_today_tasks,
    show_overdue_tasks,
    start_task_creation
)
