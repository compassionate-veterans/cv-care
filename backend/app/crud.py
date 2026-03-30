import uuid
from datetime import UTC, datetime

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models import (
    AppUser,
    AppUserCreate,
    AppUserUpdate,
    AuthIdentity,
    AuthProvider,
)


async def create_app_user(*, session: AsyncSession, user_in: AppUserCreate) -> AppUser:
    db_obj = AppUser.model_validate(user_in)
    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return db_obj


async def get_app_user(*, session: AsyncSession, user_id: uuid.UUID) -> AppUser | None:
    return await session.get(AppUser, user_id)


async def update_app_user(*, session: AsyncSession, db_user: AppUser, user_in: AppUserUpdate) -> AppUser:
    user_data = user_in.model_dump(exclude_unset=True)
    db_user.sqlmodel_update(user_data)
    session.add(db_user)
    await session.commit()
    await session.refresh(db_user)
    return db_user


async def get_user_by_identity(*, session: AsyncSession, provider: AuthProvider, external_id: str) -> AppUser | None:
    statement = (
        select(AppUser)
        .join(AuthIdentity)
        .where(
            AuthIdentity.provider == provider,
            AuthIdentity.external_id == external_id,
        )
    )
    result = await session.exec(statement)
    return result.first()


async def create_auth_identity(
    *,
    session: AsyncSession,
    user_id: uuid.UUID,
    provider: AuthProvider,
    external_id: str,
) -> AuthIdentity:
    identity = AuthIdentity(user_id=user_id, provider=provider, external_id=external_id)
    session.add(identity)
    await session.commit()
    await session.refresh(identity)
    return identity


async def touch_last_login(*, session: AsyncSession, user: AppUser) -> None:
    user.last_login_at = datetime.now(UTC)
    session.add(user)
    await session.commit()
