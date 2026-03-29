from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.models import UserRole
from tests.utils.user import create_random_app_user, get_token_headers_for_user


def test_dev_token_valid_user(client: TestClient, db: Session) -> None:
    user = create_random_app_user(db, role=UserRole.PATIENT)
    r = client.post(f"{settings.API_V1_STR}/auth/dev-token", params={"user_id": str(user.id)})
    assert r.status_code == 200
    body = r.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"


def test_dev_token_nonexistent_user(client: TestClient) -> None:
    r = client.post(
        f"{settings.API_V1_STR}/auth/dev-token",
        params={"user_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert r.status_code == 404


def test_auth_me_valid(client: TestClient, db: Session) -> None:
    user = create_random_app_user(db, role=UserRole.PROVIDER)
    headers = get_token_headers_for_user(user)
    r = client.get(f"{settings.API_V1_STR}/auth/me", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == str(user.id)
    assert body["role"] == "PROVIDER"


def test_auth_me_no_token(client: TestClient) -> None:
    r = client.get(f"{settings.API_V1_STR}/auth/me")
    assert r.status_code == 401


def test_auth_me_invalid_token(client: TestClient) -> None:
    r = client.get(
        f"{settings.API_V1_STR}/auth/me",
        headers={"Authorization": "Bearer garbage-token"},
    )
    assert r.status_code == 403
