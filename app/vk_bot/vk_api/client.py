"""
Клиент для работы с VK API через LongPoll
"""
import asyncio
import logging
import json
from typing import Optional, Dict, Any, List, Callable, Awaitable
from dataclasses import dataclass
from enum import Enum

import aiohttp
import config

logger = logging.getLogger(__name__)


class VkEventType(str, Enum):
    """Типы событий VK LongPoll"""
    MESSAGE_NEW = "message_new"
    MESSAGE_EDIT = "message_edit"
    MESSAGE_ALLOW = "message_allow"
    MESSAGE_DENY = "message_deny"


@dataclass
class VkMessage:
    """Представление сообщения VK"""
    message_id: int
    from_id: int
    peer_id: int
    text: str
    date: int
    payload: Optional[Dict[str, Any]] = None
    attachments: List[Dict] = None
    conversation_message_id: int = None

    @property
    def is_command(self) -> bool:
        """Проверяет, является ли сообщение командой"""
        return self.text.startswith('/') if self.text else False

    @property
    def command(self) -> Optional[str]:
        """Возвращает команду без слеша"""
        if self.is_command:
            return self.text.split()[0][1:].lower()
        return None

    @property
    def command_args(self) -> List[str]:
        """Возвращает аргументы команды"""
        if self.is_command:
            parts = self.text.split()
            return parts[1:] if len(parts) > 1 else []
        return []


@dataclass
class VkLongPollEvent:
    """Событие LongPoll"""
    type: VkEventType
    message: Optional[VkMessage] = None
    raw: Dict[str, Any] = None


class VkApiClient:
    """
    Клиент для работы с VK API
    """

    def __init__(self, token: str, group_id: int, api_version: str = "5.199"):
        self.token = token
        self.group_id = group_id
        self.api_version = api_version
        self.base_url = "https://api.vk.com/method/"

        self._longpoll_server: Optional[Dict] = None
        self._session: Optional[aiohttp.ClientSession] = None
        self._running = False

        # Обработчики событий
        self._handlers: Dict[VkEventType, List[Callable]] = {
            event_type: [] for event_type in VkEventType
        }

    async def _get_session(self) -> aiohttp.ClientSession:
        """Получает или создает сессию"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def api_request(
        self,
        method: str,
        params: Dict[str, Any] = None,
        retry: int = 3
    ) -> Optional[Any]:
        """
        Выполняет запрос к VK API

        Returns:
            Ответ API (может быть dict, list, int)
        """
        if params is None:
            params = {}

        params.update({
            "access_token": self.token,
            "v": self.api_version
        })

        url = f"{self.base_url}{method}"

        for attempt in range(retry):
            try:
                session = await self._get_session()
                async with session.post(url, data=params) as response:
                    data = await response.json()

                    if "error" in data:
                        error = data["error"]
                        logger.error(f"VK API error: {error}")

                        # Если слишком много запросов, ждем
                        if error.get("error_code") == 6:
                            await asyncio.sleep(1)
                            continue

                        return None

                    return data.get("response")

            except Exception as e:
                logger.error(f"VK API request failed (attempt {attempt + 1}): {e}")
                if attempt < retry - 1:
                    await asyncio.sleep(2 ** attempt)
                else:
                    return None

    async def send_message(
        self,
        peer_id: int,
        text: str,
        keyboard: Optional[str] = None,
        attachment: Optional[str] = None,
        forward_messages: Optional[List[int]] = None,
        dont_parse_links: bool = False,
        disable_mentions: bool = False
    ) -> Optional[int]:
        """
        Отправляет сообщение пользователю

        Returns:
            message_id или None в случае ошибки
        """
        import random

        params = {
            "peer_id": peer_id,
            "message": text,
            "random_id": random.randint(-2147483648, 2147483647)
        }

        if keyboard:
            params["keyboard"] = keyboard

        if attachment:
            params["attachment"] = attachment

        if forward_messages:
            params["forward_messages"] = ",".join(map(str, forward_messages))

        if dont_parse_links:
            params["dont_parse_links"] = 1

        if disable_mentions:
            params["disable_mentions"] = 1

        result = await self.api_request("messages.send", params)

        if result is not None:
            # messages.send возвращает число (ID сообщения) или список в случае множественной отправки
            if isinstance(result, list):
                return result[0] if result else None
            elif isinstance(result, dict):
                return result.get("message_id")
            else:
                return result
        return None

    async def edit_message(
        self,
        peer_id: int,
        message_id: int,
        text: str,
        keyboard: Optional[str] = None
    ) -> bool:
        """
        Редактирует сообщение
        """
        params = {
            "peer_id": peer_id,
            "message_id": message_id,
            "message": text
        }

        if keyboard:
            params["keyboard"] = keyboard

        result = await self.api_request("messages.edit", params)
        return result is not None and result == 1

    async def delete_message(
        self,
        peer_id: int,
        message_ids: List[int],
        delete_for_all: bool = True
    ) -> bool:
        """
        Удаляет сообщения
        """
        params = {
            "peer_id": peer_id,
            "message_ids": ",".join(map(str, message_ids)),
            "delete_for_all": 1 if delete_for_all else 0
        }

        result = await self.api_request("messages.delete", params)
        return result is not None

    async def get_conversation_members(self, peer_id: int) -> List[int]:
        """
        Получает список участников беседы
        """
        result = await self.api_request("messages.getConversationMembers", {
            "peer_id": peer_id
        })

        if result:
            return result.get("items", [])
        return []

    async def get_user_info(self, user_ids: List[int]) -> List[Dict]:
        """
        Получает информацию о пользователях
        """
        result = await self.api_request("users.get", {
            "user_ids": ",".join(map(str, user_ids)),
            "fields": "first_name,last_name,photo_100"
        })

        return result or []

    # ==================== LongPoll ====================

    async def _get_longpoll_server(self) -> Dict:
        """Получает сервер для LongPoll"""
        result = await self.api_request("groups.getLongPollServer", {
            "group_id": self.group_id
        })

        if not result:
            raise Exception("Failed to get LongPoll server")

        return {
            "server": result["server"],
            "key": result["key"],
            "ts": result["ts"]
        }

    async def _check_longpoll(self) -> Optional[Dict]:
        """Проверяет новые события через LongPoll"""
        if not self._longpoll_server:
            self._longpoll_server = await self._get_longpoll_server()

        url = f"{self._longpoll_server['server']}?act=a_check&key={self._longpoll_server['key']}&ts={self._longpoll_server['ts']}&wait=25"

        try:
            session = await self._get_session()
            async with session.get(url) as response:
                data = await response.json()

                if "failed" in data:
                    # Сервер требует обновления
                    logger.warning(f"LongPoll failed: {data['failed']}")
                    self._longpoll_server = await self._get_longpoll_server()
                    return None

                # Обновляем ts
                if "ts" in data:
                    self._longpoll_server["ts"] = data["ts"]

                return data

        except Exception as e:
            logger.error(f"LongPoll check error: {e}")
            return None

    def _parse_event(self, raw_event: Dict) -> Optional[VkLongPollEvent]:
        """Парсит сырое событие LongPoll"""
        event_type = raw_event.get("type")

        if event_type == VkEventType.MESSAGE_NEW:
            msg_data = raw_event.get("object", {}).get("message", {})

            # Парсим payload если есть
            payload = None
            payload_str = msg_data.get("payload")
            if payload_str:
                try:
                    payload = json.loads(payload_str)
                except json.JSONDecodeError:
                    pass

            message = VkMessage(
                message_id=msg_data.get("id", 0),
                from_id=msg_data.get("from_id", 0),
                peer_id=msg_data.get("peer_id", 0),
                text=msg_data.get("text", ""),
                date=msg_data.get("date", 0),
                payload=payload,
                attachments=msg_data.get("attachments", []),
                conversation_message_id=msg_data.get("conversation_message_id")
            )

            return VkLongPollEvent(
                type=VkEventType.MESSAGE_NEW,
                message=message,
                raw=raw_event
            )

        elif event_type == VkEventType.MESSAGE_EDIT:
            msg_data = raw_event.get("object", {})

            payload = None
            payload_str = msg_data.get("payload")
            if payload_str:
                try:
                    payload = json.loads(payload_str)
                except json.JSONDecodeError:
                    pass

            message = VkMessage(
                message_id=msg_data.get("id", 0),
                from_id=msg_data.get("from_id", 0),
                peer_id=msg_data.get("peer_id", 0),
                text=msg_data.get("text", ""),
                date=msg_data.get("date", 0),
                payload=payload,
                conversation_message_id=msg_data.get("conversation_message_id")
            )

            return VkLongPollEvent(
                type=VkEventType.MESSAGE_EDIT,
                message=message,
                raw=raw_event
            )

        return VkLongPollEvent(type=event_type, raw=raw_event)

    def on_message(self, handler: Callable[[VkMessage], Awaitable[None]] = None):
        """
        Регистрирует обработчик новых сообщений.
        Может использоваться как декоратор или прямой вызов.
        """
        if handler is not None:
            self._handlers[VkEventType.MESSAGE_NEW].append(handler)
            return handler

        def decorator(h):
            self._handlers[VkEventType.MESSAGE_NEW].append(h)
            return h

        return decorator

    def on_message_edit(self, handler: Callable[[VkMessage], Awaitable[None]] = None):
        """
        Регистрирует обработчик редактирования сообщений.
        """
        if handler is not None:
            self._handlers[VkEventType.MESSAGE_EDIT].append(handler)
            return handler

        def decorator(h):
            self._handlers[VkEventType.MESSAGE_EDIT].append(h)
            return h

        return decorator

    async def _handle_event(self, event: VkLongPollEvent):
        """Обрабатывает событие"""
        handlers = self._handlers.get(event.type, [])

        for handler in handlers:
            try:
                if event.type in (VkEventType.MESSAGE_NEW, VkEventType.MESSAGE_EDIT):
                    await handler(event.message)
                else:
                    await handler(event)
            except Exception as e:
                logger.error(f"Handler error for {event.type}: {e}", exc_info=True)

    async def start_polling(self):
        """Запускает LongPoll"""
        self._running = True
        logger.info("VK LongPoll started")

        while self._running:
            try:
                events_data = await self._check_longpoll()

                if events_data and "updates" in events_data:
                    for update in events_data["updates"]:
                        event = self._parse_event(update)
                        if event:
                            asyncio.create_task(self._handle_event(event))

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Polling error: {e}")
                await asyncio.sleep(5)

    async def stop(self):
        """Останавливает LongPoll"""
        self._running = False
        if self._session and not self._session.closed:
            await self._session.close()
        logger.info("VK LongPoll stopped")
