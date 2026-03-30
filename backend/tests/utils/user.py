import uuid

from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.security import create_access_token
from app.models import AppUser, AppUserCreate, UserRole


async def create_random_app_user(db: AsyncSession, role: UserRole = UserRole.PATIENT) -> AppUser:
    user_in = AppUserCreate(role=role, display_name=f"Test-{uuid.uuid4().hex[:8]}")
    return await crud.create_app_user(session=db, user_in=user_in)


def get_token_headers_for_user(user: AppUser) -> dict[str, str]:
    token = create_access_token(user_id=str(user.id), role=user.role.value, fhir_ref=user.fhir_ref)
    return {"Authorization": f"Bearer {token}"}
