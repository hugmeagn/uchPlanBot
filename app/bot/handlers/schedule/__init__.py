from .schedule import router as schedule_router
from ...utils.router import new_router

router = new_router(
    schedule_router,
)
