from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import logging

from .models import Notification
from .exceptions import NotificationBackendError

logger = logging.getLogger(__name__)


class NotificationBackend(ABC):
    """Абстрактный базовый класс для бэкендов"""

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.name = self.__class__.__name__

    @abstractmethod
    async def send(self, notification: Notification) -> bool:
        """Отправить уведомление"""
        pass

    async def validate(self, notification: Notification) -> bool:
        """Проверить, можно ли отправить уведомление"""
        return True

    async def get_status(self, notification_id: str) -> Optional[str]:
        """Получить статус доставки"""
        return None


class TelegramBackend(NotificationBackend):
    """Бэкенд для Telegram"""

    def __init__(self, bot, config: Dict[str, Any] = None):
        super().__init__(config)
        self.bot = bot

    async def send(self, notification: Notification) -> bool:
        try:
            # Форматируем сообщение
            text = f"*{notification.title}*\n\n{notification.content}"

            # Добавляем кнопки если есть
            reply_markup = None
            if notification.data and 'buttons' in notification.data:
                from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text=btn['text'], callback_data=btn.get('callback_data', '')
                                                                          or btn.get('url', ''))]
                    for btn in notification.data['buttons']
                ])
                reply_markup = keyboard

            # Отправляем
            await self.bot.send_message(
                chat_id=notification.user_id,
                text=text,
                parse_mode='Markdown',
                reply_markup=reply_markup,
                disable_web_page_preview=True
            )

            logger.info(f"Telegram notification sent to {notification.user_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to send Telegram notification: {e}")
            raise NotificationBackendError(f"Telegram send failed: {e}")


class VKBackend(NotificationBackend):
    """
    Бэкенд для VK (через сообщения группы)
    """

    def __init__(self, vk_api, config: Dict[str, Any] = None):
        super().__init__(config)
        self.vk_api = vk_api

    async def send(self, notification: Notification) -> bool:
        """
        Отправляет уведомление через VK API
        """
        try:
            # Форматируем сообщение
            text = f"{notification.title}\n\n{notification.content}"

            # Обрезаем длинное сообщение (лимит VK ~4000 символов)
            if len(text) > 4000:
                text = text[:3997] + "..."

            # Отправляем в отдельном потоке (VK API синхронный)
            import asyncio
            result = await asyncio.to_thread(
                self.vk_api.messages.send,
                user_id=int(notification.user_id),  # VK ID пользователя
                message=text,
                random_id=0
            )

            logger.info(f"VK notification sent to user {notification.user_id}, result: {result}")
            return True

        except Exception as e:
            logger.error(f"Failed to send VK notification: {e}")
            raise NotificationBackendError(f"VK send failed: {e}")


class ConsoleBackend(NotificationBackend):
    """Бэкенд для отладки - выводит в консоль"""

    async def send(self, notification: Notification) -> bool:
        print("\n" + "=" * 50)
        print(f"📨 NOTIFICATION [{notification.id}]")
        print(f"To: {notification.user_id} via {notification.channel}")
        print(f"Title: {notification.title}")
        print(f"Content: {notification.content}")
        print(f"Priority: {notification.priority}")
        print(f"Scheduled: {notification.scheduled_for}")
        print("=" * 50 + "\n")
        return True
