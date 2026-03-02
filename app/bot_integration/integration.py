# app/bot_integration/integration.py - обновленная версия

"""
Модуль интеграции сервисов с ботом
"""
from typing import Optional
import logging
import asyncio

from aiogram import Bot, Dispatcher

from bot.utils import dates
from services.notifications.service import (
    NotificationService, NotificationChannel, TortoiseNotificationStorage
)
from services.notifications.backends import TelegramBackend
from services.notifications.scheduler import NotificationScheduler, ScheduledTask, RecurrenceType

from services.tasks.service import TaskService
from services.tasks.repository import TortoiseTaskRepository

from services.day_planner.service import DayPlannerService  # Новый импорт

from datetime import datetime
import config

logger = logging.getLogger(__name__)


class BotIntegration:
    """Класс для интеграции бота с сервисами"""

    def __init__(self, bot: Bot, dp: Dispatcher):
        self.bot = bot
        self.dp = dp

        # Инициализируем сервисы
        self.notification_service: Optional[NotificationService] = None
        self.task_service: Optional[TaskService] = None
        self.day_planner: Optional[DayPlannerService] = None  # Новый сервис

        self.scheduler: Optional[NotificationScheduler] = None

    async def initialize_services(self):
        """Инициализирует сервисы с Tortoise ORM"""
        try:
            # Импортируем модели Tortoise
            from models.notification import NotificationModel, NotificationTemplateModel
            from models.task import TaskModel, TaskReminderModel

            # Создаем хранилища
            notification_storage = TortoiseNotificationStorage(
                notification_model=NotificationModel,
                template_model=NotificationTemplateModel
            )

            task_repository = TortoiseTaskRepository(
                task_model=TaskModel,
                reminder_model=TaskReminderModel
            )

            # Создаем сервис уведомлений
            self.notification_service = NotificationService(
                storage_backend=notification_storage
            )

            # Регистрируем Telegram бэкенд
            self.notification_service.register_backend(
                NotificationChannel.TELEGRAM,
                TelegramBackend(self.bot)
            )

            # Регистрируем Console бэкенд для отладки
            from services.notifications.backends import ConsoleBackend
            self.notification_service.register_backend(
                NotificationChannel.CONSOLE,
                ConsoleBackend()
            )

            # Создаем сервис задач
            self.task_service = TaskService(
                repository=task_repository,
                notification_service=self.notification_service
            )

            # Создаем сервис планировщика дня (НОВЫЙ)
            self.day_planner = DayPlannerService()

            # Настраиваем планировщик утренних уведомлений
            await self._setup_morning_planner()

            logger.info("Services initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize services: {e}")
            raise

    async def _setup_morning_planner(self):
        """
        Настраивает ежедневную отправку планов
        """
        if not self.scheduler:
            self.scheduler = NotificationScheduler(self.notification_service)

        # Парсим время из конфига
        try:
            hour, minute = map(int, config.DAILY_PLAN_TIME.split(':'))
        except:
            hour, minute = 8, 0  # По умолчанию 8:00

        # Вычисляем следующее время запуска
        now = dates.now()
        next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if next_run <= now:
            next_run = next_run.replace(day=next_run.day + 1)

        # Создаем задачу
        task = ScheduledTask(
            id="morning_planner",
            name="Morning Daily Planner",
            recurrence=RecurrenceType.DAILY,
            next_run=next_run,
            callback=self._send_morning_plans,
            enabled=True,
            metadata={"hour": hour, "minute": minute}
        )

        self.scheduler.add_task(task)
        self.scheduler.start()

        logger.info(f"Morning planner scheduled for {hour:02d}:{minute:02d} daily")

    async def _send_morning_plans(self):
        """
        Отправляет утренние планы всем пользователям
        """
        if not self.day_planner:
            logger.error("Day planner service not available")
            return

        logger.info("Starting morning plan distribution")
        await self.day_planner.send_daily_plan_notifications()
        logger.info("Morning plan distribution completed")

    async def cleanup(self):
        """Очистка ресурсов"""
        if self.scheduler:
            await self.scheduler.stop()
        if self.task_service:
            await self.task_service.cleanup()
        if self.notification_service:
            await self.notification_service.cleanup()
        logger.info("Services cleaned up")


# Создаем глобальный экземпляр
integration: Optional[BotIntegration] = None


async def get_integration() -> BotIntegration:
    """Возвращает глобальный экземпляр интеграции"""
    global integration
    if integration is None:
        raise RuntimeError("Integration not initialized")
    return integration


def setup_integration(bot: Bot, dp: Dispatcher) -> BotIntegration:
    """Настраивает интеграцию"""
    global integration
    integration = BotIntegration(bot, dp)
    return integration
