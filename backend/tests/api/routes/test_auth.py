from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.models import UserRole
from tests.utils.user import create_random_app_user, get_token_headers_for_user


async def test_dev_token_valid_user(client: AsyncClient, db: AsyncSession) -> None:
    user = await create_random_app_user(db, role=UserRole.PATIENT)
    r = await client.post(f"{settings.API_V1_STR}/private/dev-token", params={"user_id": str(user.id)})
    assert r.status_code == 200
    body = r.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"


async def test_dev_token_nonexistent_user(client: AsyncClient) -> None:
    r = await client.post(
        f"{settings.API_V1_STR}/private/dev-token",
        params={"user_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert r.status_code == 404


async def test_auth_me_valid(client: AsyncClient, db: AsyncSession) -> None:
    user = await create_random_app_user(db, role=UserRole.PROVIDER)
    headers = get_token_headers_for_user(user)
    r = await client.get(f"{settings.API_V1_STR}/auth/me", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == str(user.id)
    assert body["role"] == "PROVIDER"


async def test_auth_me_no_token(client: AsyncClient) -> None:
    r = await client.get(f"{settings.API_V1_STR}/auth/me")
    assert r.status_code == 401


async def test_auth_me_invalid_token(client: AsyncClient) -> None:
    r = await client.get(
        f"{settings.API_V1_STR}/auth/me",
        headers={"Authorization": "Bearer garbage-token"},
    )
    assert r.status_code == 403
