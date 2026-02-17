from sqlalchemy import select

from bot.config import settings
from bot.db.database import async_session
from bot.db.models import Admin


async def is_admin(user_id: int) -> bool:
    if user_id in settings.SENIOR_ADMIN_IDS:
        return True
    async with async_session() as session:
        result = await session.execute(
            select(Admin).where(Admin.id == user_id, Admin.is_active.is_(True))
        )
        return result.scalar_one_or_none() is not None
