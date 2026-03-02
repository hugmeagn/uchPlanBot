from typing import Dict, Any, Optional, Callable
from datetime import datetime, timedelta
import asyncio
import logging
from dataclasses import dataclass
from enum import Enum

import bot.utils.dates as dates

from .models import NotificationPriority, NotificationStatus
from .service import NotificationService

logger = logging.getLogger(__name__)


class RecurrenceType(str, Enum):
    """Типы повторения"""
    ONCE = "once"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    CUSTOM = "custom"


@dataclass
class ScheduledTask:
    """Запланированная задача"""
    id: str
    name: str
    recurrence: RecurrenceType
    next_run: datetime
    interval: Optional[timedelta] = None
    last_run: Optional[datetime] = None
    enabled: bool = True
    metadata: Dict[str, Any] = None

    # Функция для выполнения
    callback: Optional[Callable] = None

    # Параметры уведомления (если это уведомление)
    notification_template: Optional[Dict] = None


class NotificationScheduler:
    """Планировщик уведомлений"""

    def __init__(self, notification_service: NotificationService):
        self.service = notification_service
        self.tasks: Dict[str, ScheduledTask] = {}
        self._running = False
        self._worker_task = None

    def add_task(self, task: ScheduledTask):
        """Добавляет задачу"""
        self.tasks[task.id] = task
        logger.info(f"Task added: {task.name} (next run: {task.next_run})")

    def remove_task(self, task_id: str):
        """Удаляет задачу"""
        if task_id in self.tasks:
            del self.tasks[task_id]

    def start(self):
        """Запускает планировщик"""
        if self._running:
            return

        self._running = True
        self._worker_task = asyncio.create_task(self._run())
        logger.info("Scheduler started")

    async def stop(self):
        """Останавливает планировщик"""
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        logger.info("Scheduler stopped")

    async def _run(self):
        """Основной цикл планировщика"""
        while self._running:
            try:
                now = dates.now()

                for task in self.tasks.values():
                    if not task.enabled:
                        continue

                    if task.next_run <= now:
                        await self._execute_task(task)
                        self._schedule_next(task)

                # Спим до следующей минуты
                await asyncio.sleep(60 - now.second)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                await asyncio.sleep(5)

    async def _execute_task(self, task: ScheduledTask):
        """Выполняет задачу"""
        try:
            logger.info(f"Executing task: {task.name}")

            if task.callback:
                await task.callback()

            if task.notification_template:
                await self._send_notification_from_template(task)

            task.last_run = dates.now()

        except Exception as e:
            logger.error(f"Task execution failed: {e}")

    def _schedule_next(self, task: ScheduledTask):
        """Планирует следующий запуск"""
        now = dates.now()

        if task.recurrence == RecurrenceType.ONCE:
            task.enabled = False
            return

        if task.recurrence == RecurrenceType.DAILY:
            task.next_run = now + timedelta(days=1)
        elif task.recurrence == RecurrenceType.WEEKLY:
            task.next_run = now + timedelta(weeks=1)
        elif task.recurrence == RecurrenceType.MONTHLY:
            # Примерно месяц
            task.next_run = now + timedelta(days=30)
        elif task.recurrence == RecurrenceType.CUSTOM and task.interval:
            task.next_run = now + task.interval

        logger.info(f"Next run for {task.name}: {task.next_run}")

    async def _send_notification_from_template(self, task: ScheduledTask):
        """Отправляет уведомление по шаблону задачи"""
        template = task.notification_template
        if not template:
            return

        await self.service.send_notification(
            user_id=template.get('user_id'),
            channel=template.get('channel'),
            title=template.get('title', 'Уведомление'),
            content=template.get('content', ''),
            notification_type=template.get('type', 'custom'),
            priority=template.get('priority', NotificationPriority.MEDIUM),
            data=template.get('data')
        )

    async def check_overdue_notifications(self):
        """Проверяет просроченные уведомления"""
        if not self.service.storage:
            return

        notifications = await self.service.get_user_notifications(
            user_id="*",  # Все пользователи
            limit=1000,
            status=NotificationStatus.PENDING
        )

        now = dates.now()
        for notification in notifications:
            # Если уведомление должно было быть отправлено больше часа назад
            if notification.scheduled_for and \
                    notification.scheduled_for < now - timedelta(hours=1):
                logger.warning(f"Overdue notification found: {notification.id}")
                # Можно отправить сейчас или отметить как просроченное
                await self.service._queues[notification.channel].put(notification)
