from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, field_validator
import uuid

from bot.utils import dates


class NotificationChannel(str, Enum):
    """Каналы доставки уведомлений"""
    TELEGRAM = "telegram"
    EMAIL = "email"
    SMS = "sms"
    WEBHOOK = "webhook"
    CONSOLE = "console"  # для отладки


class NotificationPriority(int, Enum):
    """Приоритет уведомлений (числовые значения для БД)"""
    LOW = 0
    MEDIUM = 1
    HIGH = 2
    CRITICAL = 3


class NotificationStatus(str, Enum):
    """Статусы уведомлений"""
    PENDING = "pending"  # ожидает отправки
    SENDING = "sending"
    SENT = "sent"  # отправлено
    DELIVERED = "delivered"  # доставлено
    FAILED = "failed"  # ошибка отправки
    CANCELLED = "cancelled"  # отменено
    SCHEDULED = "scheduled"  # запланировано


class NotificationType(str, Enum):
    """Типы уведомлений"""
    TASK_REMINDER = "task_reminder"
    DEADLINE_ALERT = "deadline_alert"
    SCHEDULE_CHANGE = "schedule_change"
    SYSTEM_ALERT = "system_alert"
    TASK_CREATED = "task_created"
    TASK_COMPLETED = "task_completed"
    CUSTOM = "custom"


class Notification(BaseModel):
    """Основная модель уведомления"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    channel: NotificationChannel
    type: NotificationType
    priority: NotificationPriority = NotificationPriority.MEDIUM
    status: NotificationStatus = NotificationStatus.PENDING

    title: str
    content: str
    data: Optional[Dict[str, Any]] = None  # дополнительные данные

    scheduled_for: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    retry_count: int = 0
    max_retries: int = 3
    last_error: Optional[str] = None

    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator('scheduled_for')
    def validate_scheduled_for(cls, v):
        if v and v < dates.now():
            raise ValueError('scheduled_for cannot be in the past')
        return v


class NotificationTemplate(BaseModel):
    """Шаблон уведомления"""
    id: str
    name: str
    type: NotificationType
    channel: NotificationChannel
    title_template: str
    content_template: str
    variables: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)


class NotificationStats(BaseModel):
    """Статистика по уведомлениям"""
    total_sent: int = 0
    total_failed: int = 0
    total_pending: int = 0
    by_channel: Dict[NotificationChannel, int] = Field(default_factory=dict)
    by_type: Dict[NotificationType, int] = Field(default_factory=dict)
    by_priority: Dict[NotificationPriority, int] = Field(default_factory=dict)