from enum import Enum


class TaskStatus(str, Enum):
    """Статусы задач"""
    ACTIVE = "active"           # Активная задача
    COMPLETED = "completed"      # Выполнена
    OVERDUE = "overdue"         # Просрочена
    ARCHIVED = "archived"        # В архиве
    POSTPONED = "postponed"      # Отложена


class TaskPriority(int, Enum):
    """Приоритеты задач"""
    LOW = 0
    MEDIUM = 1
    HIGH = 2
    CRITICAL = 3


class TaskCategory(str, Enum):
    """Категории задач (можно расширять)"""
    STUDY = "study"              # Учеба
    HOMEWORK = "homework"        # Домашнее задание
    EXAM = "exam"                # Экзамен
    PROJECT = "project"          # Проект
    PERSONAL = "personal"        # Личное
    OTHER = "other"              # Другое


class ReminderType(str, Enum):
    """Типы напоминаний"""
    BEFORE_DEADLINE = "before_deadline"  # За время до дедлайна
    AT_DEADLINE = "at_deadline"          # В момент дедлайна
    AFTER_DEADLINE = "after_deadline"    # После дедлайна
    CUSTOM = "custom"                     # Произвольное


class SortField(str, Enum):
    """Поля для сортировки"""
    DEADLINE = "deadline"
    PRIORITY = "priority"
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"
    TITLE = "title"
    STATUS = "status"


class SortOrder(str, Enum):
    """Направление сортировки"""
    ASC = "asc"
    DESC = "desc"
