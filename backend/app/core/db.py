from sqlmodel import Session, create_engine, select

from app import crud
from app.core.config import settings
from app.models import AppUser, AppUserCreate, UserRole

engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))


def init_db(session: Session) -> None:
    user = session.exec(select(AppUser).where(AppUser.role == UserRole.SUPER_USER)).first()
    if not user:
        user_in = AppUserCreate(
            role=UserRole.SUPER_USER,
            display_name=settings.FIRST_SUPERUSER_DISPLAY_NAME,
        )
        crud.create_app_user(session=session, user_in=user_in)
