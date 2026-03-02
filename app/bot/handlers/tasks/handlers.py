"""
Хендлеры для работы с задачами (через инлайн кнопки)
"""
from datetime import datetime, timedelta, timezone
import logging
from typing import Optional

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import bot.utils.dates as dates
import config

from bot_integration.integration import get_integration
from services.tasks.service import (
    TaskStatus, TaskPriority, TaskCategory,
    ReminderType, TaskNotFoundError, TaskValidationError
)
from services.tasks.utils import parse_deadline, format_time_left, validate_task_title

from .keyboards import (
    get_tasks_main_keyboard,
    get_tasks_pagination_keyboard,
    get_priority_keyboard,
    get_category_keyboard,
    get_confirm_keyboard,
    get_task_detail_keyboard
)

logger = logging.getLogger(__name__)

# Создаем роутер для FSM хендлеров
router = Router()


# FSM состояния для создания задачи
class CreateTask(StatesGroup):
    title = State()
    description = State()
    deadline = State()
    priority = State()
    category = State()
    confirm = State()


# ==================== ОСНОВНЫЕ ФУНКЦИИ ДЛЯ ОТОБРАЖЕНИЯ ====================

async def show_tasks_menu(callback: CallbackQuery):
    """Показать главное меню задач"""
    await callback.message.edit_text(
        "📋 **Управление задачами**\n\n"
        "Выберите действие:",
        reply_markup=get_tasks_main_keyboard()
    )
    await callback.answer()


async def show_tasks_list(callback: CallbackQuery, page: int = 0):
    """Показать список задач с пагинацией"""
    integration = await get_integration()
    user_id = str(callback.from_user.id)

    try:
        # Получаем задачи пользователя (используем существующий метод list_tasks)
        tasks = await integration.task_service.list_tasks(
            user_id=user_id,
            show_completed=False,
            limit=50,  # Получаем достаточно задач для пагинации
            offset=page * 5
        )

        # Получаем общее количество задач (для пагинации)
        # Примечание: если у вас нет метода для получения общего количества,
        # можно получить все задачи и посчитать, но это неэффективно
        all_tasks = await integration.task_service.list_tasks(
            user_id=user_id,
            show_completed=False,
            limit=1000  # Большой лимит для подсчета
        )
        total_tasks = len(all_tasks)

        # Вычисляем общее количество страниц
        page_size = 5
        total_pages = (total_tasks + page_size - 1) // page_size

        if not tasks:
            await callback.message.edit_text(
                "📭 **У вас пока нет активных задач**\n\n"
                "Создайте новую задачу, нажав кнопку ниже:",
                reply_markup=get_tasks_main_keyboard(show_back=True)
            )
            await callback.answer()
            return

        # Формируем сообщение
        text = "📋 *Ваши активные задачи:*\n\n"

        for i, task in enumerate(tasks, 1 + page * 5):
            priority_emoji = {
                TaskPriority.LOW: "⚪",
                TaskPriority.MEDIUM: "🟡",
                TaskPriority.HIGH: "🟠",
                TaskPriority.CRITICAL: "🔴"
            }.get(task.priority, "⚪")

            deadline_text = ""
            if task.deadline:
                time_left = format_time_left(task.deadline)
                deadline_text = f" — {time_left}"

            # Отмечаем просроченные
            if task.deadline and task.deadline < dates.now():
                deadline_text = f" — ⚠️ ПРОСРОЧЕНО!"

            text += f"{i}. {priority_emoji} *{task.title}*{deadline_text}\n"

            if task.description and len(task.description) > 30:
                text += f"   📝 {task.description[:30]}...\n"

        # Добавляем клавиатуру с пагинацией
        keyboard = await get_tasks_pagination_keyboard(tasks, page, total_pages)

        await callback.message.edit_text(
            text,
            parse_mode="Markdown",
            reply_markup=keyboard
        )

    except Exception as e:
        logger.error(f"Error in show_tasks_list: {e}", exc_info=True)
        await callback.message.edit_text(
            "❌ Произошла ошибка при получении задач",
            reply_markup=get_tasks_main_keyboard(show_back=True)
        )
    finally:
        await callback.answer()


async def show_task_stats(callback: CallbackQuery):
    """Показать статистику по задачам"""
    integration = await get_integration()
    user_id = str(callback.from_user.id)

    try:
        stats = await integration.task_service.get_stats(user_id)

        text = "📊 *Статистика задач*\n\n"
        text += f"📋 **Всего задач:** {stats.total}\n"
        text += f"✅ **Активных:** {stats.active}\n"
        text += f"✔️ **Выполнено:** {stats.completed}\n"
        text += f"⚠️ **Просрочено:** {stats.overdue}\n"
        text += f"📦 **В архиве:** {stats.archived}\n"

        if hasattr(stats, 'upcoming_deadlines') and stats.upcoming_deadlines > 0:
            text += f"\n⏰ **Ближайших дедлайнов (24ч):** {stats.upcoming_deadlines}\n"

        # По приоритетам
        if hasattr(stats, 'by_priority') and stats.by_priority:
            text += "\n*По приоритетам:*\n"
            priority_counts = []
            for priority, count in stats.by_priority.items():
                emoji = {0: "⚪", 1: "🟡", 2: "🟠", 3: "🔴"}.get(priority, "⚪")
                priority_counts.append(f"{emoji} {count}")

            if priority_counts:
                text += " ".join(priority_counts)

        await callback.message.edit_text(
            text,
            parse_mode="Markdown",
            reply_markup=get_tasks_main_keyboard(show_back=True)
        )

    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        await callback.message.edit_text(
            "❌ Произошла ошибка при получении статистики",
            reply_markup=get_tasks_main_keyboard(show_back=True)
        )
    finally:
        await callback.answer()


async def show_today_tasks(callback: CallbackQuery):
    """Показать задачи на сегодня"""
    integration = await get_integration()
    user_id = str(callback.from_user.id)

    try:
        today = dates.now().date()
        tomorrow = today + timedelta(days=1)

        # Получаем все активные задачи
        all_tasks = await integration.task_service.list_tasks(
            user_id=user_id,
            show_completed=False
        )

        # Фильтруем задачи на сегодня
        tasks = []
        for task in all_tasks:
            if task.deadline and task.deadline.date() == today:
                tasks.append(task)

        if not tasks:
            await callback.message.edit_text(
                "✅ **На сегодня задач нет!**\n\n"
                "Можно отдохнуть или создать новую задачу.",
                reply_markup=get_tasks_main_keyboard(show_back=True)
            )
            await callback.answer()
            return

        text = "📅 **Задачи на сегодня:**\n\n"

        for task in tasks:
            priority_emoji = {
                TaskPriority.LOW: "⚪",
                TaskPriority.MEDIUM: "🟡",
                TaskPriority.HIGH: "🟠",
                TaskPriority.CRITICAL: "🔴"
            }.get(task.priority, "⚪")

            time_str = task.deadline.strftime("%H:%M") if task.deadline else "весь день"
            text += f"{priority_emoji} *{task.title}* — {time_str}\n"

        await callback.message.edit_text(
            text,
            parse_mode="Markdown",
            reply_markup=get_tasks_main_keyboard(show_back=True)
        )

    except Exception as e:
        logger.error(f"Error in show_today_tasks: {e}")
        await callback.message.edit_text(
            "❌ Произошла ошибка",
            reply_markup=get_tasks_main_keyboard(show_back=True)
        )
    finally:
        await callback.answer()


async def show_overdue_tasks(callback: CallbackQuery):
    """Показать просроченные задачи"""
    integration = await get_integration()
    user_id = str(callback.from_user.id)

    try:
        # Получаем все активные задачи
        all_tasks = await integration.task_service.list_tasks(
            user_id=user_id,
            show_completed=False,
            limit=1000
        )

        # Фильтруем просроченные вручную
        now = dates.now()
        overdue_tasks = [
            task for task in all_tasks
            if task.deadline and task.deadline < now
        ]

        if not overdue_tasks:
            await callback.message.edit_text(
                "✅ **Просроченных задач нет!**\n\n"
                "Отлично! Вы всё успеваете.",
                reply_markup=get_tasks_main_keyboard(show_back=True)
            )
            await callback.answer()
            return

        text = "⚠️ **Просроченные задачи:**\n\n"

        for task in overdue_tasks:
            days_overdue = (now - task.deadline).days if task.deadline else 0
            text += f"🔴 *{task.title}* — просрочено на {days_overdue} дн.\n"

        await callback.message.edit_text(
            text,
            parse_mode="Markdown",
            reply_markup=get_tasks_main_keyboard(show_back=True)
        )

    except Exception as e:
        logger.error(f"Error in show_overdue_tasks: {e}")
        await callback.message.edit_text(
            "❌ Произошла ошибка",
            reply_markup=get_tasks_main_keyboard(show_back=True)
        )
    finally:
        await callback.answer()


# ==================== ДЕТАЛЬНЫЙ ПРОСМОТР ЗАДАЧИ ====================

async def show_task_detail(callback: CallbackQuery, task_id: str):
    """Показать детальную информацию о задаче"""
    integration = await get_integration()
    user_id = str(callback.from_user.id)

    try:
        task = await integration.task_service.get_task(task_id, user_id)

        priority_names = {
            TaskPriority.LOW: "Низкий",
            TaskPriority.MEDIUM: "Средний",
            TaskPriority.HIGH: "Высокий",
            TaskPriority.CRITICAL: "Критичный"
        }

        category_names = {
            TaskCategory.STUDY: "📚 Учеба",
            TaskCategory.HOMEWORK: "🏠 Домашнее задание",
            TaskCategory.EXAM: "📝 Экзамен",
            TaskCategory.PROJECT: "💼 Проект",
            TaskCategory.PERSONAL: "👤 Личное",
            TaskCategory.OTHER: "📦 Другое"
        }

        text = f"📋 *{task.title}*\n\n"

        if task.description:
            text += f"📝 *Описание:*\n{task.description}\n\n"

        if task.deadline:
            # Конвертируем UTC в локальное время
            local_deadline = dates.to_local(task.deadline)
            now_local = dates.now()

            time_left = format_time_left(task.deadline)  # эта функция уже должна работать с UTC
            deadline_status = "⚠️ ПРОСРОЧЕНО!" if task.deadline < dates.now() else ""

            text += f"🗓 *Дедлайн:* {local_deadline.strftime('%d.%m.%Y %H:%M')}\n"
            text += f"⏳ *Осталось:* {time_left} {deadline_status}\n\n"

        text += f"⚡ *Приоритет:* {priority_names.get(task.priority, 'Средний')}\n"
        text += f"📂 *Категория:* {category_names.get(task.category, '📦 Другое')}\n"
        text += f"📊 *Статус:* {'✅ Выполнена' if task.status == TaskStatus.COMPLETED else '⏳ Активна'}\n"

        if hasattr(task, 'progress') and task.progress:
            text += f"📈 *Прогресс:* {task.progress}%\n"

        text += f"\n🆔 `{task.id[:8]}...`"

        await callback.message.edit_text(
            text,
            parse_mode="Markdown",
            reply_markup=get_task_detail_keyboard(task_id, task.status == TaskStatus.COMPLETED)
        )

    except TaskNotFoundError:
        await callback.message.edit_text(
            "❌ Задача не найдена",
            reply_markup=get_tasks_main_keyboard(show_back=True)
        )
    except Exception as e:
        logger.error(f"Error in show_task_detail: {e}")
        await callback.message.edit_text(
            "❌ Произошла ошибка",
            reply_markup=get_tasks_main_keyboard(show_back=True)
        )
    finally:
        await callback.answer()


# ==================== СОЗДАНИЕ ЗАДАЧИ (FSM) ====================

# app/bot/handlers/tasks/handlers.py - исправленные FSM хендлеры

# ==================== СОЗДАНИЕ ЗАДАЧИ (FSM) ====================

async def start_task_creation(update: Message | CallbackQuery, state: FSMContext):
    """Начинает создание новой задачи"""
    # Очищаем предыдущее состояние
    await state.clear()

    if isinstance(update, CallbackQuery):
        message = update.message
        await update.answer()
        # Удаляем сообщение с кнопкой, чтобы не загромождать чат
        await message.delete()
    else:
        message = update

    await state.set_state(CreateTask.title)

    text = (
        "📝 **Создание новой задачи**\n\n"
        "Введите **название** задачи (или отправьте 'отмена' для выхода):"
    )

    await message.answer(text, parse_mode="Markdown")


@router.message(CreateTask.title)
async def task_title_handler(message: Message, state: FSMContext):
    """Обрабатывает ввод названия задачи"""
    title = message.text.strip()

    # Проверяем, не является ли ввод командой отмены
    if title.lower() in ['отмена', 'cancel', 'стоп']:
        await state.clear()
        await message.answer("❌ Создание задачи отменено")
        return

    if not validate_task_title(title):
        await message.answer(
            "❌ Некорректное название. Название должно быть от 3 до 100 символов.\n"
            "Попробуйте еще раз (или отправьте 'отмена' для выхода):"
        )
        return

    await state.update_data(title=title)
    await state.set_state(CreateTask.description)

    await message.answer(
        "📝 Введите **описание** задачи (или отправьте `-` чтобы пропустить):",
        parse_mode="Markdown"
    )


@router.message(CreateTask.description)
async def task_description_handler(message: Message, state: FSMContext):
    """Обрабатывает ввод описания задачи"""
    text = message.text.strip()

    # Проверяем, не является ли ввод командой отмены
    if text.lower() in ['отмена', 'cancel', 'стоп']:
        await state.clear()
        await message.answer("❌ Создание задачи отменено")
        return

    description = None if text == "-" else text

    await state.update_data(description=description)
    await state.set_state(CreateTask.deadline)

    await message.answer(
        "🗓 Введите **дедлайн** задачи (или отправьте `-` чтобы пропустить):\n\n"
        "**Примеры:**\n"
        "• завтра 18:00\n"
        "• 25.12 15:30\n"
        "• через 2 часа\n"
        "• 31.12.2024 23:59",
        parse_mode="Markdown"
    )


@router.message(CreateTask.deadline)
async def task_deadline_handler(message: Message, state: FSMContext):
    """Обрабатывает ввод дедлайна"""
    text = message.text.strip()

    # Проверяем, не является ли ввод командой отмены
    if text.lower() in ['отмена', 'cancel', 'стоп']:
        await state.clear()
        await message.answer("❌ Создание задачи отменено")
        return

    deadline = None

    if text != "-":
        deadline = parse_deadline(text)
        if not deadline:
            await message.answer(
                "❌ Не удалось распознать дату. Попробуйте еще раз:\n\n"
                "Пример: завтра 18:00 или 25.12 15:30\n"
                "Или отправьте 'отмена' для выхода"
            )
            return

    await state.update_data(deadline=deadline)
    await state.set_state(CreateTask.priority)

    await message.answer(
        "⚡ Выберите **приоритет** задачи:",
        reply_markup=get_priority_keyboard(),
        parse_mode="Markdown"
    )


@router.message(CreateTask.priority)
async def task_priority_handler(message: Message, state: FSMContext):
    """Обрабатывает выбор приоритета"""
    text = message.text.strip()

    # Проверяем, не является ли ввод командой отмены
    if text.lower() in ['отмена', 'cancel', 'стоп']:
        await state.clear()
        await message.answer("❌ Создание задачи отменено", reply_markup=ReplyKeyboardRemove())
        return

    priority_map = {
        "Низкий": TaskPriority.LOW,
        "Средний": TaskPriority.MEDIUM,
        "Высокий": TaskPriority.HIGH,
        "Критичный": TaskPriority.CRITICAL
    }

    if text not in priority_map:
        await message.answer(
            "❌ Пожалуйста, выберите приоритет из клавиатуры:\n"
            "Или отправьте 'отмена' для выхода",
            reply_markup=get_priority_keyboard()
        )
        return

    await state.update_data(priority=priority_map[text])
    await state.set_state(CreateTask.category)

    await message.answer(
        "📂 Выберите **категорию** задачи:",
        reply_markup=get_category_keyboard(),
        parse_mode="Markdown"
    )

async def cmd_task_create(message: Message, state: FSMContext):
    """Начинает создание новой задачи по команде /newtask"""
    # Очищаем предыдущее состояние
    await state.clear()

    await state.set_state(CreateTask.title)

    text = (
        "📝 **Создание новой задачи**\n\n"
        "Введите **название** задачи:"
    )

    await message.answer(text, parse_mode="Markdown")


@router.message(Command("cancel"))
@router.message(F.text.lower().in_(['отмена', 'cancel', 'стоп']))
async def cmd_cancel(message: Message, state: FSMContext):
    """Отмена текущего действия и возврат в главное меню"""
    current_state = await state.get_state()

    if current_state is None:
        # Если не в состоянии, просто показываем меню
        from bot.handlers.menu.menu import show_main_menu
        await show_main_menu(message)
        return

    await state.clear()
    await message.answer(
        "❌ Действие отменено",
        reply_markup=ReplyKeyboardRemove()
    )

    # Показываем главное меню
    from bot.handlers.menu.menu import show_main_menu
    await show_main_menu(message)

async def _format_task_preview(
        title: str,
        description: Optional[str],
        deadline: Optional[datetime],
        priority: TaskPriority,
        category: TaskCategory
) -> str:
    """Форматирует предварительный просмотр задачи"""
    priority_names = {
        TaskPriority.LOW: "Низкий",
        TaskPriority.MEDIUM: "Средний",
        TaskPriority.HIGH: "Высокий",
        TaskPriority.CRITICAL: "Критичный"
    }

    category_names = {
        TaskCategory.STUDY: "📚 Учеба",
        TaskCategory.HOMEWORK: "🏠 Домашнее задание",
        TaskCategory.EXAM: "📝 Экзамен",
        TaskCategory.PROJECT: "💼 Проект",
        TaskCategory.PERSONAL: "👤 Личное",
        TaskCategory.OTHER: "📦 Другое"
    }

    text = f"*Название:* {title}\n"

    if description:
        text += f"*Описание:* {description[:100]}{'...' if len(description) > 100 else ''}\n"

    if deadline:
        # deadline уже должен быть в локальном времени
        text += f"*Дедлайн:* {deadline.strftime('%d.%m.%Y %H:%M')}\n"

    text += f"*Приоритет:* {priority_names.get(priority, 'Средний')}\n"
    text += f"*Категория:* {category_names.get(category, '📦 Другое')}"

    return text


@router.message(CreateTask.category)
async def task_category_handler(message: Message, state: FSMContext):
    """Обрабатывает выбор категории"""
    text = message.text.strip()

    # Проверяем, не является ли ввод командой отмены
    if text.lower() in ['отмена', 'cancel', 'стоп']:
        await state.clear()
        await message.answer("❌ Создание задачи отменено", reply_markup=ReplyKeyboardRemove())
        # Показываем главное меню
        from bot.handlers.menu.menu import show_main_menu
        await show_main_menu(message)
        return

    category_map = {
        "📚 Учеба": TaskCategory.STUDY,
        "🏠 Домашнее задание": TaskCategory.HOMEWORK,
        "📝 Экзамен": TaskCategory.EXAM,
        "💼 Проект": TaskCategory.PROJECT,
        "👤 Личное": TaskCategory.PERSONAL,
        "📦 Другое": TaskCategory.OTHER
    }

    if text not in category_map:
        await message.answer(
            "❌ Пожалуйста, выберите категорию из клавиатуры:\n"
            "Или отправьте 'отмена' для выхода",
            reply_markup=get_category_keyboard()
        )
        return

    data = await state.get_data()
    category = category_map[text]

    # Конвертируем deadline в локальное время для отображения в предпросмотре
    deadline_for_preview = None
    if data.get('deadline'):
        # deadline хранится в UTC, конвертируем в локальное для отображения
        deadline_for_preview = dates.to_local(data['deadline'])

    # Показываем предварительный просмотр
    preview = await _format_task_preview(
        title=data['title'],
        description=data.get('description'),
        deadline=deadline_for_preview,  # Используем локальное время для отображения
        priority=data['priority'],
        category=category
    )

    await state.update_data(category=category)
    await state.set_state(CreateTask.confirm)

    await message.answer(
        f"📋 **Предварительный просмотр задачи:**\n\n{preview}\n\n"
        "Всё верно?",
        reply_markup=get_confirm_keyboard(),
        parse_mode="Markdown"
    )


# app/bot/handlers/tasks/handlers.py

@router.message(Command("rems"))
async def cmd_test_reminders(message: Message):
    """Тестовая команда для проверки напоминаний"""
    integration = await get_integration()
    user_id = str(message.from_user.id)

    # Создаем тестовую задачу с дедлайном через 2 минуты
    from datetime import timedelta
    from bot.utils.dates import now

    test_deadline = now() + timedelta(minutes=2)

    try:
        task = await integration.task_service.create_task(
            user_id=user_id,
            title="🔴 ТЕСТОВАЯ ЗАДАЧА",
            description="Проверка напоминаний",
            deadline=test_deadline,
            reminder_minutes_before=[1]  # Напоминание за 1 минуту
        )

        await message.answer(
            f"✅ **Создана тестовая задача**\n\n"
            f"Название: {task.title}\n"
            f"Дедлайн: {test_deadline.strftime('%H:%M:%S')}\n"
            f"Напоминание через 1 минуту\n\n"
            f"Проверьте, придет ли уведомление!"
        )

    except Exception as e:
        logger.error(f"Error creating test task: {e}")
        await message.answer(f"❌ Ошибка: {e}")


@router.message(CreateTask.confirm)
async def task_confirm_handler(message: Message, state: FSMContext):
    """Подтверждает создание задачи и показывает главное меню"""
    text = message.text.strip()

    if text.lower() in ['отмена', 'cancel', 'стоп']:
        await state.clear()
        await message.answer(
            "❌ Создание задачи отменено",
            reply_markup=ReplyKeyboardRemove()
        )
        # Показываем главное меню после отмены
        from bot.handlers.menu.menu import show_main_menu
        await show_main_menu(message)
        return

    if text != "✅ Да, создать":
        await state.clear()
        await message.answer(
            "❌ Создание задачи отменено",
            reply_markup=ReplyKeyboardRemove()
        )
        # Показываем главное меню после отмены
        from bot.handlers.menu.menu import show_main_menu
        await show_main_menu(message)
        return

    integration = await get_integration()
    user_id = str(message.from_user.id)
    data = await state.get_data()

    try:
        # Создаем задачу (deadline уже в UTC из parse_deadline)
        task = await integration.task_service.create_task(
            user_id=user_id,
            title=data['title'],
            description=data.get('description'),
            priority=data['priority'],
            category=data['category'],
            deadline=data.get('deadline'),  # Это UTC
            reminder_minutes_before=config.REMINDER_BEFORE_DEADLINE if data.get('deadline') else None
        )

        await state.clear()

        # Форматируем дедлайн с учетом часового пояса
        deadline_str = "Не указан"
        if task.deadline:
            # Конвертируем UTC в локальное время для отображения
            local_deadline = dates.to_local(task.deadline)
            deadline_str = local_deadline.strftime('%d.%m.%Y %H:%M')

        # Отправляем сообщение об успешном создании
        await message.answer(
            f"✅ **Задача успешно создана!**\n\n"
            f"📌 *{task.title}*\n"
            f"📅 Дедлайн: {deadline_str}",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardRemove()
        )

        # Показываем главное меню
        from bot.handlers.menu.menu import show_main_menu
        await show_main_menu(message)

    except TaskValidationError as e:
        await state.clear()
        await message.answer(
            f"❌ **Ошибка:** {e}\n\n"
            f"Попробуйте создать задачу заново.",
            reply_markup=ReplyKeyboardRemove()
        )
        # Показываем главное меню даже при ошибке валидации
        from bot.handlers.menu.menu import show_main_menu
        await show_main_menu(message)

    except Exception as e:
        logger.error(f"Error creating task: {e}")
        await state.clear()
        await message.answer(
            "❌ **Произошла ошибка при создании задачи**\n\n"
            "Пожалуйста, попробуйте позже.",
            reply_markup=ReplyKeyboardRemove()
        )
        # Показываем главное меню при любой ошибке
        from bot.handlers.menu.menu import show_main_menu
        await show_main_menu(message)


# ==================== ДЕЙСТВИЯ С ЗАДАЧАМИ ====================

async def complete_task(callback: CallbackQuery, task_id: str):
    """Отметить задачу как выполненную"""
    integration = await get_integration()
    user_id = str(callback.from_user.id)

    try:
        task = await integration.task_service.complete_task(task_id, user_id)

        await callback.message.edit_text(
            f"✅ **Задача выполнена!**\n\n"
            f"Название: {task.title}\n\n"
            f"Поздравляю с выполнением! 🎉",
            reply_markup=get_tasks_main_keyboard(show_back=True)
        )

        # Отправляем уведомление
        if integration.notification_service:
            await integration.notification_service.send_notification(
                user_id=user_id,
                channel="telegram",
                title="🎉 Задача выполнена",
                content=f"Поздравляю! Задача '{task.title}' выполнена!",
                notification_type="task_completed",
                data={"task_id": task.id}
            )

    except TaskNotFoundError:
        await callback.message.edit_text(
            "❌ Задача не найдена",
            reply_markup=get_tasks_main_keyboard(show_back=True)
        )
    except Exception as e:
        logger.error(f"Error completing task: {e}")
        await callback.message.edit_text(
            "❌ Произошла ошибка",
            reply_markup=get_tasks_main_keyboard(show_back=True)
        )
    finally:
        await callback.answer()


async def delete_task(callback: CallbackQuery, task_id: str):
    """Удалить задачу"""
    integration = await get_integration()
    user_id = str(callback.from_user.id)

    try:
        success = await integration.task_service.delete_task(task_id, user_id)

        if success:
            await callback.message.edit_text(
                "✅ Задача успешно удалена",
                reply_markup=get_tasks_main_keyboard(show_back=True)
            )
        else:
            await callback.message.edit_text(
                "❌ Задача не найдена",
                reply_markup=get_tasks_main_keyboard(show_back=True)
            )

    except Exception as e:
        logger.error(f"Error deleting task: {e}")
        await callback.message.edit_text(
            "❌ Произошла ошибка при удалении",
            reply_markup=get_tasks_main_keyboard(show_back=True)
        )
    finally:
        await callback.answer()


async def postpone_task(callback: CallbackQuery, task_id: str):
    """Отложить задачу на 1 час"""
    integration = await get_integration()
    user_id = str(callback.from_user.id)

    try:
        task = await integration.task_service.get_task(task_id, user_id)

        if task.deadline:
            # Пересоздаем напоминание через час
            await integration.task_service.add_reminder(
                task_id, user_id,
                reminder_type=ReminderType.CUSTOM,
                custom_time=dates.now().replace(second=0) + timedelta(hours=1)
            )

        await callback.answer("⏰ Напомню через час!", show_alert=False)

    except Exception as e:
        logger.error(f"Error postponing task: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


# ==================== CALLBACK ХЕНДЛЕР ====================

# app/bot/handlers/tasks/handlers.py - исправленный task_callback_handler

# ==================== CALLBACK ХЕНДЛЕР ====================

async def task_callback_handler(callback: CallbackQuery, state: FSMContext):
    """Единый обработчик callback'ов от задач"""
    action = callback.data

    try:
        if action == "tasks_main":
            await show_tasks_menu(callback)

        elif action == "tasks_list":
            await show_tasks_list(callback, page=0)

        elif action.startswith("tasks_page_"):
            page = int(action.replace("tasks_page_", ""))
            await show_tasks_list(callback, page=page)

        elif action.startswith("task_view_"):
            task_id = action.replace("task_view_", "")
            await show_task_detail(callback, task_id)

        elif action.startswith("task_done_"):
            task_id = action.replace("task_done_", "")
            await complete_task(callback, task_id)

        elif action.startswith("task_delete_"):
            task_id = action.replace("task_delete_", "")
            await delete_task(callback, task_id)

        elif action.startswith("task_postpone_"):
            task_id = action.replace("task_postpone_", "")
            await postpone_task(callback, task_id)

        elif action == "tasks_stats":
            await show_task_stats(callback)

        elif action == "tasks_today":
            await show_today_tasks(callback)

        elif action == "tasks_overdue":
            await show_overdue_tasks(callback)

        elif action == "tasks_new":
            # Вызываем команду создания задачи
            await cmd_task_create(callback.message, state)
            await callback.answer()

        else:
            await callback.answer()

    except Exception as e:
        logger.error(f"Error in task callback handler: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)
