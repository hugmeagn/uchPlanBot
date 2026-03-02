# app/bot/middlewares/services.py
"""
Middleware для передачи сервисов в хендлеры
"""
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from bot_integration.integration import get_integration


class ServicesMiddleware(BaseMiddleware):
    """Middleware для добавления сервисов в данные хендлера"""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # Получаем интеграцию
        integration = await get_integration()

        # Добавляем сервисы в данные
        data['notification_service'] = integration.notification_service
        data['task_service'] = integration.task_service

        return await handler(event, data)
