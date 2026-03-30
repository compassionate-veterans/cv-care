from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.config import settings
from app.models import AppUser, AppUserCreate, UserRole

engine = create_async_engine(str(settings.SQLALCHEMY_DATABASE_URI))


async def init_db(session: AsyncSession) -> None:
    result = await session.exec(select(AppUser).where(AppUser.role == UserRole.SUPER_USER))
    user = result.first()
    if not user:
        user_in = AppUserCreate(
            role=UserRole.SUPER_USER,
            display_name=settings.FIRST_SUPERUSER_DISPLAY_NAME,
        )
        await crud.create_app_user(session=session, user_in=user_in)
