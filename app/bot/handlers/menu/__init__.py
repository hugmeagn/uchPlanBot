from .start import router as start_router
from .menu import router as menu_router
from .help import router as help_router
from ..planner import router as planner_router  # Добавляем
from ...utils.router import new_router

router = new_router(
    start_router,
    menu_router,
    help_router,
    planner_router,  # Добавляем
)
