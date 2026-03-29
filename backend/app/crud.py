import uuid
from datetime import UTC, datetime

from sqlmodel import Session, select

from app.models import (
    AppUser,
    AppUserCreate,
    AppUserUpdate,
    AuthIdentity,
    AuthProvider,
)


def create_app_user(*, session: Session, user_in: AppUserCreate) -> AppUser:
    db_obj = AppUser.model_validate(user_in)
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def get_app_user(*, session: Session, user_id: uuid.UUID) -> AppUser | None:
    return session.get(AppUser, user_id)


def update_app_user(*, session: Session, db_user: AppUser, user_in: AppUserUpdate) -> AppUser:
    user_data = user_in.model_dump(exclude_unset=True)
    db_user.sqlmodel_update(user_data)
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user


def get_user_by_identity(*, session: Session, provider: AuthProvider, external_id: str) -> AppUser | None:
    statement = (
        select(AppUser)
        .join(AuthIdentity)
        .where(
            AuthIdentity.provider == provider,
            AuthIdentity.external_id == external_id,
        )
    )
    return session.exec(statement).first()


def create_auth_identity(
    *,
    session: Session,
    user_id: uuid.UUID,
    provider: AuthProvider,
    external_id: str,
) -> AuthIdentity:
    identity = AuthIdentity(user_id=user_id, provider=provider, external_id=external_id)
    session.add(identity)
    session.commit()
    session.refresh(identity)
    return identity


def touch_last_login(*, session: Session, user: AppUser) -> None:
    user.last_login_at = datetime.now(UTC)
    session.add(user)
    session.commit()
