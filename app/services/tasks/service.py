from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
import asyncio
import logging
from collections import defaultdict

from bot.utils import dates
from .models import (
    Task, TaskReminder, TaskFilter, TaskStats
)
from .enums import (
    TaskStatus, TaskPriority, TaskCategory,
    ReminderType, SortField, SortOrder
)
from .repository import TaskRepository
from .exceptions import (
    TaskNotFoundError, TaskValidationError,
    ReminderError
)
from ..notifications.models import NotificationType

logger = logging.getLogger(__name__)


class TaskService:
    """Сервис для управления задачами"""

    def __init__(
            self,
            repository: TaskRepository,
            notification_service=None  # Опционально: сервис уведомлений
    ):
        self.repository = repository
        self.notification_service = notification_service

        # Кэш для быстрого доступа
        self._cache: Dict[str, Dict[str, Task]] = defaultdict(dict)

        # Запускаем фоновые задачи
        self._background_tasks = []
        self._start_background_tasks()

    # Добавьте этот метод в класс TaskService
    def _now(self) -> datetime:
        """Возвращает текущее время в UTC (aware)"""
        return dates.now()

    def _start_background_tasks(self):
        """Запускает фоновые задачи"""
        self._background_tasks.append(
            asyncio.create_task(self._check_deadlines_loop())
        )
        self._background_tasks.append(
            asyncio.create_task(self._check_reminders_loop())
        )

    async def _check_deadlines_loop(self):
        """Фоновый цикл проверки дедлайнов"""
        while True:
            try:
                await self._check_overdue_tasks()
                await asyncio.sleep(60)  # Проверяем каждую минуту
            except Exception as e:
                logger.error(f"Error in deadlines check loop: {e}")
                await asyncio.sleep(60)

    async def _check_reminders_loop(self):
        """Фоновый цикл проверки напоминаний"""
        while True:
            try:
                if self.notification_service:
                    await self._process_reminders()
                await asyncio.sleep(30)  # Проверяем каждые 30 секунд
            except Exception as e:
                logger.error(f"Error in reminders check loop: {e}")
                await asyncio.sleep(30)

    async def _check_overdue_tasks(self):
        """Проверяет и обновляет просроченные задачи"""
        # В реальном приложении нужно получать всех пользователей
        # Здесь для примера просто проверяем все задачи
        all_users = set()  # Нужно получать из репозитория

        for user_id in all_users:
            overdue_tasks = await self.repository.get_overdue_tasks(user_id)

            for task in overdue_tasks:
                if task.status == TaskStatus.ACTIVE:
                    task.status = TaskStatus.OVERDUE
                    task.updated_at = self._now()
                    await self.repository.update(task)

                    # Отправляем уведомление о просрочке
                    if self.notification_service and task.reminder_enabled:
                        await self._send_overdue_notification(task)

    # app/services/tasks/service.py - исправленный метод _process_reminders

    async def _process_reminders(self):
        """Обрабатывает напоминания"""
        if not self.notification_service:
            logger.warning("Notification service not available, cannot process reminders")
            return

        logger.info("Starting reminder processing cycle")
        now = dates.now()
        logger.info(f"Current time (ekat): {now}")

        try:
            # Получаем всех пользователей
            from models.user import User
            users = await User.all()

            total_tasks_with_reminders = 0

            for user in users:
                user_id = str(user.telegram_id)

                # Получаем активные задачи пользователя с дедлайнами
                # Используем прямой запрос к модели для получения задач с reminders
                from models.task import TaskModel

                # Находим задачи, у которых есть неотправленные напоминания
                db_tasks = await TaskModel.filter(
                    user_id=user_id,
                    status=TaskStatus.ACTIVE.value,
                    reminder_enabled=True,
                    deadline__isnull=False
                ).prefetch_related('reminders')

                for db_task in db_tasks:
                    # Конвертируем в модель Task с напоминаниями
                    reminders = []
                    for db_reminder in db_task.reminders:
                        if not db_reminder.sent:  # Только неотправленные
                            reminder_dict = db_reminder.__dict__
                            reminders.append(TaskReminder.model_validate(reminder_dict))

                    if not reminders:
                        continue  # Нет неотправленных напоминаний

                    total_tasks_with_reminders += 1

                    task_dict = db_task.__dict__
                    task_dict['reminders'] = reminders
                    task = Task.model_validate(task_dict)

                    for reminder in reminders:
                        # Проверяем, нужно ли отправить напоминание
                        should_send = self._check_reminder_time(task, reminder, now)

                        if should_send:
                            logger.info(f"Should send reminder for task {task.id}, reminder {reminder.id}")
                            await self._send_reminder_notification(task, reminder)

                            # Отмечаем напоминание как отправленное в БД
                            await self._mark_reminder_sent(reminder.id, now)
                        else:
                            # Логируем время до отправки
                            if task.deadline and reminder.time_before:
                                reminder_time = task.deadline - timedelta(minutes=reminder.time_before)
                                time_diff = (reminder_time - now).total_seconds()
                                if -60 < time_diff < 3600:
                                    logger.info(f"Reminder {reminder.id} will be sent in {time_diff / 60:.1f} minutes")

            logger.info(f"Reminder processing completed. Checked {total_tasks_with_reminders} tasks with reminders")

        except Exception as e:
            logger.error(f"Error in _process_reminders: {e}", exc_info=True)

    async def _mark_reminder_sent(self, reminder_id: str, sent_at: datetime):
        """Отмечает напоминание как отправленное в БД"""
        try:
            from models.task import TaskReminderModel
            await TaskReminderModel.filter(id=reminder_id).update(
                sent=True,
                sent_at=sent_at
            )
            logger.debug(f"Marked reminder {reminder_id} as sent")
        except Exception as e:
            logger.error(f"Error marking reminder as sent: {e}")

    def _check_reminder_time(
            self,
            task: Task,
            reminder: TaskReminder,
            now: datetime
    ) -> bool:
        """Проверяет, пора ли отправлять напоминание"""
        if not task.deadline:
            return False

        if reminder.reminder_type == ReminderType.AT_DEADLINE:
            return abs((task.deadline - now).total_seconds()) < 60  # В пределах минуты

        elif reminder.reminder_type == ReminderType.BEFORE_DEADLINE:
            if reminder.time_before:
                reminder_time = task.deadline - timedelta(minutes=reminder.time_before)
                return abs((reminder_time - now).total_seconds()) < 60

        elif reminder.reminder_type == ReminderType.CUSTOM:
            if reminder.custom_time:
                return abs((reminder.custom_time - now).total_seconds()) < 60

        return False

    async def _send_reminder_notification(self, task: Task, reminder: TaskReminder):
        """Отправляет уведомление-напоминание"""
        if not self.notification_service:
            logger.error("Cannot send reminder: notification service not available")
            return

        logger.info(f"Sending reminder notification for task {task.id}")

        # Определяем текст уведомления
        now = dates.now()
        time_left = task.deadline - now
        hours = time_left.total_seconds() // 3600
        minutes = (time_left.total_seconds() % 3600) // 60

        if hours > 0:
            time_text = f"через {int(hours)}ч {int(minutes)}м"
        else:
            time_text = f"через {int(minutes)}м"

        title = f"⏰ Напоминание: {task.title}"

        if reminder.reminder_type == ReminderType.AT_DEADLINE:
            content = f"Срок выполнения задачи '{task.title}' наступает сейчас!"
        else:
            content = f"Задача '{task.title}' должна быть выполнена {time_text}"

        # Добавляем описание если есть
        if task.description:
            content += f"\n\n📝 {task.description[:100]}"

        # Конвертируем приоритет в число (0, 1, 2, 3)
        notification_priority = self._priority_to_notification(task.priority)
        logger.info(f"Task priority: {task.priority} -> notification priority: {notification_priority}")

        # Отправляем уведомление
        try:
            notification = await self.notification_service.send_notification(
                user_id=task.user_id,
                channel="telegram",  # или NotificationChannel.TELEGRAM
                title=title,
                content=content,
                notification_type=NotificationType.TASK_REMINDER.value,  # "task_reminder"
                priority=notification_priority,  # Теперь передаем число 0,1,2,3
                data={
                    "task_id": task.id,
                    "reminder_id": reminder.id,
                    "buttons": [
                        {
                            "text": "✅ Выполнено",
                            "callback_data": f"task_done_{task.id}"
                        },
                        {
                            "text": "⏰ Отложить на час",
                            "callback_data": f"task_postpone_{task.id}"
                        },
                        {
                            "text": "👀 Посмотреть",
                            "callback_data": f"task_view_{task.id}"
                        }
                    ]
                }
            )

            if notification:
                logger.info(f"Notification sent with ID: {notification.id}")
                reminder.notification_id = notification.id
            else:
                logger.error("Failed to send notification: no notification returned")

        except Exception as e:
            logger.error(f"Error sending notification: {e}", exc_info=True)

    async def _send_overdue_notification(self, task: Task):
        """Отправляет уведомление о просрочке"""
        if not self.notification_service:
            return

        await self.notification_service.send_notification(
            user_id=task.user_id,
            channel="telegram",
            title="⚠️ ПРОСРОЧЕНО!",
            content=f"Задача '{task.title}' просрочена!",
            notification_type="task_overdue",
            priority="high",
            data={
                "task_id": task.id,
                "buttons": [
                    {
                        "text": "✅ Выполнено",
                        "callback_data": f"task_done_{task.id}"
                    },
                    {
                        "text": "📅 Перенести",
                        "callback_data": f"task_reschedule_{task.id}"
                    }
                ]
            }
        )

    def _priority_to_notification(self, priority: TaskPriority) -> int:
        """
        Конвертирует приоритет задачи в числовой приоритет уведомления

        TaskPriority и NotificationPriority имеют одинаковые значения:
            LOW = 0
            MEDIUM = 1
            HIGH = 2
            CRITICAL = 3
        """
        if isinstance(priority, TaskPriority):
            return priority.value

        # Если пришло строкой
        mapping = {
            'low': 0,
            'medium': 1,
            'high': 2,
            'critical': 3,
            0: 0, 1: 1, 2: 2, 3: 3
        }
        result = mapping.get(priority, 1)  # По умолчанию MEDIUM
        logger.debug(f"Converted priority {priority} to {result}")
        return result

    async def create_task(
            self,
            user_id: str,
            title: str,
            description: Optional[str] = None,
            category: TaskCategory = TaskCategory.OTHER,
            priority: TaskPriority = TaskPriority.MEDIUM,
            deadline: Optional[datetime] = None,
            tags: List[str] = None,
            reminder_minutes_before: Optional[List[int]] = None,
            **kwargs
    ) -> Task:
        """
        Создает новую задачу
        """
        # Валидация
        if not title or len(title.strip()) == 0:
            raise TaskValidationError("Title cannot be empty")

        if len(title) > 200:
            raise TaskValidationError("Title is too long (max 200 chars)")

        if description and len(description) > 2000:
            raise TaskValidationError("Description is too long (max 2000 chars)")

        # Создаем задачу
        task = Task(
            user_id=user_id,
            title=title.strip(),
            description=description.strip() if description else None,
            category=category,
            priority=priority,
            deadline=deadline,
            tags=tags or [],
            **kwargs
        )

        # Добавляем напоминания
        if deadline and reminder_minutes_before:
            logger.info(f"Adding {len(reminder_minutes_before)} reminders for task")
            for minutes in reminder_minutes_before:
                reminder = TaskReminder(
                    task_id=task.id,
                    reminder_type=ReminderType.BEFORE_DEADLINE,
                    time_before=minutes
                )
                task.reminders.append(reminder)

        # Сохраняем в БД
        created_task = await self.repository.create(task)

        # Кэшируем
        self._cache[user_id][created_task.id] = created_task

        logger.info(f"Task created: {created_task.id} for user {user_id}")

        return created_task

    async def get_task(self, task_id: str, user_id: str) -> Task:
        """
        Получает задачу по ID
        """
        # Проверяем кэш
        if task_id in self._cache.get(user_id, {}):
            return self._cache[user_id][task_id]

        # Ищем в БД
        task = await self.repository.get(task_id, user_id)

        if not task:
            raise TaskNotFoundError(f"Task {task_id} not found")

        # Кэшируем
        self._cache[user_id][task_id] = task

        return task

    async def update_task(
            self,
            task_id: str,
            user_id: str,
            **updates
    ) -> Task:
        """
        Обновляет задачу
        """
        task = await self.get_task(task_id, user_id)

        # Обновляем поля
        for key, value in updates.items():
            if hasattr(task, key) and value is not None:
                setattr(task, key, value)

        task.updated_at = self._now()

        # Если задача помечена как выполненная
        if updates.get('status') == TaskStatus.COMPLETED:
            task.completed_at = self._now()
            task.progress = 100

        # Сохраняем
        updated_task = await self.repository.update(task)

        # Обновляем кэш
        self._cache[user_id][task_id] = updated_task

        return updated_task

    async def delete_task(self, task_id: str, user_id: str) -> bool:
        """
        Удаляет задачу
        """
        result = await self.repository.delete(task_id, user_id)

        if result and user_id in self._cache:
            self._cache[user_id].pop(task_id, None)

        return result

    async def complete_task(self, task_id: str, user_id: str) -> Task:
        """
        Отмечает задачу как выполненную
        """
        task = await self.get_task(task_id, user_id)
        task.mark_completed()

        updated_task = await self.repository.update(task)
        self._cache[user_id][task_id] = updated_task

        return updated_task

    async def list_tasks(
            self,
            user_id: str,
            status: Optional[List[TaskStatus]] = None,
            category: Optional[List[TaskCategory]] = None,
            priority: Optional[List[TaskPriority]] = None,
            tags: Optional[List[str]] = None,
            search: Optional[str] = None,
            show_completed: bool = False,
            sort_by: SortField = SortField.DEADLINE,
            sort_order: SortOrder = SortOrder.ASC,
            limit: int = 100,
            offset: int = 0
    ) -> List[Task]:
        """
        Получает список задач с фильтрацией
        """
        # Создаем фильтр
        filter_params = TaskFilter()

        if status:
            filter_params.status = status
        elif not show_completed:
            filter_params.status = [TaskStatus.ACTIVE, TaskStatus.OVERDUE]

        if category:
            filter_params.category = category

        if priority:
            filter_params.priority = priority

        if tags:
            filter_params.tags = tags

        if search:
            filter_params.search_text = search

        # Получаем задачи
        tasks = await self.repository.list(
            user_id=user_id,
            filter_params=filter_params,
            sort_by=sort_by.value,
            sort_order=sort_order.value,
            limit=limit,
            offset=offset
        )

        # Обновляем кэш
        for task in tasks:
            self._cache[user_id][task.id] = task

        return tasks

    async def get_stats(self, user_id: str) -> TaskStats:
        """
        Получает статистику по задачам пользователя
        """
        return await self.repository.get_stats(user_id)

    async def add_reminder(
            self,
            task_id: str,
            user_id: str,
            reminder_type: ReminderType,
            time_before: Optional[int] = None,
            custom_time: Optional[datetime] = None
    ) -> Task:
        """
        Добавляет напоминание к задаче
        """
        task = await self.get_task(task_id, user_id)

        if not task.deadline and reminder_type != ReminderType.CUSTOM:
            raise ReminderError("Cannot add deadline reminder to task without deadline")

        if reminder_type == ReminderType.BEFORE_DEADLINE and not time_before:
            raise ReminderError("time_before required for BEFORE_DEADLINE reminder")

        if reminder_type == ReminderType.CUSTOM and not custom_time:
            raise ReminderError("custom_time required for CUSTOM reminder")

        if reminder_type == ReminderType.CUSTOM and custom_time and custom_time < self._now():
            raise ReminderError("Custom reminder time cannot be in the past")

        reminder = TaskReminder(
            task_id=task.id,
            reminder_type=reminder_type,
            time_before=time_before,
            custom_time=custom_time
        )

        task.reminders.append(reminder)
        task.updated_at = self._now()

        updated_task = await self.repository.update(task)
        self._cache[user_id][task_id] = updated_task

        return updated_task

    async def remove_reminder(
            self,
            task_id: str,
            user_id: str,
            reminder_id: str
    ) -> Task:
        """
        Удаляет напоминание
        """
        task = await self.get_task(task_id, user_id)

        task.reminders = [r for r in task.reminders if r.id != reminder_id]
        task.updated_at = self._now()

        updated_task = await self.repository.update(task)
        self._cache[user_id][task_id] = updated_task

        return updated_task

    async def toggle_reminders(self, task_id: str, user_id: str, enabled: bool) -> Task:
        """
        Включает/выключает напоминания для задачи
        """
        task = await self.get_task(task_id, user_id)
        task.reminder_enabled = enabled
        task.updated_at = self._now()

        updated_task = await self.repository.update(task)
        self._cache[user_id][task_id] = updated_task

        return updated_task

    async def search_tasks(
            self,
            user_id: str,
            query: str,
            limit: int = 20
    ) -> List[Task]:
        """
        Поиск задач по тексту
        """
        filter_params = TaskFilter(search_text=query)

        return await self.repository.list(
            user_id=user_id,
            filter_params=filter_params,
            limit=limit
        )

    async def get_upcoming_deadlines(
            self,
            user_id: str,
            days: int = 7
    ) -> List[Task]:
        """
        Получает задачи с ближайшими дедлайнами
        """
        now = self._now()
        deadline_limit = now + timedelta(days=days)

        filter_params = TaskFilter(
            status=[TaskStatus.ACTIVE],
            deadline_from=now,
            deadline_to=deadline_limit
        )

        return await self.repository.list(
            user_id=user_id,
            filter_params=filter_params,
            sort_by="deadline",
            limit=100
        )

    async def bulk_complete(self, user_id: str, task_ids: List[str]) -> int:
        """
        Массовое завершение задач
        """
        return await self.repository.bulk_update_status(
            user_id=user_id,
            task_ids=task_ids,
            status=TaskStatus.COMPLETED
        )

    async def bulk_delete(self, user_id: str, task_ids: List[str]) -> int:
        """
        Массовое удаление задач
        """
        deleted = 0
        for task_id in task_ids:
            if await self.delete_task(task_id, user_id):
                deleted += 1
        return deleted

    async def export_tasks(
            self,
            user_id: str,
            include_completed: bool = False,
            format: str = "json"
    ) -> Dict[str, Any]:
        """
        Экспортирует задачи пользователя
        """
        filter_params = None if include_completed else TaskFilter(
            status=[TaskStatus.ACTIVE, TaskStatus.OVERDUE]
        )

        tasks = await self.repository.list(
            user_id=user_id,
            filter_params=filter_params,
            limit=10000  # Большой лимит для экспорта
        )

        export_data = {
            "user_id": user_id,
            "export_date": self._now().isoformat(),
            "total_tasks": len(tasks),
            "tasks": [task.model_dump() for task in tasks]
        }

        return export_data

    async def import_tasks(
            self,
            user_id: str,
            tasks_data: List[Dict[str, Any]]
    ) -> List[Task]:
        """
        Импортирует задачи
        """
        imported_tasks = []

        for task_data in tasks_data:
            # Убираем служебные поля
            task_data.pop('id', None)
            task_data.pop('user_id', None)
            task_data.pop('created_at', None)
            task_data.pop('updated_at', None)

            task = await self.create_task(
                user_id=user_id,
                **task_data
            )
            imported_tasks.append(task)

        return imported_tasks

    async def cleanup(self):
        """Очистка ресурсов"""
        for task in self._background_tasks:
            task.cancel()

        await asyncio.gather(*self._background_tasks, return_exceptions=True)
        self._cache.clear()
