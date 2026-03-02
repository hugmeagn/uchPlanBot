from aiogram import Router


def new_router(*routers) -> Router:
    router = Router()
    for r in routers:
        router.include_router(r)

    return router
