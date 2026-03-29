from fastapi import APIRouter

from app import crud
from app.api.deps import SessionDep
from app.models import AppUser, AppUserCreate, AppUserPublic

router = APIRouter(tags=["private"], prefix="/private")


@router.post("/users/", response_model=AppUserPublic)
def create_user(user_in: AppUserCreate, session: SessionDep) -> AppUser:
    """Create a new user (dev only, no auth required)."""
    return crud.create_app_user(session=session, user_in=user_in)
