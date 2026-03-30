from typing import Any

import httpx
from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.models import UserRole
from tests.utils.user import create_random_app_user, get_token_headers_for_user

FHIR_BASE = settings.FHIR_BASE_URL


async def _enroll_with_consent(client: AsyncClient, headers: dict[str, str], name: str, phone: str) -> dict[str, Any]:
    r = await client.post(
        f"{settings.API_V1_STR}/patients/",
        headers=headers,
        json={"display_name": name, "phone": phone},
    )
    enrolled: dict[str, Any] = r.json()
    await client.post(
        f"{settings.API_V1_STR}/patients/{enrolled['id']}/consents/",
        headers=headers,
        json={"consent_type": "therapy_participation"},
    )
    return enrolled


def _create_encounter() -> str:
    r = httpx.post(
        f"{FHIR_BASE}/Encounter",
        json={
            "resourceType": "Encounter",
            "status": "finished",
            "class": {"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode", "code": "VR"},
        },
        headers={"Content-Type": "application/fhir+json"},
    )
    r.raise_for_status()
    return r.json()["id"]


async def test_mark_attendance_as_provider(client: AsyncClient, db: AsyncSession) -> None:
    provider = await create_random_app_user(db, role=UserRole.PROVIDER)
    headers = get_token_headers_for_user(provider)
    enrolled = await _enroll_with_consent(client, headers, "Attend 1", "+15105553001")
    encounter_id = _create_encounter()
    r = await client.post(
        f"{settings.API_V1_STR}/attendance/",
        headers=headers,
        json={"patient_id": enrolled["id"], "encounter_id": encounter_id},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["attended"] is True
    assert body["encounter_id"] == encounter_id


async def test_undo_attendance(client: AsyncClient, db: AsyncSession) -> None:
    provider = await create_random_app_user(db, role=UserRole.PROVIDER)
    headers = get_token_headers_for_user(provider)
    enrolled = await _enroll_with_consent(client, headers, "Undo 1", "+15105553002")
    encounter_id = _create_encounter()
    created = (
        await client.post(
            f"{settings.API_V1_STR}/attendance/",
            headers=headers,
            json={"patient_id": enrolled["id"], "encounter_id": encounter_id},
        )
    ).json()
    r = await client.put(f"{settings.API_V1_STR}/attendance/{created['id']}/undo", headers=headers)
    assert r.status_code == 200
    assert r.json()["status"] == "entered-in-error"


async def test_remark_after_undo(client: AsyncClient, db: AsyncSession) -> None:
    provider = await create_random_app_user(db, role=UserRole.PROVIDER)
    headers = get_token_headers_for_user(provider)
    enrolled = await _enroll_with_consent(client, headers, "Remark 1", "+15105553003")
    encounter_id = _create_encounter()
    created = (
        await client.post(
            f"{settings.API_V1_STR}/attendance/",
            headers=headers,
            json={"patient_id": enrolled["id"], "encounter_id": encounter_id},
        )
    ).json()
    await client.put(f"{settings.API_V1_STR}/attendance/{created['id']}/undo", headers=headers)
    r = await client.post(
        f"{settings.API_V1_STR}/attendance/",
        headers=headers,
        json={"patient_id": enrolled["id"], "encounter_id": encounter_id},
    )
    assert r.status_code == 201


async def test_mark_attendance_as_patient_403(client: AsyncClient, db: AsyncSession) -> None:
    provider = await create_random_app_user(db, role=UserRole.PROVIDER)
    provider_headers = get_token_headers_for_user(provider)
    enrolled = await _enroll_with_consent(client, provider_headers, "Patient Mark", "+15105553004")
    encounter_id = _create_encounter()
    patient = await create_random_app_user(db, role=UserRole.PATIENT)
    patient_headers = get_token_headers_for_user(patient)
    r = await client.post(
        f"{settings.API_V1_STR}/attendance/",
        headers=patient_headers,
        json={"patient_id": enrolled["id"], "encounter_id": encounter_id},
    )
    assert r.status_code == 403


async def test_list_attendance_by_encounter(client: AsyncClient, db: AsyncSession) -> None:
    provider = await create_random_app_user(db, role=UserRole.PROVIDER)
    headers = get_token_headers_for_user(provider)
    enrolled = await _enroll_with_consent(client, headers, "List Enc", "+15105553005")
    encounter_id = _create_encounter()
    await client.post(
        f"{settings.API_V1_STR}/attendance/",
        headers=headers,
        json={"patient_id": enrolled["id"], "encounter_id": encounter_id},
    )
    r = await client.get(f"{settings.API_V1_STR}/attendance/", headers=headers, params={"encounter_id": encounter_id})
    assert r.status_code == 200
    assert len(r.json()) >= 1


async def test_list_attendance_by_patient(client: AsyncClient, db: AsyncSession) -> None:
    provider = await create_random_app_user(db, role=UserRole.PROVIDER)
    headers = get_token_headers_for_user(provider)
    enrolled = await _enroll_with_consent(client, headers, "List Pat", "+15105553006")
    encounter_id = _create_encounter()
    await client.post(
        f"{settings.API_V1_STR}/attendance/",
        headers=headers,
        json={"patient_id": enrolled["id"], "encounter_id": encounter_id},
    )
    r = await client.get(f"{settings.API_V1_STR}/attendance/", headers=headers, params={"patient_id": enrolled["id"]})
    assert r.status_code == 200
    assert len(r.json()) >= 1


async def test_list_attendance_no_filter_422(client: AsyncClient, db: AsyncSession) -> None:
    provider = await create_random_app_user(db, role=UserRole.PROVIDER)
    headers = get_token_headers_for_user(provider)
    r = await client.get(f"{settings.API_V1_STR}/attendance/", headers=headers)
    assert r.status_code == 422


async def test_walkin_attendance_by_display_name(client: AsyncClient, db: AsyncSession) -> None:
    provider = await create_random_app_user(db, role=UserRole.PROVIDER)
    headers = get_token_headers_for_user(provider)
    encounter_id = _create_encounter()
    r = await client.post(
        f"{settings.API_V1_STR}/attendance/",
        headers=headers,
        json={"display_name": "Samsung 17", "encounter_id": encounter_id},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["attended"] is True
    assert body["patient_fhir_ref"].startswith("Patient/")


async def test_walkin_no_patient_id_no_name_422(client: AsyncClient, db: AsyncSession) -> None:
    provider = await create_random_app_user(db, role=UserRole.PROVIDER)
    headers = get_token_headers_for_user(provider)
    encounter_id = _create_encounter()
    r = await client.post(
        f"{settings.API_V1_STR}/attendance/",
        headers=headers,
        json={"encounter_id": encounter_id},
    )
    assert r.status_code == 422
