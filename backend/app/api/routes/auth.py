from fastapi import APIRouter

from app.api.deps import CurrentUser
from app.models import AppUser, AppUserPublic

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me", response_model=AppUserPublic)
async def read_current_user(current_user: CurrentUser) -> AppUser:
    """Verify token and return current user."""
    return current_user
