from datetime import datetime, timedelta
from typing import Optional, List, Dict
from abc import ABC, abstractmethod
import logging

import bot.utils.dates as dates

from .models import Task, TaskFilter, TaskStats, TaskReminder
from .enums import TaskStatus
from .exceptions import TaskNotFoundError, TaskAccessDeniedError

logger = logging.getLogger(__name__)


class TaskRepository(ABC):
    """Абстрактный репозиторий для задач"""

    @abstractmethod
    async def create(self, task: Task) -> Task:
        """Создать задачу"""
        pass

    @abstractmethod
    async def get(self, task_id: str, user_id: str) -> Optional[Task]:
        """Получить задачу по ID"""
        pass

    @abstractmethod
    async def update(self, task: Task) -> Task:
        """Обновить задачу"""
        pass

    @abstractmethod
    async def delete(self, task_id: str, user_id: str) -> bool:
        """Удалить задачу"""
        pass

    @abstractmethod
    async def list(
            self,
            user_id: str,
            filter_params: Optional[TaskFilter] = None,
            sort_by: str = "deadline",
            sort_order: str = "asc",
            limit: int = 100,
            offset: int = 0
    ) -> List[Task]:
        """Получить список задач"""
        pass

    @abstractmethod
    async def count(
            self,
            user_id: str,
            filter_params: Optional[TaskFilter] = None
    ) -> int:
        """Получить количество задач"""
        pass

    @abstractmethod
    async def get_stats(self, user_id: str) -> TaskStats:
        """Получить статистику по задачам пользователя"""
        pass

    @abstractmethod
    async def get_upcoming_deadlines(
            self,
            user_id: str,
            hours: int = 24
    ) -> List[Task]:
        """Получить задачи с ближайшими дедлайнами"""
        pass

    @abstractmethod
    async def get_overdue_tasks(self, user_id: str) -> List[Task]:
        """Получить просроченные задачи"""
        pass

    @abstractmethod
    async def bulk_update_status(
            self,
            user_id: str,
            task_ids: List[str],
            status: TaskStatus
    ) -> int:
        """Массовое обновление статуса"""
        pass


class InMemoryTaskRepository(TaskRepository):
    """In-memory реализация репозитория (для тестирования)"""

    def __init__(self):
        self._tasks: Dict[str, Task] = {}
        self._user_tasks: Dict[str, List[str]] = {}

    async def create(self, task: Task) -> Task:
        self._tasks[task.id] = task

        if task.user_id not in self._user_tasks:
            self._user_tasks[task.user_id] = []
        self._user_tasks[task.user_id].append(task.id)

        return task

    async def get(self, task_id: str, user_id: str) -> Optional[Task]:
        task = self._tasks.get(task_id)
        if task and task.user_id == user_id:
            return task
        return None

    async def update(self, task: Task) -> Task:
        if task.id not in self._tasks:
            raise TaskNotFoundError(f"Task {task.id} not found")

        existing = self._tasks[task.id]
        if existing.user_id != task.user_id:
            raise TaskAccessDeniedError("Cannot update task from another user")

        self._tasks[task.id] = task
        return task

    async def delete(self, task_id: str, user_id: str) -> bool:
        task = await self.get(task_id, user_id)
        if not task:
            return False

        del self._tasks[task_id]
        if user_id in self._user_tasks:
            self._user_tasks[user_id].remove(task_id)

        return True

    async def list(
            self,
            user_id: str,
            filter_params: Optional[TaskFilter] = None,
            sort_by: str = "deadline",
            sort_order: str = "asc",
            limit: int = 100,
            offset: int = 0
    ) -> List[Task]:
        tasks = []

        # Получаем все задачи пользователя
        for task_id in self._user_tasks.get(user_id, []):
            task = self._tasks.get(task_id)
            if task:
                tasks.append(task)

        # Применяем фильтры
        if filter_params:
            tasks = self._apply_filters(tasks, filter_params)

        # Сортируем
        tasks.sort(
            key=lambda t: getattr(t, sort_by, dates.now()),
            reverse=(sort_order == "desc")
        )

        # Применяем пагинацию
        return tasks[offset:offset + limit]

    async def count(
            self,
            user_id: str,
            filter_params: Optional[TaskFilter] = None
    ) -> int:
        tasks = await self.list(user_id, filter_params, limit=10000)
        return len(tasks)

    async def get_stats(self, user_id: str) -> TaskStats:
        tasks = await self.list(user_id)
        stats = TaskStats()

        now = dates.now()

        for task in tasks:
            stats.total += 1

            if task.status == TaskStatus.ACTIVE:
                stats.active += 1
            elif task.status == TaskStatus.COMPLETED:
                stats.completed += 1
            elif task.status == TaskStatus.OVERDUE:
                stats.overdue += 1
            elif task.status == TaskStatus.ARCHIVED:
                stats.archived += 1

            stats.by_priority[task.priority] = stats.by_priority.get(task.priority, 0) + 1
            stats.by_category[task.category] = stats.by_category.get(task.category, 0) + 1

            if task.deadline and task.status == TaskStatus.ACTIVE:
                if task.deadline <= now + timedelta(hours=24):
                    stats.upcoming_deadlines += 1

        return stats

    async def get_upcoming_deadlines(
            self,
            user_id: str,
            hours: int = 24
    ) -> List[Task]:
        tasks = await self.list(
            user_id,
            TaskFilter(status=[TaskStatus.ACTIVE])
        )

        now = dates.now()
        deadline_limit = now + timedelta(hours=hours)

        return [
            task for task in tasks
            if task.deadline and now <= task.deadline <= deadline_limit
        ]

    async def get_overdue_tasks(self, user_id: str) -> List[Task]:
        tasks = await self.list(
            user_id,
            TaskFilter(status=[TaskStatus.ACTIVE])
        )

        now = dates.now()

        return [
            task for task in tasks
            if task.deadline and task.deadline < now
        ]

    async def bulk_update_status(
            self,
            user_id: str,
            task_ids: List[str],
            status: TaskStatus
    ) -> int:
        updated = 0
        for task_id in task_ids:
            task = await self.get(task_id, user_id)
            if task:
                task.status = status
                task.updated_at = dates.now()
                await self.update(task)
                updated += 1
        return updated

    def _apply_filters(self, tasks: List[Task], filters: TaskFilter) -> List[Task]:
        """Применяет фильтры к списку задач"""
        filtered = tasks.copy()

        if filters.status:
            filtered = [t for t in filtered if t.status in filters.status]

        if filters.priority:
            filtered = [t for t in filtered if t.priority in filters.priority]

        if filters.category:
            filtered = [t for t in filtered if t.category in filters.category]

        if filters.tags:
            filtered = [t for t in filtered if any(tag in t.tags for tag in filters.tags)]

        if filters.deadline_from:
            filtered = [
                t for t in filtered
                if t.deadline and t.deadline >= filters.deadline_from
            ]

        if filters.deadline_to:
            filtered = [
                t for t in filtered
                if t.deadline and t.deadline <= filters.deadline_to
            ]

        if filters.search_text:
            search = filters.search_text.lower()
            filtered = [
                t for t in filtered
                if search in t.title.lower() or
                   (t.description and search in t.description.lower())
            ]

        if filters.has_deadline is not None:
            if filters.has_deadline:
                filtered = [t for t in filtered if t.deadline]
            else:
                filtered = [t for t in filtered if not t.deadline]

        if filters.is_overdue is not None:
            now = dates.now()
            if filters.is_overdue:
                filtered = [
                    t for t in filtered
                    if t.deadline and t.deadline < now and t.status != TaskStatus.COMPLETED
                ]
            else:
                filtered = [
                    t for t in filtered
                    if not (t.deadline and t.deadline < now and t.status != TaskStatus.COMPLETED)
                ]

        return filtered


# Tortoise ORM реализация (если используете Tortoise)
class TortoiseTaskRepository(TaskRepository):
    """Реализация репозитория с Tortoise ORM"""

    def __init__(self, task_model, reminder_model=None):
        self.TaskModel = task_model
        self.ReminderModel = reminder_model

    async def create(self, task: Task) -> Task:
        # Конвертируем Pydantic модель в dict для ORM
        task_dict = task.model_dump(exclude={'reminders'})

        # Создаем задачу в БД
        db_task = await self.TaskModel.create(**task_dict)

        # Создаем напоминания
        if task.reminders and self.ReminderModel:
            for reminder in task.reminders:
                reminder_dict = reminder.model_dump()
                reminder_dict['task_id'] = db_task.id
                await self.ReminderModel.create(**reminder_dict)

        return await self.get(db_task.id, task.user_id)

    async def get(self, task_id: str, user_id: str) -> Optional[Task]:
        """Получает задачу по ID с предзагрузкой напоминаний"""
        db_task = await self.TaskModel.filter(
            id=task_id,
            user_id=user_id
        ).prefetch_related('reminders').first()

        if not db_task:
            return None

        # Получаем напоминания
        reminders = []
        if hasattr(db_task, 'reminders'):
            for db_reminder in db_task.reminders:
                reminder_dict = db_reminder.__dict__
                reminders.append(TaskReminder.model_validate(reminder_dict))

        task_dict = db_task.__dict__
        task_dict['reminders'] = reminders

        logger.debug(f"Loaded task {task_id} with {len(reminders)} reminders")
        return Task.model_validate(task_dict)

    async def update(self, task: Task) -> Task:
        db_task = await self.TaskModel.get_or_none(id=task.id)
        if not db_task:
            raise TaskNotFoundError(f"Task {task.id} not found")

        if db_task.user_id != task.user_id:
            raise TaskAccessDeniedError("Cannot update task from another user")

        # Обновляем поля задачи
        task_dict = task.model_dump(exclude={'reminders', 'id'})
        await db_task.update_from_dict(task_dict)
        await db_task.save()

        # Обновляем напоминания
        if self.ReminderModel and task.reminders:
            # Удаляем старые
            await self.ReminderModel.filter(task_id=task.id).delete()

            # Создаем новые
            for reminder in task.reminders:
                reminder_dict = reminder.model_dump()
                reminder_dict['task_id'] = task.id
                await self.ReminderModel.create(**reminder_dict)

        return await self.get(task.id, task.user_id)

    async def delete(self, task_id: str, user_id: str) -> bool:
        db_task = await self.TaskModel.get_or_none(id=task_id, user_id=user_id)
        if not db_task:
            return False

        # Удаляем связанные напоминания
        if self.ReminderModel:
            await self.ReminderModel.filter(task_id=task_id).delete()

        await db_task.delete()
        return True

    async def list(
            self,
            user_id: str,
            filter_params: Optional[TaskFilter] = None,
            sort_by: str = "deadline",
            sort_order: str = "asc",
            limit: int = 100,
            offset: int = 0
    ) -> List[Task]:
        """Получает список задач с предзагрузкой напоминаний"""
        query = self.TaskModel.filter(user_id=user_id)

        # Применяем фильтры
        if filter_params:
            query = self._apply_filters_to_query(query, filter_params)

        # Сортировка
        order_prefix = "" if sort_order == "asc" else "-"
        query = query.order_by(f"{order_prefix}{sort_by}")

        # Пагинация с предзагрузкой напоминаний
        db_tasks = await query.limit(limit).offset(offset).prefetch_related('reminders')

        logger.info(f"Found {len(db_tasks)} tasks for user {user_id}")

        tasks = []
        for db_task in db_tasks:
            task_dict = db_task.__dict__

            # Загружаем напоминания
            reminders = []
            if hasattr(db_task, 'reminders'):
                for db_reminder in db_task.reminders:  # уже предзагружено через prefetch_related
                    reminder_dict = db_reminder.__dict__
                    reminders.append(TaskReminder.model_validate(reminder_dict))

            task_dict['reminders'] = reminders
            tasks.append(Task.model_validate(task_dict))

            logger.debug(f"Task {db_task.id} has {len(reminders)} reminders")

        return tasks

    async def count(
            self,
            user_id: str,
            filter_params: Optional[TaskFilter] = None
    ) -> int:
        query = self.TaskModel.filter(user_id=user_id)

        if filter_params:
            query = self._apply_filters_to_query(query, filter_params)

        return await query.count()

    async def get_stats(self, user_id: str) -> TaskStats:
        # Получаем все задачи пользователя
        all_tasks = await self.TaskModel.filter(user_id=user_id)

        stats = TaskStats()
        now = dates.now()

        for db_task in all_tasks:
            stats.total += 1

            if db_task.status == TaskStatus.ACTIVE:
                stats.active += 1
            elif db_task.status == TaskStatus.COMPLETED:
                stats.completed += 1
            elif db_task.status == TaskStatus.OVERDUE:
                stats.overdue += 1
            elif db_task.status == TaskStatus.ARCHIVED:
                stats.archived += 1

            stats.by_priority[db_task.priority] = stats.by_priority.get(db_task.priority, 0) + 1
            stats.by_category[db_task.category] = stats.by_category.get(db_task.category, 0) + 1

            if db_task.deadline and db_task.status == TaskStatus.ACTIVE:
                if db_task.deadline <= now + timedelta(hours=24):
                    stats.upcoming_deadlines += 1

        return stats

    async def get_upcoming_deadlines(
            self,
            user_id: str,
            hours: int = 24
    ) -> List[Task]:
        now = dates.now()
        deadline_limit = now + timedelta(hours=hours)

        db_tasks = await self.TaskModel.filter(
            user_id=user_id,
            status=TaskStatus.ACTIVE,
            deadline__gte=now,
            deadline__lte=deadline_limit
        )

        tasks = []
        for db_task in db_tasks:
            tasks.append(Task.model_validate(db_task.__dict__))

        return tasks

    async def get_overdue_tasks(self, user_id: str) -> List[Task]:
        now = dates.now()

        db_tasks = await self.TaskModel.filter(
            user_id=user_id,
            status=TaskStatus.ACTIVE,
            deadline__lt=now
        )

        tasks = []
        for db_task in db_tasks:
            tasks.append(Task.model_validate(db_task.__dict__))

        return tasks

    async def bulk_update_status(
            self,
            user_id: str,
            task_ids: List[str],
            status: TaskStatus
    ) -> int:
        result = await self.TaskModel.filter(
            id__in=task_ids,
            user_id=user_id
        ).update(
            status=status,
            updated_at=dates.now()
        )

        return result

    def _apply_filters_to_query(self, query, filters: TaskFilter):
        """Применяет фильтры к Tortoise запросу"""
        if filters.status:
            query = query.filter(status__in=filters.status)

        if filters.priority:
            query = query.filter(priority__in=filters.priority)

        if filters.category:
            query = query.filter(category__in=filters.category)

        if filters.tags:
            # Для простоты ищем хотя бы один тег
            query = query.filter(tags__overlap=filters.tags)

        if filters.deadline_from:
            query = query.filter(deadline__gte=filters.deadline_from)

        if filters.deadline_to:
            query = query.filter(deadline__lte=filters.deadline_to)

        if filters.created_from:
            query = query.filter(created_at__gte=filters.created_from)

        if filters.created_to:
            query = query.filter(created_at__lte=filters.created_to)

        if filters.search_text:
            query = query.filter(
                title__icontains=filters.search_text
            ) | query.filter(
                description__icontains=filters.search_text
            )

        if filters.has_deadline is not None:
            if filters.has_deadline:
                query = query.filter(deadline__isnull=False)
            else:
                query = query.filter(deadline__isnull=True)

        if filters.reminder_enabled is not None:
            query = query.filter(reminder_enabled=filters.reminder_enabled)

        return query
