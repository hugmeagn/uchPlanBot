"""
Middleware для передачи сервисов в хендлеры
"""
from typing import Optional, Any
from dataclasses import dataclass

from services.notifications.service import NotificationService
from services.tasks.service import TaskService
from services.day_planner.service import DayPlannerService


@dataclass
class ServicesContainer:
    """Контейнер для сервисов"""
    notification_service: Optional[NotificationService] = None
    task_service: Optional[TaskService] = None
    day_planner: Optional[DayPlannerService] = None


class ServicesMiddleware:
    """
    Middleware для предоставления сервисов хендлерам
    """

    def __init__(self, services: ServicesContainer):
        self.services = services

    async def __call__(self, handler, event, data: dict) -> Any:
        """Добавляет сервисы в данные хендлера"""
        data['notification_service'] = self.services.notification_service
        data['task_service'] = self.services.task_service
        data['day_planner'] = self.services.day_planner
        data['services'] = self.services

        return await handler(event, data)
