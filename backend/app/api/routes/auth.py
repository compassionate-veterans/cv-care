from fastapi import APIRouter, HTTPException

from app.api.deps import CurrentUser, SessionDep
from app.core import security
from app.core.config import settings
from app.models import AppUser, AppUserPublic, Token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/dev-token", response_model=Token)
def dev_token(session: SessionDep, user_id: str) -> Token:
    """DEV ONLY: Issue a token for a given user_id."""
    if settings.ENVIRONMENT != "local":
        raise HTTPException(status_code=404)
    user = session.get(AppUser, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    token = security.create_access_token(user_id=str(user.id), role=user.role.value, fhir_ref=user.fhir_ref)
    return Token(access_token=token)


@router.get("/me", response_model=AppUserPublic)
def read_current_user(current_user: CurrentUser) -> AppUser:
    """Verify token and return current user."""
    return current_user
