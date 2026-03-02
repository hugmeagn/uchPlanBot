from enum import Enum
from typing import Optional, Dict, Any, List, Callable, Awaitable
from datetime import datetime
import asyncio
import logging
from collections import defaultdict

import bot.utils.dates as dates

from .models import (
    Notification, NotificationStatus, NotificationChannel,
    NotificationPriority, NotificationStats, NotificationTemplate, NotificationType
)
from .backends import (
    NotificationBackend
)
from .exceptions import (
    NotificationError, NotificationBackendError,
    NotificationNotFoundError
)
from .utils import retry_async, rate_limit

logger = logging.getLogger(__name__)


class NotificationService:
    """Основной сервис для работы с уведомлениями"""

    def __init__(self, storage_backend=None, config: Dict[str, Any] = None):
        """
        :param storage_backend: Бэкенд для хранения (можно использовать Tortoise ORM)
        :param config: Конфигурация сервиса
        """
        self.storage = storage_backend
        self.config = config or {}

        # Регистрируем бэкенды
        self.backends: Dict[NotificationChannel, NotificationBackend] = {}
        self._register_default_backends()

        # Очереди уведомлений
        self._queues = defaultdict(asyncio.Queue)
        self._workers = {}

        # Коллбеки
        self._callbacks: Dict[str, List[Callable]] = defaultdict(list)

        # Статистика
        self.stats = NotificationStats()

        # Запускаем workers
        self._start_workers()

    def _register_default_backends(self):
        """Регистрирует стандартные бэкенды"""
        # Будет переопределено при инициализации
        pass

    def register_backend(self, channel: NotificationChannel, backend: NotificationBackend):
        """Регистрирует бэкенд для канала"""
        self.backends[channel] = backend

    def _start_workers(self):
        """Запускает воркеры для обработки очередей"""
        channel: NotificationChannel
        for channel in NotificationChannel:
            self._workers[channel] = asyncio.create_task(
                self._process_queue(channel)
            )

    async def _process_queue(self, channel: NotificationChannel):
        """Обрабатывает очередь уведомлений для конкретного канала"""
        queue = self._queues[channel]
        backend = self.backends.get(channel)

        if not backend:
            logger.warning(f"No backend for channel {channel}")
            return

        while True:
            try:
                notification = await queue.get()

                # Проверяем, не просрочено ли
                if notification.scheduled_for and notification.scheduled_for > dates.now():
                    # Возвращаем в очередь
                    await asyncio.sleep(1)
                    await queue.put(notification)
                    continue

                # Отправляем
                await self._send_notification(notification, backend)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error processing notification: {e}")

    @retry_async(max_retries=3, delay=1)
    async def _send_notification(self, notification: Notification, backend: NotificationBackend):
        """Отправляет одно уведомление с повторами"""
        try:
            # Обновляем статус
            notification.status = NotificationStatus.SENDING
            notification.updated_at = dates.now()
            await self._save_notification(notification)

            # Валидация
            if not await backend.validate(notification):
                raise NotificationError("Notification validation failed")

            # Отправка
            success = await backend.send(notification)

            if success:
                notification.status = NotificationStatus.SENT
                notification.sent_at = dates.now()
                self.stats.total_sent += 1
                logger.info(f"Notification {notification.id} sent successfully")
            else:
                raise NotificationError("Backend returned False")

        except NotificationBackendError as e:
            notification.retry_count += 1
            notification.last_error = str(e)

            if notification.retry_count >= notification.max_retries:
                notification.status = NotificationStatus.FAILED
                self.stats.total_failed += 1
                logger.error(f"Notification {notification.id} failed after {notification.retry_count} retries")
            else:
                # Возвращаем в очередь
                notification.status = NotificationStatus.PENDING
                await asyncio.sleep(2 ** notification.retry_count)  # exponential backoff
                await self._queues[notification.channel].put(notification)

        except Exception as e:
            notification.status = NotificationStatus.FAILED
            notification.last_error = str(e)
            self.stats.total_failed += 1
            logger.error(f"Unexpected error sending notification {notification.id}: {e}")

        finally:
            notification.updated_at = dates.now()
            await self._save_notification(notification)

            # Вызываем коллбеки
            await self._trigger_callbacks(notification)

    async def send_notification(
            self,
            user_id: str,
            channel: NotificationChannel,
            title: str,
            content: str,
            notification_type: str = NotificationType.CUSTOM.value,
            priority: int = NotificationPriority.MEDIUM.value,  # Изменено на int
            scheduled_for: Optional[datetime] = None,
            data: Optional[Dict] = None,
            **kwargs
    ) -> Notification:
        """
        Создаёт и отправляет уведомление
        """
        # Убеждаемся, что priority - это число
        if isinstance(priority, Enum):
            priority = priority.value
        elif isinstance(priority, str):
            # Если вдруг пришла строка, конвертируем
            priority_map = {
                'low': 0, 'medium': 1, 'high': 2, 'critical': 3
            }
            priority = priority_map.get(priority.lower(), 1)

        # Приводим к int
        priority = int(priority)

        logger.info(f"Creating notification with priority: {priority} (type: {type(priority)})")

        notification = Notification(
            user_id=user_id,
            channel=channel,
            type=notification_type,
            priority=priority,  # Теперь точно число
            title=title,
            content=content,
            scheduled_for=scheduled_for,
            data=data,
            **kwargs
        )

        # Сохраняем
        await self._save_notification(notification)

        # Если не отложенное, добавляем в очередь
        if not scheduled_for or scheduled_for <= dates.now():
            await self._queues[channel].put(notification)
        else:
            notification.status = NotificationStatus.SCHEDULED
            await self._save_notification(notification)

            # Запускаем таймер
            asyncio.create_task(
                self._schedule_notification(notification)
            )

        return notification

    async def _schedule_notification(self, notification: Notification):
        """Планирует отложенное уведомление"""
        delay = (notification.scheduled_for - dates.now()).total_seconds()
        if delay > 0:
            await asyncio.sleep(delay)
            await self._queues[notification.channel].put(notification)

    async def send_template(
            self,
            user_id: str,
            template_name: str,
            variables: Dict[str, Any],
            **kwargs
    ) -> Optional[Notification]:
        """Отправляет уведомление по шаблону"""
        template = await self._get_template(template_name)
        if not template:
            raise NotificationError(f"Template {template_name} not found")

        # Заполняем шаблон
        title = template.title_template.format(**variables)
        content = template.content_template.format(**variables)

        return await self.send_notification(
            user_id=user_id,
            channel=template.channel,
            title=title,
            content=content,
            notification_type=template.type,
            **kwargs
        )

    async def send_bulk(
            self,
            user_ids: List[str],
            channel: NotificationChannel,
            title: str,
            content: str,
            **kwargs
    ) -> List[Notification]:
        """Массовая рассылка"""
        notifications = []
        for user_id in user_ids:
            notification = await self.send_notification(
                user_id=user_id,
                channel=channel,
                title=title,
                content=content,
                **kwargs
            )
            notifications.append(notification)

        return notifications

    @rate_limit(max_calls=10, period=1)  # Не больше 10 в секунду
    async def send_priority_notification(self, *args, **kwargs):
        """Отправка с ограничением по частоте"""
        return await self.send_notification(*args, **kwargs)

    async def cancel_notification(self, notification_id: str) -> bool:
        """Отменяет уведомление"""
        notification = await self.get_notification(notification_id)
        if not notification:
            raise NotificationNotFoundError(f"Notification {notification_id} not found")

        if notification.status in (NotificationStatus.PENDING, NotificationStatus.SCHEDULED):
            notification.status = NotificationStatus.CANCELLED
            notification.updated_at = dates.now()
            await self._save_notification(notification)
            return True

        return False

    async def get_notification(self, notification_id: str) -> Optional[Notification]:
        """Получает уведомление по ID"""
        if self.storage:
            return await self.storage.get_notification(notification_id)
        return None

    async def get_user_notifications(
            self,
            user_id: str,
            limit: int = 50,
            offset: int = 0,
            status: Optional[NotificationStatus] = None
    ) -> List[Notification]:
        """Получает уведомления пользователя"""
        if self.storage:
            return await self.storage.get_user_notifications(
                user_id, limit, offset, status
            )
        return []

    async def get_stats(self) -> NotificationStats:
        """Возвращает статистику"""
        if self.storage:
            return await self.storage.get_stats()
        return self.stats

    async def mark_as_delivered(self, notification_id: str):
        """Отмечает уведомление как доставленное"""
        notification = await self.get_notification(notification_id)
        if notification:
            notification.status = NotificationStatus.DELIVERED
            notification.delivered_at = dates.now()
            await self._save_notification(notification)

    async def register_callback(
            self,
            event: str,
            callback: Callable[[Notification], Awaitable[None]]
    ):
        """Регистрирует коллбек на события"""
        self._callbacks[event].append(callback)

    async def _trigger_callbacks(self, notification: Notification):
        """Вызывает коллбеки для события"""
        callbacks = self._callbacks.get(notification.status.value, [])
        for callback in callbacks:
            try:
                await callback(notification)
            except Exception as e:
                logger.error(f"Callback failed: {e}")

    async def _save_notification(self, notification: Notification):
        """Сохраняет уведомление в хранилище"""
        if self.storage:
            await self.storage.save_notification(notification)

    async def _get_template(self, name: str) -> Optional[NotificationTemplate]:
        """Получает шаблон по имени"""
        if self.storage:
            return await self.storage.get_template(name)
        return None

    async def cleanup(self):
        """Очистка ресурсов"""
        for worker in self._workers.values():
            worker.cancel()

        await asyncio.gather(*self._workers.values(), return_exceptions=True)


class TortoiseNotificationStorage:
    """Адаптер для хранения уведомлений в Tortoise ORM"""

    def __init__(self, notification_model, template_model=None):
        self.NotificationModel = notification_model
        self.TemplateModel = template_model

    async def save_notification(self, notification: Notification):
        """Сохраняет уведомление"""
        await self.NotificationModel.update_or_create(
            id=notification.id,
            defaults=notification.model_dump()
        )

    async def get_notification(self, notification_id: str) -> Optional[Notification]:
        """Получает уведомление"""
        instance = await self.NotificationModel.get_or_none(id=notification_id)
        if instance:
            return Notification.model_validate(instance.__dict__)
        return None

    async def get_user_notifications(self, user_id: str, limit: int, offset: int, status=None):
        """Получает уведомления пользователя"""
        query = self.NotificationModel.filter(user_id=user_id)
        if status:
            query = query.filter(status=status)

        instances = await query.order_by('-created_at').limit(limit).offset(offset)
        return [Notification.model_validate(i.__dict__) for i in instances]

    async def get_stats(self) -> NotificationStats:
        """Получает статистику"""
        stats = NotificationStats()

        # Общая статистика
        all_notifications = await self.NotificationModel.all()

        for notification in all_notifications:
            if notification.status == 'sent':
                stats.total_sent += 1
            elif notification.status == 'failed':
                stats.total_failed += 1
            elif notification.status == 'pending':
                stats.total_pending += 1

            stats.by_channel[notification.channel] = \
                stats.by_channel.get(notification.channel, 0) + 1

            stats.by_type[notification.type] = \
                stats.by_type.get(notification.type, 0) + 1

            stats.by_priority[notification.priority] = \
                stats.by_priority.get(notification.priority, 0) + 1

        return stats

    async def get_template(self, name: str):
        """Получает шаблон"""
        if not self.TemplateModel:
            return None

        instance = await self.TemplateModel.get_or_none(name=name)
        if instance:
            return NotificationTemplate.model_validate(instance.__dict__)
        return None
