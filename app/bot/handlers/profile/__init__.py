from .setup import router as setup_router
from .profile import router as profile_router
from ...utils.router import new_router

router = new_router(
    setup_router,
    profile_router,
)
