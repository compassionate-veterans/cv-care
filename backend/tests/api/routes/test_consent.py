from typing import Any

from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.models import AppUser, UserRole
from tests.utils.user import create_random_app_user, get_token_headers_for_user


async def _enroll(client: AsyncClient, headers: dict[str, str], name: str, phone: str) -> dict[str, Any]:
    r = await client.post(
        f"{settings.API_V1_STR}/patients/",
        headers=headers,
        json={"display_name": name, "phone": phone},
    )
    resp: dict[str, Any] = r.json()
    return resp


async def _create_consent(
    client: AsyncClient, headers: dict[str, str], patient_id: str, consent_type: str, expires_at: str | None = None
) -> Any:
    body: dict[str, Any] = {"consent_type": consent_type}
    if expires_at:
        body["expires_at"] = expires_at
    return await client.post(f"{settings.API_V1_STR}/patients/{patient_id}/consents/", headers=headers, json=body)


async def test_create_consent_therapy_participation(client: AsyncClient, db: AsyncSession) -> None:
    provider = await create_random_app_user(db, role=UserRole.PROVIDER)
    headers = get_token_headers_for_user(provider)
    enrolled = await _enroll(client, headers, "Consent Test 1", "+15105551001")
    r = await _create_consent(client, headers, enrolled["id"], "therapy_participation")
    assert r.status_code == 201
    body = r.json()
    assert body["consent_type"] == "therapy-participation"
    assert body["status"] == "active"


async def test_create_consent_mmj_with_expiry(client: AsyncClient, db: AsyncSession) -> None:
    provider = await create_random_app_user(db, role=UserRole.PROVIDER)
    headers = get_token_headers_for_user(provider)
    enrolled = await _enroll(client, headers, "Consent Test 2", "+15105551002")
    r = await _create_consent(client, headers, enrolled["id"], "mmj_management", expires_at="2027-12-31T00:00:00Z")
    assert r.status_code == 201
    body = r.json()
    assert body["expires_at"] is not None


async def test_list_consents_empty(client: AsyncClient, db: AsyncSession) -> None:
    provider = await create_random_app_user(db, role=UserRole.PROVIDER)
    headers = get_token_headers_for_user(provider)
    enrolled = await _enroll(client, headers, "No Consents", "+15105551004")
    r = await client.get(f"{settings.API_V1_STR}/patients/{enrolled['id']}/consents/", headers=headers)
    assert r.status_code == 200
    assert r.json() == []


async def test_list_consents_returns_created(client: AsyncClient, db: AsyncSession) -> None:
    provider = await create_random_app_user(db, role=UserRole.PROVIDER)
    headers = get_token_headers_for_user(provider)
    enrolled = await _enroll(client, headers, "List Consents", "+15105551005")
    await _create_consent(client, headers, enrolled["id"], "therapy_participation")
    await _create_consent(client, headers, enrolled["id"], "recording_ai")
    r = await client.get(f"{settings.API_V1_STR}/patients/{enrolled['id']}/consents/", headers=headers)
    assert r.status_code == 200
    types = {c["consent_type"] for c in r.json()}
    assert "therapy-participation" in types
    assert "recording-ai" in types


async def test_revoke_consent(client: AsyncClient, db: AsyncSession) -> None:
    provider = await create_random_app_user(db, role=UserRole.PROVIDER)
    headers = get_token_headers_for_user(provider)
    enrolled = await _enroll(client, headers, "Revoke Test", "+15105551006")
    created = (await _create_consent(client, headers, enrolled["id"], "therapy_participation")).json()
    r = await client.post(
        f"{settings.API_V1_STR}/patients/{enrolled['id']}/consents/{created['id']}/revoke", headers=headers
    )
    assert r.status_code == 200
    assert r.json()["status"] == "inactive"


async def test_revoke_already_revoked_idempotent(client: AsyncClient, db: AsyncSession) -> None:
    provider = await create_random_app_user(db, role=UserRole.PROVIDER)
    headers = get_token_headers_for_user(provider)
    enrolled = await _enroll(client, headers, "Revoke Twice", "+15105551007")
    created = (await _create_consent(client, headers, enrolled["id"], "therapy_participation")).json()
    await client.post(
        f"{settings.API_V1_STR}/patients/{enrolled['id']}/consents/{created['id']}/revoke", headers=headers
    )
    r = await client.post(
        f"{settings.API_V1_STR}/patients/{enrolled['id']}/consents/{created['id']}/revoke", headers=headers
    )
    assert r.status_code == 200


async def test_create_consent_for_other_patient_as_patient_403(client: AsyncClient, db: AsyncSession) -> None:
    provider = await create_random_app_user(db, role=UserRole.PROVIDER)
    provider_headers = get_token_headers_for_user(provider)
    enrolled = await _enroll(client, provider_headers, "Other Patient", "+15105551008")
    other_patient = await create_random_app_user(db, role=UserRole.PATIENT)
    other_headers = get_token_headers_for_user(other_patient)
    r = await _create_consent(client, other_headers, enrolled["id"], "therapy_participation")
    assert r.status_code == 403


async def test_create_consent_for_self_as_patient(client: AsyncClient, db: AsyncSession) -> None:
    provider = await create_random_app_user(db, role=UserRole.PROVIDER)
    provider_headers = get_token_headers_for_user(provider)
    enrolled = await _enroll(client, provider_headers, "Self Consent", "+15105551009")
    patient_user = await db.get(AppUser, enrolled["id"])
    assert patient_user is not None
    patient_headers = get_token_headers_for_user(patient_user)
    r = await _create_consent(client, patient_headers, enrolled["id"], "therapy_participation")
    assert r.status_code == 201
