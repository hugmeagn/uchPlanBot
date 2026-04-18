"""
Хендлеры для работы с задачами
"""
import logging
from datetime import datetime, timedelta
from typing import Optional, List

from ..vk_api.client import VkMessage
from ..keyboards.tasks import (
    get_tasks_menu_keyboard,
    get_task_detail_keyboard,
    get_priority_keyboard,
    get_category_keyboard
)
from ..keyboards.base import create_back_keyboard, create_confirm_keyboard, create_pagination_keyboard
from ..handlers import router
from models.user import User
from services.tasks.service import (
    TaskStatus, TaskPriority, TaskCategory,
    ReminderType, TaskNotFoundError
)
from services.tasks.utils import parse_deadline, format_time_left
from ..utils.vk_utils import format_message, create_keyboard, create_text_button
import bot.utils.dates as dates

logger = logging.getLogger(__name__)

# Состояния FSM для создания задачи
STATE_TASK_TITLE = "task_title"
STATE_TASK_DESCRIPTION = "task_description"
STATE_TASK_DEADLINE = "task_deadline"
STATE_TASK_PRIORITY = "task_priority"
STATE_TASK_CATEGORY = "task_category"
STATE_TASK_CONFIRM = "task_confirm"


@router.command("tasks")
@router.callback("menu_tasks")
async def show_tasks_menu(message: VkMessage, state: Optional[str], data: dict):
    """Показывает главное меню задач"""
    vk = data['vk']
    fsm = data['fsm']
    user_id = message.from_id

    await fsm.clear(user_id)

    text = (
        "📋 **Управление задачами**\n\n"
        "Выберите действие:"
    )

    await vk.send_message(
        peer_id=user_id,
        text=format_message(text),
        keyboard=get_tasks_menu_keyboard()
    )


@router.callback("tasks_list")
async def show_tasks_list(message: VkMessage, state: Optional[str], data: dict, page: int = 0):
    """Показывает список задач с пагинацией"""
    vk = data['vk']
    task_service = data['task_service']
    user_id = message.from_id

    try:
        tasks = await task_service.list_tasks(
            user_id=str(user_id),
            show_completed=False,
            limit=50
        )

        if not tasks:
            await vk.send_message(
                peer_id=user_id,
                text="📭 **У вас пока нет активных задач**\n\nСоздайте новую задачу!",
                keyboard=get_tasks_menu_keyboard()
            )
            return

        # Пагинация
        page_size = 5
        total_pages = (len(tasks) + page_size - 1) // page_size
        page_tasks = tasks[page * page_size:(page + 1) * page_size]

        text = "📋 **Ваши активные задачи:**\n\n"

        for i, task in enumerate(page_tasks, 1 + page * page_size):
            priority_emoji = {
                TaskPriority.LOW: "⚪",
                TaskPriority.MEDIUM: "🟡",
                TaskPriority.HIGH: "🟠",
                TaskPriority.CRITICAL: "🔴"
            }.get(task.priority, "⚪")

            deadline_text = ""
            if task.deadline:
                if task.deadline < dates.now():
                    deadline_text = " — ⚠️ ПРОСРОЧЕНО!"
                else:
                    time_left = format_time_left(task.deadline)
                    deadline_text = f" — {time_left}"

            text += f"{i}. {priority_emoji} {task.title}{deadline_text}\n"

        # Создаем клавиатуру с задачами и пагинацией
        buttons = []

        for task in page_tasks:
            title = task.title
            # Обрезаем до 37 символов (с запасом для "...")
            if len(title) > 37:
                title = title[:37] + "..."

            buttons.append([create_text_button(
                f"📌 {title}",
                {"callback": f"task_view_{task.id}"},
                "primary"
            )])

        if total_pages > 1:
            pagination_row = []
            if page > 0:
                pagination_row.append(create_text_button("◀️", {"callback": f"tasks_page_{page - 1}"}, "secondary"))
            pagination_row.append(
                create_text_button(f"{page + 1}/{total_pages}", {"callback": "tasks_current"}, "primary"))
            if page < total_pages - 1:
                pagination_row.append(create_text_button("▶️", {"callback": f"tasks_page_{page + 1}"}, "secondary"))
            buttons.append(pagination_row)

        buttons.append([create_text_button("➕ Новая задача", {"callback": "tasks_new"}, "positive")])
        buttons.append([create_text_button("↩️ Назад", {"callback": "tasks_main"}, "secondary")])

        await vk.send_message(
            peer_id=user_id,
            text=format_message(text),
            keyboard=create_keyboard(buttons)
        )

    except Exception as e:
        logger.error(f"Error showing tasks: {e}", exc_info=True)
        await vk.send_message(
            peer_id=user_id,
            text="❌ Ошибка при получении задач.",
            keyboard=create_back_keyboard("tasks_main")
        )


@router.callback("tasks_page_")
async def handle_tasks_pagination(message: VkMessage, state: Optional[str], data: dict):
    """Обрабатывает пагинацию списка задач"""
    callback = message.payload.get("callback")
    page = int(callback.replace("tasks_page_", ""))
    await show_tasks_list(message, state, data, page)


@router.callback("tasks_new")
@router.callback("menu_add_task")
async def start_task_creation(message: VkMessage, state: Optional[str], data: dict):
    """Начинает создание новой задачи"""
    vk = data['vk']
    fsm = data['fsm']
    user_id = message.from_id

    await fsm.set_state(user_id, STATE_TASK_TITLE)
    await fsm.set_data(user_id, {})

    text = (
        "📝 **Создание новой задачи**\n\n"
        "Введите **название** задачи (или отправьте 'отмена' для выхода):"
    )

    await vk.send_message(
        peer_id=user_id,
        text=format_message(text),
        keyboard=create_back_keyboard("tasks_main")
    )


@router.message(STATE_TASK_TITLE)
async def handle_task_title(message: VkMessage, state: Optional[str], data: dict):
    """Обрабатывает ввод названия задачи"""
    vk = data['vk']
    fsm = data['fsm']
    user_id = message.from_id

    title = message.text.strip()

    if title.lower() in ['отмена', 'cancel']:
        await fsm.clear(user_id)
        await show_tasks_menu(message, state, data)
        return

    if len(title) < 3 or len(title) > 100:
        await vk.send_message(
            peer_id=user_id,
            text="❌ Название должно быть от 3 до 100 символов.",
            keyboard=create_back_keyboard("tasks_main")
        )
        return

    await fsm.update_data(user_id, title=title)
    await fsm.set_state(user_id, STATE_TASK_DESCRIPTION)

    await vk.send_message(
        peer_id=user_id,
        text="📝 Введите **описание** задачи (или отправьте '-' чтобы пропустить):",
        keyboard=create_back_keyboard("tasks_main")
    )


@router.message(STATE_TASK_DESCRIPTION)
async def handle_task_description(message: VkMessage, state: Optional[str], data: dict):
    """Обрабатывает ввод описания задачи"""
    vk = data['vk']
    fsm = data['fsm']
    user_id = message.from_id

    text = message.text.strip()

    if text.lower() in ['отмена', 'cancel']:
        await fsm.clear(user_id)
        await show_tasks_menu(message, state, data)
        return

    description = None if text == "-" else text

    await fsm.update_data(user_id, description=description)
    await fsm.set_state(user_id, STATE_TASK_DEADLINE)

    await vk.send_message(
        peer_id=user_id,
        text=(
            "🗓 Введите **дедлайн** задачи (или отправьте '-' чтобы пропустить):\n\n"
            "**Примеры:**\n"
            "• завтра 18:00\n"
            "• 25.12 15:30\n"
            "• через 2 часа"
        ),
        keyboard=create_back_keyboard("tasks_main")
    )


@router.message(STATE_TASK_DEADLINE)
async def handle_task_deadline(message: VkMessage, state: Optional[str], data: dict):
    """Обрабатывает ввод дедлайна"""
    vk = data['vk']
    fsm = data['fsm']
    user_id = message.from_id

    text = message.text.strip()

    if text.lower() in ['отмена', 'cancel']:
        await fsm.clear(user_id)
        await show_tasks_menu(message, state, data)
        return

    deadline = None

    if text != "-":
        deadline = parse_deadline(text)
        if not deadline:
            await vk.send_message(
                peer_id=user_id,
                text="❌ Не удалось распознать дату. Попробуйте еще раз.",
                keyboard=create_back_keyboard("tasks_main")
            )
            return

    await fsm.update_data(user_id, deadline=deadline)
    await fsm.set_state(user_id, STATE_TASK_PRIORITY)

    await vk.send_message(
        peer_id=user_id,
        text="⚡ Выберите **приоритет** задачи:",
        keyboard=get_priority_keyboard()
    )


@router.callback("priority_low")
@router.callback("priority_medium")
@router.callback("priority_high")
@router.callback("priority_critical")
async def handle_task_priority(message: VkMessage, state: Optional[str], data: dict):
    """Обрабатывает выбор приоритета"""
    vk = data['vk']
    fsm = data['fsm']
    user_id = message.from_id

    callback = message.payload.get("callback")

    priority_map = {
        "priority_low": TaskPriority.LOW,
        "priority_medium": TaskPriority.MEDIUM,
        "priority_high": TaskPriority.HIGH,
        "priority_critical": TaskPriority.CRITICAL
    }

    priority = priority_map.get(callback, TaskPriority.MEDIUM)

    await fsm.update_data(user_id, priority=priority)
    await fsm.set_state(user_id, STATE_TASK_CATEGORY)

    await vk.send_message(
        peer_id=user_id,
        text="📂 Выберите **категорию** задачи:",
        keyboard=get_category_keyboard()
    )


@router.callback("category_study")
@router.callback("category_homework")
@router.callback("category_exam")
@router.callback("category_project")
@router.callback("category_personal")
@router.callback("category_other")
async def handle_task_category(message: VkMessage, state: Optional[str], data: dict):
    """Обрабатывает выбор категории"""
    vk = data['vk']
    fsm = data['fsm']
    user_id = message.from_id

    callback = message.payload.get("callback")

    category_map = {
        "category_study": TaskCategory.STUDY,
        "category_homework": TaskCategory.HOMEWORK,
        "category_exam": TaskCategory.EXAM,
        "category_project": TaskCategory.PROJECT,
        "category_personal": TaskCategory.PERSONAL,
        "category_other": TaskCategory.OTHER
    }

    category = category_map.get(callback, TaskCategory.OTHER)

    fsm_data = await fsm.get_data(user_id)
    await fsm.update_data(user_id, category=category)
    await fsm.set_state(user_id, STATE_TASK_CONFIRM)

    # Формируем предпросмотр
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

    preview = f"**Название:** {fsm_data['title']}\n"

    if fsm_data.get('description'):
        preview += f"**Описание:** {fsm_data['description'][:100]}\n"

    if fsm_data.get('deadline'):
        local_deadline = dates.to_local(fsm_data['deadline'])
        preview += f"**Дедлайн:** {local_deadline.strftime('%d.%m.%Y %H:%M')}\n"

    preview += f"**Приоритет:** {priority_names.get(fsm_data['priority'], 'Средний')}\n"
    preview += f"**Категория:** {category_names.get(category, '📦 Другое')}"

    await vk.send_message(
        peer_id=user_id,
        text=format_message(f"📋 **Предварительный просмотр:**\n\n{preview}\n\nВсё верно?"),
        keyboard=create_confirm_keyboard("task_confirm", "task_cancel")
    )


@router.callback("task_confirm")
async def confirm_task_creation(message: VkMessage, state: Optional[str], data: dict):
    """Подтверждает создание задачи"""
    vk = data['vk']
    fsm = data['fsm']
    task_service = data['task_service']
    user_id = message.from_id

    fsm_data = await fsm.get_data(user_id)

    try:
        import config

        task = await task_service.create_task(
            user_id=str(user_id),
            title=fsm_data['title'],
            description=fsm_data.get('description'),
            priority=fsm_data['priority'],
            category=fsm_data['category'],
            deadline=fsm_data.get('deadline'),
            reminder_minutes_before=config.REMINDER_BEFORE_DEADLINE if fsm_data.get('deadline') else None
        )

        await fsm.clear(user_id)

        deadline_str = "Не указан"
        if task.deadline:
            local_deadline = dates.to_local(task.deadline)
            deadline_str = local_deadline.strftime('%d.%m.%Y %H:%M')

        await vk.send_message(
            peer_id=user_id,
            text=format_message(
                f"✅ **Задача успешно создана!**\n\n"
                f"📌 {task.title}\n"
                f"📅 Дедлайн: {deadline_str}"
            )
        )

        await show_tasks_menu(message, state, data)

    except Exception as e:
        logger.error(f"Error creating task: {e}", exc_info=True)
        await fsm.clear(user_id)
        await vk.send_message(
            peer_id=user_id,
            text="❌ Ошибка при создании задачи.",
            keyboard=create_back_keyboard("tasks_main")
        )


@router.callback("task_cancel")
async def cancel_task_creation(message: VkMessage, state: Optional[str], data: dict):
    """Отменяет создание задачи"""
    vk = data['vk']
    fsm = data['fsm']
    user_id = message.from_id

    await fsm.clear(user_id)

    await vk.send_message(
        peer_id=user_id,
        text="❌ Создание задачи отменено."
    )

    await show_tasks_menu(message, state, data)


@router.callback("task_view_")
async def show_task_detail(message: VkMessage, state: Optional[str], data: dict):
    """Показывает детальную информацию о задаче"""
    vk = data['vk']
    task_service = data['task_service']
    user_id = message.from_id

    callback = message.payload.get("callback")
    task_id = callback.replace("task_view_", "")

    try:
        task = await task_service.get_task(task_id, str(user_id))

        priority_names = {
            TaskPriority.LOW: "Низкий",
            TaskPriority.MEDIUM: "Средний",
            TaskPriority.HIGH: "Высокий",
            TaskPriority.CRITICAL: "Критичный"
        }

        text = f"📋 **{task.title}**\n\n"

        if task.description:
            text += f"📝 **Описание:**\n{task.description}\n\n"

        if task.deadline:
            local_deadline = dates.to_local(task.deadline)
            time_left = format_time_left(task.deadline)
            deadline_status = " ⚠️ ПРОСРОЧЕНО!" if task.deadline < dates.now() else ""

            text += f"🗓 **Дедлайн:** {local_deadline.strftime('%d.%m.%Y %H:%M')}\n"
            text += f"⏳ **Осталось:** {time_left}{deadline_status}\n\n"

        text += f"⚡ **Приоритет:** {priority_names.get(task.priority, 'Средний')}\n"
        text += f"📊 **Статус:** {'✅ Выполнена' if task.status == TaskStatus.COMPLETED else '⏳ Активна'}\n"

        is_completed = task.status == TaskStatus.COMPLETED

        await vk.send_message(
            peer_id=user_id,
            text=format_message(text),
            keyboard=get_task_detail_keyboard(task_id, is_completed)
        )

    except TaskNotFoundError:
        await vk.send_message(
            peer_id=user_id,
            text="❌ Задача не найдена.",
            keyboard=create_back_keyboard("tasks_list")
        )


@router.callback("task_done_")
async def complete_task(message: VkMessage, state: Optional[str], data: dict):
    """Отмечает задачу как выполненную"""
    vk = data['vk']
    task_service = data['task_service']
    user_id = message.from_id

    callback = message.payload.get("callback")
    task_id = callback.replace("task_done_", "")

    try:
        task = await task_service.complete_task(task_id, str(user_id))

        await vk.send_message(
            peer_id=user_id,
            text=format_message(f"✅ **Задача выполнена!**\n\n{task.title}\n\nПоздравляю! 🎉")
        )

        await show_tasks_menu(message, state, data)

    except Exception as e:
        logger.error(f"Error completing task: {e}")
        await vk.send_message(
            peer_id=user_id,
            text="❌ Ошибка при выполнении задачи.",
            keyboard=create_back_keyboard("tasks_main")
        )


@router.callback("task_delete_")
async def delete_task(message: VkMessage, state: Optional[str], data: dict):
    """Удаляет задачу"""
    vk = data['vk']
    task_service = data['task_service']
    user_id = message.from_id

    callback = message.payload.get("callback")
    task_id = callback.replace("task_delete_", "")

    try:
        success = await task_service.delete_task(task_id, str(user_id))

        if success:
            await vk.send_message(
                peer_id=user_id,
                text="✅ Задача успешно удалена."
            )
        else:
            await vk.send_message(
                peer_id=user_id,
                text="❌ Задача не найдена."
            )

        await show_tasks_menu(message, state, data)

    except Exception as e:
        logger.error(f"Error deleting task: {e}")
        await vk.send_message(
            peer_id=user_id,
            text="❌ Ошибка при удалении задачи.",
            keyboard=create_back_keyboard("tasks_main")
        )


@router.callback("tasks_stats")
@router.callback("menu_task_stats")
async def show_task_stats(message: VkMessage, state: Optional[str], data: dict):
    """Показывает статистику по задачам"""
    vk = data['vk']
    task_service = data['task_service']
    user_id = message.from_id

    try:
        stats = await task_service.get_stats(str(user_id))

        text = (
            "📊 **Статистика задач**\n\n"
            f"📋 **Всего задач:** {stats.total}\n"
            f"✅ **Активных:** {stats.active}\n"
            f"✔️ **Выполнено:** {stats.completed}\n"
            f"⚠️ **Просрочено:** {stats.overdue}\n"
            f"📦 **В архиве:** {stats.archived}\n"
        )

        if hasattr(stats, 'upcoming_deadlines') and stats.upcoming_deadlines > 0:
            text += f"\n⏰ **Ближайших дедлайнов (24ч):** {stats.upcoming_deadlines}\n"

        await vk.send_message(
            peer_id=user_id,
            text=format_message(text),
            keyboard=create_back_keyboard("tasks_main")
        )

    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        await vk.send_message(
            peer_id=user_id,
            text="❌ Ошибка при получении статистики.",
            keyboard=create_back_keyboard("tasks_main")
        )


@router.callback("tasks_today")
@router.callback("menu_today")
async def show_today_tasks(message: VkMessage, state: Optional[str], data: dict):
    """Показывает задачи на сегодня"""
    vk = data['vk']
    task_service = data['task_service']
    user_id = message.from_id

    try:
        all_tasks = await task_service.list_tasks(
            user_id=str(user_id),
            show_completed=False
        )

        today = dates.now().date()
        tasks = [t for t in all_tasks if t.deadline and t.deadline.date() == today]

        if not tasks:
            await vk.send_message(
                peer_id=user_id,
                text="✅ **На сегодня задач нет!**\n\nМожно отдохнуть или создать новую задачу.",
                keyboard=create_back_keyboard("tasks_main")
            )
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
            text += f"{priority_emoji} {task.title} — {time_str}\n"

        await vk.send_message(
            peer_id=user_id,
            text=format_message(text),
            keyboard=create_back_keyboard("tasks_main")
        )

    except Exception as e:
        logger.error(f"Error showing today tasks: {e}")
        await vk.send_message(
            peer_id=user_id,
            text="❌ Ошибка.",
            keyboard=create_back_keyboard("tasks_main")
        )


@router.callback("tasks_overdue")
@router.callback("menu_overdue")
async def show_overdue_tasks(message: VkMessage, state: Optional[str], data: dict):
    """Показывает просроченные задачи"""
    vk = data['vk']
    task_service = data['task_service']
    user_id = message.from_id

    try:
        all_tasks = await task_service.list_tasks(
            user_id=str(user_id),
            show_completed=False,
            limit=1000
        )

        now = dates.now()
        overdue_tasks = [t for t in all_tasks if t.deadline and t.deadline < now]

        if not overdue_tasks:
            await vk.send_message(
                peer_id=user_id,
                text="✅ **Просроченных задач нет!**\n\nОтлично! Вы всё успеваете.",
                keyboard=create_back_keyboard("tasks_main")
            )
            return

        text = "⚠️ **Просроченные задачи:**\n\n"

        for task in overdue_tasks:
            days_overdue = (now - task.deadline).days if task.deadline else 0
            text += f"🔴 {task.title} — просрочено на {days_overdue} дн.\n"

        await vk.send_message(
            peer_id=user_id,
            text=format_message(text),
            keyboard=create_back_keyboard("tasks_main")
        )

    except Exception as e:
        logger.error(f"Error showing overdue tasks: {e}")
        await vk.send_message(
            peer_id=user_id,
            text="❌ Ошибка.",
            keyboard=create_back_keyboard("tasks_main")
        )


@router.callback("tasks_main")
async def back_to_tasks_menu(message: VkMessage, state: Optional[str], data: dict):
    """Возврат в меню задач"""
    await show_tasks_menu(message, state, data)
