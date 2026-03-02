class TaskError(Exception):
    """Базовое исключение для задач"""
    pass


class TaskNotFoundError(TaskError):
    """Задача не найдена"""
    pass


class TaskValidationError(TaskError):
    """Ошибка валидации задачи"""
    pass


class TaskAccessDeniedError(TaskError):
    """Нет доступа к задаче"""
    pass


class TaskDeadlineError(TaskError):
    """Ошибка с дедлайном"""
    pass


class ReminderError(TaskError):
    """Ошибка с напоминанием"""
    pass
