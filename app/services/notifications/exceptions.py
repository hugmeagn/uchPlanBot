class NotificationError(Exception):
    """Базовое исключение для уведомлений"""
    pass


class NotificationBackendError(NotificationError):
    """Ошибка бэкенда"""
    pass


class NotificationNotFoundError(NotificationError):
    """Уведомление не найдено"""
    pass


class NotificationValidationError(NotificationError):
    """Ошибка валидации"""
    pass


class NotificationRateLimitError(NotificationError):
    """Превышен лимит отправки"""
    pass
