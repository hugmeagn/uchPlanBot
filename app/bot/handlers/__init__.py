"""
Инициализация всех обработчиков.
"""
from .menu import router as menu_router
from .profile import router as profile_router
from .settings import router as settings_router
from .schedule import router as schedule_router
from .tasks import router as tasks_router
from .notifications import router as notifications_router
from ..utils.router import new_router

router = new_router(
    menu_router,
    profile_router,
    settings_router,
    schedule_router,
    tasks_router,
    notifications_router,
)
