from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator, ConfigDict
import uuid
import bot.utils.dates as dates

from .enums import TaskStatus, TaskPriority, TaskCategory, ReminderType


class TaskReminder(BaseModel):
    """Напоминание по задаче"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str
    reminder_type: ReminderType
    time_before: Optional[int] = None  # минут до дедлайна
    custom_time: Optional[datetime] = None  # конкретное время
    sent: bool = False
    sent_at: Optional[datetime] = None
    notification_id: Optional[str] = None  # ID уведомления из системы нотификаций

    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)


class Task(BaseModel):
    """Основная модель задачи"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str  # ID пользователя в Telegram

    # Основные поля
    title: str
    description: Optional[str] = None
    category: TaskCategory = TaskCategory.OTHER
    priority: TaskPriority = TaskPriority.MEDIUM
    status: TaskStatus = TaskStatus.ACTIVE

    # Даты
    deadline: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: dates.now())
    updated_at: datetime = Field(default_factory=lambda: dates.now())
    completed_at: Optional[datetime] = None

    # Напоминания
    reminders: List[TaskReminder] = Field(default_factory=list)
    reminder_enabled: bool = True

    # Дополнительные поля
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    parent_task_id: Optional[str] = None  # для подзадач
    subtasks: List[str] = Field(default_factory=list)  # ID подзадач

    # Прогресс
    progress: int = Field(default=0, ge=0, le=100)

    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)

    @field_validator('deadline', mode='before')
    def validate_deadline(cls, v):
        if v is None:
            return v
        # Если deadline уже offset-aware, оставляем как есть
        if hasattr(v, 'tzinfo') and v.tzinfo is not None:
            return v
        # Если naive, делаем aware (UTC)
        return v.replace(tzinfo=timezone.utc)

    def _ensure_aware(self, dt: Optional[datetime]) -> Optional[datetime]:
        """Преобразует naive datetime в aware (UTC)"""
        if dt is None:
            return None
        if hasattr(dt, 'tzinfo') and dt.tzinfo is not None:
            return dt
        return dt.replace(tzinfo=timezone.utc)

    def is_overdue(self) -> bool:
        """Проверяет, просрочена ли задача"""
        if not self.deadline or self.status in [TaskStatus.COMPLETED, TaskStatus.ARCHIVED]:
            return False

        # Приводим оба времени к UTC для сравнения
        now = dates.now()
        deadline = self._ensure_aware(self.deadline)

        return deadline < now and self.status != TaskStatus.COMPLETED

    def mark_completed(self):
        """Отмечает задачу как выполненную"""
        self.status = TaskStatus.COMPLETED
        self.completed_at = dates.now()
        self.updated_at = dates.now()
        self.progress = 100

    def update_progress(self, progress: int):
        """Обновляет прогресс задачи"""
        self.progress = max(0, min(100, progress))
        self.updated_at = dates.now()

        if self.progress == 100 and self.status != TaskStatus.COMPLETED:
            self.mark_completed()

class TaskFilter(BaseModel):
    """Фильтр для поиска задач"""
    status: Optional[List[TaskStatus]] = None
    priority: Optional[List[TaskPriority]] = None
    category: Optional[List[TaskCategory]] = None
    tags: Optional[List[str]] = None
    deadline_from: Optional[datetime] = None
    deadline_to: Optional[datetime] = None
    created_from: Optional[datetime] = None
    created_to: Optional[datetime] = None
    search_text: Optional[str] = None  # поиск по title и description
    has_deadline: Optional[bool] = None
    is_overdue: Optional[bool] = None
    reminder_enabled: Optional[bool] = None


class TaskStats(BaseModel):
    """Статистика по задачам"""
    total: int = 0
    active: int = 0
    completed: int = 0
    overdue: int = 0
    archived: int = 0
    by_priority: Dict[TaskPriority, int] = Field(default_factory=dict)
    by_category: Dict[TaskCategory, int] = Field(default_factory=dict)
    upcoming_deadlines: int = 0  # задачи с дедлайном в ближайшие 24 часа
    avg_completion_time: Optional[float] = None  # среднее время выполнения в часах


class TaskExportData(BaseModel):
    """Данные для экспорта задач"""
    tasks: List[Task]
    export_format: str = "json"
    include_completed: bool = False
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
