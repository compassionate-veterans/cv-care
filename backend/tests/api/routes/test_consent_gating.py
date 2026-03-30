from typing import Any

from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.models import UserRole
from tests.utils.user import create_random_app_user, get_token_headers_for_user


async def _enroll(client: AsyncClient, headers: dict[str, str], name: str, phone: str) -> dict[str, Any]:
    r = await client.post(
        f"{settings.API_V1_STR}/patients/",
        headers=headers,
        json={"display_name": name, "phone": phone},
    )
    resp: dict[str, Any] = r.json()
    return resp


async def _grant_consent(client: AsyncClient, headers: dict[str, str], patient_id: str, consent_type: str) -> None:
    r = await client.post(
        f"{settings.API_V1_STR}/patients/{patient_id}/consents/",
        headers=headers,
        json={"consent_type": consent_type},
    )
    assert r.status_code == 201


async def _revoke_consent(client: AsyncClient, headers: dict[str, str], patient_id: str, consent_id: str) -> None:
    r = await client.post(
        f"{settings.API_V1_STR}/patients/{patient_id}/consents/{consent_id}/revoke",
        headers=headers,
    )
    assert r.status_code == 200


async def test_clinical_without_consent_404(client: AsyncClient, db: AsyncSession) -> None:
    provider = await create_random_app_user(db, role=UserRole.PROVIDER)
    headers = get_token_headers_for_user(provider)
    enrolled = await _enroll(client, headers, "No Consent", "+15105552001")
    r = await client.get(f"{settings.API_V1_STR}/patients/{enrolled['id']}/clinical", headers=headers)
    assert r.status_code == 404


async def test_clinical_with_consent_200(client: AsyncClient, db: AsyncSession) -> None:
    provider = await create_random_app_user(db, role=UserRole.PROVIDER)
    headers = get_token_headers_for_user(provider)
    enrolled = await _enroll(client, headers, "With Consent", "+15105552002")
    await _grant_consent(client, headers, enrolled["id"], "therapy_participation")
    r = await client.get(f"{settings.API_V1_STR}/patients/{enrolled['id']}/clinical", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["resourceType"] == "Patient"


async def test_clinical_after_revoke_404(client: AsyncClient, db: AsyncSession) -> None:
    provider = await create_random_app_user(db, role=UserRole.PROVIDER)
    headers = get_token_headers_for_user(provider)
    enrolled = await _enroll(client, headers, "Revoke Gate", "+15105552003")
    await _grant_consent(client, headers, enrolled["id"], "therapy_participation")
    consents_r = await client.get(f"{settings.API_V1_STR}/patients/{enrolled['id']}/consents/", headers=headers)
    consent_id = consents_r.json()[0]["id"]
    await _revoke_consent(client, headers, enrolled["id"], consent_id)
    r = await client.get(f"{settings.API_V1_STR}/patients/{enrolled['id']}/clinical", headers=headers)
    assert r.status_code == 404
