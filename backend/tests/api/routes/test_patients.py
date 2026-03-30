from typing import Any

from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.models import AppUser, UserRole
from tests.utils.user import create_random_app_user, get_token_headers_for_user


async def _enroll(
    client: AsyncClient, headers: dict[str, str], display_name: str = "Test Patient", phone: str = "+15105550001"
) -> dict[str, Any]:
    r = await client.post(
        f"{settings.API_V1_STR}/patients/",
        headers=headers,
        json={"display_name": display_name, "phone": phone},
    )
    resp: dict[str, Any] = r.json()
    return resp


async def test_enroll_patient_as_provider(client: AsyncClient, db: AsyncSession) -> None:
    provider = await create_random_app_user(db, role=UserRole.PROVIDER)
    headers = get_token_headers_for_user(provider)
    r = await client.post(
        f"{settings.API_V1_STR}/patients/",
        headers=headers,
        json={"display_name": "Jane Doe", "phone": "+15105550001"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["display_name"] == "Jane Doe"
    assert body["fhir_ref"].startswith("Patient/")
    assert body["role"] == "PATIENT"


async def test_enroll_patient_as_patient_forbidden(client: AsyncClient, db: AsyncSession) -> None:
    patient = await create_random_app_user(db, role=UserRole.PATIENT)
    headers = get_token_headers_for_user(patient)
    r = await client.post(
        f"{settings.API_V1_STR}/patients/",
        headers=headers,
        json={"display_name": "Should Fail", "phone": "+15105550002"},
    )
    assert r.status_code == 403


async def test_enroll_patient_missing_phone(client: AsyncClient, db: AsyncSession) -> None:
    provider = await create_random_app_user(db, role=UserRole.PROVIDER)
    headers = get_token_headers_for_user(provider)
    r = await client.post(
        f"{settings.API_V1_STR}/patients/",
        headers=headers,
        json={"display_name": "No Phone"},
    )
    assert r.status_code == 422


async def test_list_patients_as_provider(client: AsyncClient, db: AsyncSession) -> None:
    provider = await create_random_app_user(db, role=UserRole.PROVIDER)
    headers = get_token_headers_for_user(provider)
    await _enroll(client, headers, display_name="List Test", phone="+15105550003")
    r = await client.get(f"{settings.API_V1_STR}/patients/", headers=headers)
    assert r.status_code == 200
    assert isinstance(r.json(), list)
    assert len(r.json()) >= 1


async def test_get_patient_as_provider(client: AsyncClient, db: AsyncSession) -> None:
    provider = await create_random_app_user(db, role=UserRole.PROVIDER)
    headers = get_token_headers_for_user(provider)
    enrolled = await _enroll(client, headers, display_name="Get Test", phone="+15105550004")
    r = await client.get(f"{settings.API_V1_STR}/patients/{enrolled['id']}", headers=headers)
    assert r.status_code == 200
    assert r.json()["id"] == enrolled["id"]


async def test_get_patient_as_own_patient(client: AsyncClient, db: AsyncSession) -> None:
    provider = await create_random_app_user(db, role=UserRole.PROVIDER)
    provider_headers = get_token_headers_for_user(provider)
    enrolled = await _enroll(client, provider_headers, display_name="Self Access", phone="+15105550005")
    patient_user = await db.get(AppUser, enrolled["id"])
    assert patient_user is not None
    patient_headers = get_token_headers_for_user(patient_user)
    r = await client.get(f"{settings.API_V1_STR}/patients/{enrolled['id']}", headers=patient_headers)
    assert r.status_code == 200


async def test_get_patient_as_other_patient_forbidden(client: AsyncClient, db: AsyncSession) -> None:
    provider = await create_random_app_user(db, role=UserRole.PROVIDER)
    provider_headers = get_token_headers_for_user(provider)
    enrolled = await _enroll(client, provider_headers, display_name="Other Access", phone="+15105550006")
    other_patient = await create_random_app_user(db, role=UserRole.PATIENT)
    other_headers = get_token_headers_for_user(other_patient)
    r = await client.get(f"{settings.API_V1_STR}/patients/{enrolled['id']}", headers=other_headers)
    assert r.status_code == 403


async def test_get_patient_not_found(client: AsyncClient, db: AsyncSession) -> None:
    provider = await create_random_app_user(db, role=UserRole.PROVIDER)
    headers = get_token_headers_for_user(provider)
    r = await client.get(f"{settings.API_V1_STR}/patients/00000000-0000-0000-0000-000000000000", headers=headers)
    assert r.status_code == 404


async def test_list_patients_as_cannabis_admin_only_mmj(client: AsyncClient, db: AsyncSession) -> None:
    provider = await create_random_app_user(db, role=UserRole.PROVIDER)
    provider_headers = get_token_headers_for_user(provider)
    p1 = await _enroll(client, provider_headers, "MMJ Patient", "+15105554001")
    p2 = await _enroll(client, provider_headers, "No MMJ Patient", "+15105554002")
    await client.post(
        f"{settings.API_V1_STR}/patients/{p1['id']}/consents/",
        headers=provider_headers,
        json={"consent_type": "mmj_management"},
    )
    admin = await create_random_app_user(db, role=UserRole.ADMIN_CANNABIS)
    admin_headers = get_token_headers_for_user(admin)
    r = await client.get(f"{settings.API_V1_STR}/patients/", headers=admin_headers)
    assert r.status_code == 200
    ids = {p["id"] for p in r.json()}
    assert p1["id"] in ids
    assert p2["id"] not in ids


async def test_list_patients_as_cannabis_admin_no_mmj_empty(client: AsyncClient, db: AsyncSession) -> None:
    admin = await create_random_app_user(db, role=UserRole.ADMIN_CANNABIS)
    admin_headers = get_token_headers_for_user(admin)
    provider = await create_random_app_user(db, role=UserRole.PROVIDER)
    provider_headers = get_token_headers_for_user(provider)
    await _enroll(client, provider_headers, "No MMJ At All", "+15105554003")
    r = await client.get(f"{settings.API_V1_STR}/patients/", headers=admin_headers)
    assert r.status_code == 200
    # May contain patients from other tests with mmj consent, but the new one should not be there
    names = {p["display_name"] for p in r.json()}
    assert "No MMJ At All" not in names


async def test_get_patient_as_cannabis_admin_with_mmj(client: AsyncClient, db: AsyncSession) -> None:
    provider = await create_random_app_user(db, role=UserRole.PROVIDER)
    provider_headers = get_token_headers_for_user(provider)
    enrolled = await _enroll(client, provider_headers, "MMJ Get", "+15105554004")
    await client.post(
        f"{settings.API_V1_STR}/patients/{enrolled['id']}/consents/",
        headers=provider_headers,
        json={"consent_type": "mmj_management"},
    )
    admin = await create_random_app_user(db, role=UserRole.ADMIN_CANNABIS)
    admin_headers = get_token_headers_for_user(admin)
    r = await client.get(f"{settings.API_V1_STR}/patients/{enrolled['id']}", headers=admin_headers)
    assert r.status_code == 200


async def test_get_patient_as_cannabis_admin_without_mmj_404(client: AsyncClient, db: AsyncSession) -> None:
    provider = await create_random_app_user(db, role=UserRole.PROVIDER)
    provider_headers = get_token_headers_for_user(provider)
    enrolled = await _enroll(client, provider_headers, "No MMJ Get", "+15105554005")
    admin = await create_random_app_user(db, role=UserRole.ADMIN_CANNABIS)
    admin_headers = get_token_headers_for_user(admin)
    r = await client.get(f"{settings.API_V1_STR}/patients/{enrolled['id']}", headers=admin_headers)
    assert r.status_code == 404


async def test_get_mmj_info_as_cannabis_admin(client: AsyncClient, db: AsyncSession) -> None:
    provider = await create_random_app_user(db, role=UserRole.PROVIDER)
    provider_headers = get_token_headers_for_user(provider)
    enrolled = await _enroll(client, provider_headers, "MMJ Info", "+15105554006")
    await client.post(
        f"{settings.API_V1_STR}/patients/{enrolled['id']}/consents/",
        headers=provider_headers,
        json={"consent_type": "mmj_management", "expires_at": "2027-12-31T00:00:00Z"},
    )
    admin = await create_random_app_user(db, role=UserRole.ADMIN_CANNABIS)
    admin_headers = get_token_headers_for_user(admin)
    r = await client.get(f"{settings.API_V1_STR}/patients/{enrolled['id']}/mmj", headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["display_name"] == "MMJ Info"
    assert body["phone"] == "+15105554006"
    assert body["consent_expires"] is not None


async def test_get_mmj_info_without_consent_404(client: AsyncClient, db: AsyncSession) -> None:
    provider = await create_random_app_user(db, role=UserRole.PROVIDER)
    provider_headers = get_token_headers_for_user(provider)
    enrolled = await _enroll(client, provider_headers, "No MMJ Info", "+15105554007")
    admin = await create_random_app_user(db, role=UserRole.ADMIN_CANNABIS)
    admin_headers = get_token_headers_for_user(admin)
    r = await client.get(f"{settings.API_V1_STR}/patients/{enrolled['id']}/mmj", headers=admin_headers)
    assert r.status_code == 404


async def test_get_mmj_info_as_patient_403(client: AsyncClient, db: AsyncSession) -> None:
    provider = await create_random_app_user(db, role=UserRole.PROVIDER)
    provider_headers = get_token_headers_for_user(provider)
    enrolled = await _enroll(client, provider_headers, "MMJ Forbidden", "+15105554008")
    await client.post(
        f"{settings.API_V1_STR}/patients/{enrolled['id']}/consents/",
        headers=provider_headers,
        json={"consent_type": "mmj_management"},
    )
    patient = await create_random_app_user(db, role=UserRole.PATIENT)
    patient_headers = get_token_headers_for_user(patient)
    r = await client.get(f"{settings.API_V1_STR}/patients/{enrolled['id']}/mmj", headers=patient_headers)
    assert r.status_code == 403
