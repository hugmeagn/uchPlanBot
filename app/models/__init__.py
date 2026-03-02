from .institution import Institution
from .user import User
from .task import TaskModel, TaskReminderModel
from .notification import NotificationModel, NotificationTemplateModel

MODULES = ("institution", "user", "task", "notification", "daily_plan")

# Список моделей для регистрации в Tortoise
TORTOISE_MODELS = tuple(f"models.{e}" for e in MODULES)
