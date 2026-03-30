from collections.abc import AsyncGenerator, Callable
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import InvalidTokenError
from pydantic import ValidationError
from sqlmodel.ext.asyncio.session import AsyncSession

from app import fhir
from app.core import security
from app.core.config import settings
from app.core.db import engine
from app.models import AppUser, TokenPayload, UserRole

bearer_scheme = HTTPBearer()


async def get_db() -> AsyncGenerator[AsyncSession]:
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_db)]
TokenDep = Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)]


async def get_current_user(session: SessionDep, credentials: TokenDep) -> AppUser:
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.SECRET_KEY,
            algorithms=[security.ALGORITHM],
        )
        token_data = TokenPayload(**payload)
    except (InvalidTokenError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )
    user = await session.get(AppUser, token_data.sub)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


CurrentUser = Annotated[AppUser, Depends(get_current_user)]


def get_fhir(request: Request) -> fhir.Client:
    return request.app.state.fhir  # type: ignore[no-any-return]


FHIRDep = Annotated[fhir.Client, Depends(get_fhir)]


def _require_role(*allowed: UserRole) -> Callable[[CurrentUser], AppUser]:
    def checker(current_user: CurrentUser) -> AppUser:
        if current_user.role not in allowed:
            raise HTTPException(status_code=403, detail="Insufficient privileges")
        return current_user

    return checker


RequireProvider = Annotated[AppUser, Depends(_require_role(UserRole.PROVIDER, UserRole.SUPER_USER))]
RequireAdminCannabis = Annotated[
    AppUser,
    Depends(_require_role(UserRole.ADMIN_CANNABIS, UserRole.PROVIDER, UserRole.SUPER_USER)),
]
RequirePatient = Annotated[
    AppUser,
    Depends(_require_role(UserRole.PATIENT, UserRole.PROVIDER, UserRole.SUPER_USER)),
]
RequireSuperUser = Annotated[AppUser, Depends(_require_role(UserRole.SUPER_USER))]
