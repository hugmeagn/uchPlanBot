"""
Обработчики команд запуска и главного меню.
"""
import logging
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from bot.handlers.menu.keyboards.menu import main_menu_kb

# Импортируем функции для отображения разделов
from bot.handlers.tasks import show_tasks_list, show_task_stats, show_today_tasks, show_overdue_tasks
from bot.handlers.notifications import show_notifications_list

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("menu"))
@router.callback_query(F.data == "back_to_menu")
async def show_main_menu(update: Message | CallbackQuery):
    """
    Показать главное меню.
    """
    if isinstance(update, CallbackQuery):
        message = update.message
        await update.answer()
    else:
        message = update

    await message.answer(
        "🏠 **Главное меню**\n\n"
        "Выберите действие:",
        reply_markup=main_menu_kb(),
    )


# ==================== ОБРАБОТЧИКИ ДЛЯ ЗАДАЧ ====================

@router.callback_query(F.data == "menu_tasks")
async def menu_tasks(callback: CallbackQuery):
    """Показать список задач"""
    await show_tasks_list(callback)


@router.callback_query(F.data == "menu_add_task")
async def menu_add_task(callback: CallbackQuery, state: FSMContext):
    """Начать создание новой задачи"""
    from bot.handlers.tasks import start_task_creation
    await start_task_creation(callback, state)


@router.callback_query(F.data == "menu_task_stats")
async def menu_task_stats(callback: CallbackQuery):
    """Показать статистику задач"""
    await show_task_stats(callback)


@router.callback_query(F.data == "menu_today")
async def menu_today(callback: CallbackQuery):
    """Показать задачи на сегодня"""
    await show_today_tasks(callback)


@router.callback_query(F.data == "menu_overdue")
async def menu_overdue(callback: CallbackQuery):
    """Показать просроченные задачи"""
    await show_overdue_tasks(callback)


# ==================== ОБРАБОТЧИКИ ДЛЯ УВЕДОМЛЕНИЙ ====================

@router.callback_query(F.data == "menu_notifications")
async def menu_notifications(callback: CallbackQuery):
    """Показать уведомления"""
    await show_notifications_list(callback)


# ==================== ОБРАБОТЧИКИ ДЛЯ РАСПИСАНИЯ ====================

@router.callback_query(F.data == "menu_schedule")
async def menu_schedule(callback: CallbackQuery):
    """Показать меню расписания"""
    # Импортируем здесь, чтобы избежать циклических импортов
    from bot.handlers.schedule.schedule import show_schedule_menu
    await show_schedule_menu(callback)
