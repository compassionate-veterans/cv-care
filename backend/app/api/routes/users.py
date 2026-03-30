import uuid

from fastapi import APIRouter, HTTPException
from sqlmodel import select

from app import crud
from app.api.deps import RequireSuperUser, SessionDep
from app.models import AppUser, AppUserCreate, AppUserPublic, Message

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/", response_model=list[AppUserPublic])
async def list_users(
    session: SessionDep,
    _: RequireSuperUser,
    skip: int = 0,
    limit: int = 100,
) -> list[AppUser]:
    statement = select(AppUser).offset(skip).limit(limit)
    result = await session.exec(statement)
    return list(result.all())


@router.post("/", response_model=AppUserPublic, status_code=201)
async def create_user(session: SessionDep, _: RequireSuperUser, user_in: AppUserCreate) -> AppUser:
    return await crud.create_app_user(session=session, user_in=user_in)


@router.get("/{user_id}", response_model=AppUserPublic)
async def get_user(session: SessionDep, _: RequireSuperUser, user_id: uuid.UUID) -> AppUser:
    user = await session.get(AppUser, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.delete("/{user_id}", response_model=Message)
async def delete_user(session: SessionDep, _: RequireSuperUser, user_id: uuid.UUID) -> Message:
    user = await session.get(AppUser, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    await session.delete(user)
    await session.commit()
    return Message(message="User deleted")
