from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.core.db import init_db
from app.core.security import create_access_token
from app.main import app
from app.models import AppUser, UserRole


@pytest.fixture(scope="session")
async def engine() -> AsyncGenerator[AsyncEngine]:
    e = create_async_engine(str(settings.SQLALCHEMY_DATABASE_URI))
    yield e
    await e.dispose()


@pytest.fixture(scope="session", autouse=True)
async def _seed_db(engine: AsyncEngine) -> None:
    async with AsyncSession(engine) as session:
        await init_db(session)


@pytest.fixture
async def db(engine: AsyncEngine) -> AsyncGenerator[AsyncSession]:
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient]:
    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _make_token_headers(user: AppUser) -> dict[str, str]:
    token = create_access_token(user_id=str(user.id), role=user.role.value, fhir_ref=user.fhir_ref)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def superuser_token_headers(db: AsyncSession) -> dict[str, str]:
    result = await db.exec(select(AppUser).where(AppUser.role == UserRole.SUPER_USER))
    user = result.first()
    assert user is not None
    return _make_token_headers(user)
