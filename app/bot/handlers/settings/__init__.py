from .settings import router as settings_router
from ...utils.router import new_router

router = new_router(
    settings_router,
)
