from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.models import UserRole
from tests.utils.user import create_random_app_user, get_token_headers_for_user


async def test_list_users_as_superuser(client: AsyncClient, superuser_token_headers: dict[str, str]) -> None:
    r = await client.get(f"{settings.API_V1_STR}/users/", headers=superuser_token_headers)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


async def test_list_users_as_patient_forbidden(client: AsyncClient, db: AsyncSession) -> None:
    user = await create_random_app_user(db, role=UserRole.PATIENT)
    headers = get_token_headers_for_user(user)
    r = await client.get(f"{settings.API_V1_STR}/users/", headers=headers)
    assert r.status_code == 403


async def test_create_user_as_superuser(client: AsyncClient, superuser_token_headers: dict[str, str]) -> None:
    r = await client.post(
        f"{settings.API_V1_STR}/users/",
        headers=superuser_token_headers,
        json={"role": "PATIENT", "display_name": "Created Via API"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["display_name"] == "Created Via API"
    assert body["role"] == "PATIENT"


async def test_create_user_as_patient_forbidden(client: AsyncClient, db: AsyncSession) -> None:
    user = await create_random_app_user(db, role=UserRole.PATIENT)
    headers = get_token_headers_for_user(user)
    r = await client.post(
        f"{settings.API_V1_STR}/users/",
        headers=headers,
        json={"role": "PATIENT", "display_name": "Should Fail"},
    )
    assert r.status_code == 403


async def test_get_user_as_superuser(
    client: AsyncClient, superuser_token_headers: dict[str, str], db: AsyncSession
) -> None:
    user = await create_random_app_user(db, role=UserRole.PATIENT)
    r = await client.get(f"{settings.API_V1_STR}/users/{user.id}", headers=superuser_token_headers)
    assert r.status_code == 200
    assert r.json()["id"] == str(user.id)


async def test_delete_user_as_superuser(
    client: AsyncClient, superuser_token_headers: dict[str, str], db: AsyncSession
) -> None:
    user = await create_random_app_user(db, role=UserRole.PATIENT)
    r = await client.delete(f"{settings.API_V1_STR}/users/{user.id}", headers=superuser_token_headers)
    assert r.status_code == 200
    assert r.json()["message"] == "User deleted"
