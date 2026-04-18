"""
Основной класс VK бота
"""
import asyncio
import logging
from typing import Optional

from .vk_api.client import VkApiClient, VkMessage
from .fsm.storage import VkFSMStorage
from .handlers import router
from .middlewares import ServicesContainer

from services.notifications.backends import VKBackend
from services.notifications.service import NotificationService, NotificationChannel, TortoiseNotificationStorage
from services.tasks.service import TaskService
from services.tasks.repository import TortoiseTaskRepository
from services.day_planner.service import DayPlannerService
from services.notifications.scheduler import NotificationScheduler, ScheduledTask, RecurrenceType

import config
from bot.utils import dates

logger = logging.getLogger(__name__)


class VkBot:
    """
    Основной класс VK бота
    """

    def __init__(self):
        self.vk = VkApiClient(
            token=config.VK_TOKEN,
            group_id=int(config.VK_GROUP_ID)
        )

        self.fsm = VkFSMStorage()

        # Сервисы
        self.notification_service: Optional[NotificationService] = None
        self.task_service: Optional[TaskService] = None
        self.day_planner: Optional[DayPlannerService] = None
        self.scheduler: Optional[NotificationScheduler] = None

        # Регистрируем обработчики
        self._register_handlers()

    def _register_handlers(self):
        """Регистрирует обработчики сообщений"""
        # Исправлено: передаем функцию-обработчик как аргумент
        self.vk.on_message(self._handle_message)

    async def _handle_message(self, message: VkMessage):
        """Обрабатывает входящее сообщение"""
        user_id = message.from_id

        # Пропускаем сообщения от бота (отрицательные ID)
        if user_id < 0:
            return

        try:
            # Получаем текущее состояние пользователя
            state = await self.fsm.get_state(user_id)

            # Подготавливаем данные для хендлеров
            data = {
                'vk': self.vk,
                'fsm': self.fsm,
                'notification_service': self.notification_service,
                'task_service': self.task_service,
                'day_planner': self.day_planner,
            }

            # Передаем в роутер
            await router.handle_message(message, state, data)

        except Exception as e:
            logger.error(f"Error processing message from {user_id}: {e}", exc_info=True)

            # Отправляем сообщение об ошибке
            try:
                await self.vk.send_message(
                    peer_id=user_id,
                    text="❌ Произошла ошибка. Попробуйте позже или используйте /start."
                )
            except:
                pass

    async def initialize_services(self):
        """Инициализирует сервисы"""
        try:
            from models.notification import NotificationModel, NotificationTemplateModel
            from models.task import TaskModel, TaskReminderModel

            # Хранилище уведомлений
            notification_storage = TortoiseNotificationStorage(
                notification_model=NotificationModel,
                template_model=NotificationTemplateModel
            )

            # Репозиторий задач
            task_repository = TortoiseTaskRepository(
                task_model=TaskModel,
                reminder_model=TaskReminderModel
            )

            # Сервис уведомлений
            self.notification_service = NotificationService(
                storage_backend=notification_storage
            )

            # Регистрируем VK бэкенд
            self.notification_service.register_backend(
                NotificationChannel.VK,
                VKBackend(self.vk)
            )

            # Сервис задач
            self.task_service = TaskService(
                repository=task_repository,
                notification_service=self.notification_service
            )

            # Сервис планировщика
            self.day_planner = DayPlannerService()

            # Настраиваем планировщик
            await self._setup_morning_planner()

            logger.info("VK Bot services initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize services: {e}")
            raise

    async def _setup_morning_planner(self):
        """Настраивает ежедневную отправку планов"""
        if not self.scheduler:
            self.scheduler = NotificationScheduler(self.notification_service)

        try:
            hour, minute = map(int, config.DAILY_PLAN_TIME.split(':'))
        except:
            hour, minute = 8, 0

        now = dates.now()
        next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if next_run <= now:
            next_run = next_run.replace(day=next_run.day + 1)

        task = ScheduledTask(
            id="morning_planner_vk",
            name="Morning Daily Planner VK",
            recurrence=RecurrenceType.DAILY,
            next_run=next_run,
            callback=self._send_morning_plans,
            enabled=True,
            metadata={"hour": hour, "minute": minute}
        )

        self.scheduler.add_task(task)
        self.scheduler.start()

        logger.info(f"VK Morning planner scheduled for {hour:02d}:{minute:02d} daily")

    async def _send_morning_plans(self):
        """Отправляет утренние планы всем пользователям"""
        if not self.day_planner:
            logger.error("Day planner service not available")
            return

        logger.info("Starting VK morning plan distribution")

        try:
            from models.user import User
            today = dates.today()

            # Получаем всех VK пользователей с включенными уведомлениями
            users = await User.filter(
                vk_id__isnull=False,
                notifications_enabled=True
            )

            for user in users:
                try:
                    await user.fetch_related('institution')

                    result = await self.day_planner.get_or_generate_plan(user, today)

                    if result.success and result.plan:
                        await self.notification_service.send_notification(
                            user_id=str(user.vk_id),
                            channel=NotificationChannel.VK,
                            title="🌅 Доброе утро! Вот ваш план на сегодня:",
                            content=result.plan,
                            notification_type="daily_plan",
                            priority=2
                        )

                        from models.daily_plan import DailyPlan
                        await DailyPlan.filter(
                            user=user,
                            plan_date=today
                        ).update(
                            notification_sent=True,
                            sent_at=dates.now()
                        )

                        logger.info(f"Sent daily plan to VK user {user.vk_id}")

                except Exception as e:
                    logger.error(f"Error sending plan to VK user {user.vk_id}: {e}")

        except Exception as e:
            logger.error(f"Error in morning plan distribution: {e}")

    async def start(self):
        """Запускает бота"""
        await self.fsm.start_cleanup()
        await self.initialize_services()

        logger.info("🚀 VK Bot started!")
        await self.vk.start_polling()

    async def stop(self):
        """Останавливает бота"""
        await self.fsm.stop_cleanup()

        if self.scheduler:
            await self.scheduler.stop()

        if self.task_service:
            await self.task_service.cleanup()

        if self.notification_service:
            await self.notification_service.cleanup()

        await self.vk.stop()

        logger.info("VK Bot stopped")
