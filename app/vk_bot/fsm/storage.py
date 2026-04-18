"""
Хранилище состояний FSM для VK бота
"""
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import asyncio
import logging

logger = logging.getLogger(__name__)


@dataclass
class VkState:
    """Состояние пользователя в FSM"""
    state: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)
    updated_at: datetime = field(default_factory=datetime.now)
    message_id: Optional[int] = None  # ID последнего сообщения бота


class VkFSMStorage:
    """
    In-memory хранилище состояний FSM для VK
    В production лучше использовать Redis
    """

    def __init__(self, ttl_seconds: int = 3600):
        self._states: Dict[int, VkState] = {}
        self._ttl = ttl_seconds
        self._lock = asyncio.Lock()

        # Запускаем очистку устаревших состояний
        self._cleanup_task: Optional[asyncio.Task] = None

    async def start_cleanup(self):
        """Запускает фоновую очистку"""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def stop_cleanup(self):
        """Останавливает очистку"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None

    async def _cleanup_loop(self):
        """Цикл очистки устаревших состояний"""
        while True:
            try:
                await asyncio.sleep(300)  # Каждые 5 минут
                await self._cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup error: {e}")

    async def _cleanup_expired(self):
        """Удаляет устаревшие состояния"""
        async with self._lock:
            now = datetime.now()
            expired = []

            for user_id, state in self._states.items():
                if now - state.updated_at > timedelta(seconds=self._ttl):
                    expired.append(user_id)

            for user_id in expired:
                del self._states[user_id]

            if expired:
                logger.debug(f"Cleaned up {len(expired)} expired states")

    async def get_state(self, user_id: int) -> Optional[str]:
        """Получает текущее состояние пользователя"""
        async with self._lock:
            if user_id in self._states:
                state = self._states[user_id]
                state.updated_at = datetime.now()
                return state.state
            return None

    async def set_state(self, user_id: int, state: Optional[str] = None):
        """Устанавливает состояние пользователя"""
        async with self._lock:
            if user_id not in self._states:
                self._states[user_id] = VkState()

            self._states[user_id].state = state
            self._states[user_id].updated_at = datetime.now()

    async def get_data(self, user_id: int) -> Dict[str, Any]:
        """Получает данные состояния пользователя"""
        async with self._lock:
            if user_id in self._states:
                state = self._states[user_id]
                state.updated_at = datetime.now()
                return state.data.copy()
            return {}

    async def set_data(self, user_id: int, data: Dict[str, Any]):
        """Устанавливает данные состояния пользователя"""
        async with self._lock:
            if user_id not in self._states:
                self._states[user_id] = VkState()

            self._states[user_id].data = data.copy()
            self._states[user_id].updated_at = datetime.now()

    async def update_data(self, user_id: int, **kwargs):
        """Обновляет данные состояния пользователя"""
        async with self._lock:
            if user_id not in self._states:
                self._states[user_id] = VkState()

            state = self._states[user_id]
            state.data.update(kwargs)
            state.updated_at = datetime.now()

    async def clear(self, user_id: int):
        """Очищает состояние пользователя"""
        async with self._lock:
            if user_id in self._states:
                del self._states[user_id]

    async def get_message_id(self, user_id: int) -> Optional[int]:
        """Получает ID последнего сообщения бота"""
        async with self._lock:
            if user_id in self._states:
                return self._states[user_id].message_id
            return None

    async def set_message_id(self, user_id: int, message_id: int):
        """Устанавливает ID последнего сообщения бота"""
        async with self._lock:
            if user_id not in self._states:
                self._states[user_id] = VkState()

            self._states[user_id].message_id = message_id
            self._states[user_id].updated_at = datetime.now()

    async def is_waiting_for_input(self, user_id: int) -> bool:
        """Проверяет, ожидает ли пользователь ввода (находится ли в состоянии FSM)"""
        state = await self.get_state(user_id)
        return state is not None
