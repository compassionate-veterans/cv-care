import uuid

from fastapi import APIRouter, HTTPException

from app import crud
from app.api.deps import SessionDep
from app.core import security
from app.models import AppUser, AppUserCreate, AppUserPublic, Token

router = APIRouter(tags=["private"], prefix="/private")


@router.post("/users/", response_model=AppUserPublic)
async def create_user(user_in: AppUserCreate, session: SessionDep) -> AppUser:
    """Create a new user (dev only, no auth required)."""
    return await crud.create_app_user(session=session, user_in=user_in)


@router.post("/dev-token", response_model=Token)
async def dev_token(session: SessionDep, user_id: uuid.UUID) -> Token:
    """Issue a token for a given user_id. Dev only."""
    user = await session.get(AppUser, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    token = security.create_access_token(user_id=str(user.id), role=user.role.value, fhir_ref=user.fhir_ref)
    return Token(access_token=token)
