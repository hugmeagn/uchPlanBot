"""
Хендлеры VK бота
"""
from typing import Dict, Callable, Awaitable, Optional
from ..vk_api.client import VkMessage
from ..fsm.storage import VkFSMStorage


class VkRouter:
    """
    Роутер для VK хендлеров
    """

    def __init__(self):
        self._message_handlers: Dict[str, Callable] = {}  # handlers by state
        self._command_handlers: Dict[str, Callable] = {}  # handlers by command
        self._callback_handlers: Dict[str, Callable] = {}  # handlers by callback
        self._default_handler: Optional[Callable] = None

    def message(self, state: Optional[str] = None):
        """Декоратор для обработки сообщений в определенном состоянии"""

        def decorator(handler: Callable):
            key = state or "__default__"
            self._message_handlers[key] = handler
            return handler

        return decorator

    def command(self, command: str):
        """Декоратор для обработки команд"""

        def decorator(handler: Callable):
            self._command_handlers[command.lower()] = handler
            return handler

        return decorator

    def callback(self, callback_data: str):
        """Декоратор для обработки callback'ов"""

        def decorator(handler: Callable):
            self._callback_handlers[callback_data] = handler
            return handler

        return decorator

    def default(self):
        """Декоратор для обработчика по умолчанию"""

        def decorator(handler: Callable):
            self._default_handler = handler
            return handler

        return decorator

    async def handle_message(
            self,
            message: VkMessage,
            state: Optional[str],
            data: dict
    ):
        """
        Обрабатывает сообщение
        """
        # Сначала проверяем callback (если есть payload)
        if message.payload:
            callback = message.payload.get("callback")
            if callback and callback in self._callback_handlers:
                await self._callback_handlers[callback](message, state, data)
                return

        # Проверяем команды
        if message.is_command and message.command:
            cmd = message.command
            if cmd in self._command_handlers:
                await self._command_handlers[cmd](message, state, data)
                return

        # Проверяем хендлеры по состоянию
        if state and state in self._message_handlers:
            await self._message_handlers[state](message, state, data)
            return

        # Хендлер по умолчанию для сообщений
        if "__default__" in self._message_handlers:
            await self._message_handlers["__default__"](message, state, data)
            return

        # Глобальный обработчик по умолчанию
        if self._default_handler:
            await self._default_handler(message, state, data)


# Создаем главный роутер
router = VkRouter()

# Импортируем хендлеры для регистрации
from . import menu
from . import profile
from . import schedule
from . import tasks
from . import planner
from . import notifications
from . import settings
