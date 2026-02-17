from aiogram import Router

from bot.handlers.admin import router as admin_router
from bot.handlers.common import router as common_router
from bot.handlers.user import router as user_router


def get_all_routers() -> list[Router]:
    return [common_router, admin_router, user_router]
