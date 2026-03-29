import httpx
from fhir.resources.R4B.patient import Patient

from app.core.config import settings

FHIR_BASE = settings.FHIR_BASE_URL


def _post_patient(family: str, given: str) -> Patient:
    p = Patient(name=[{"use": "official", "family": family, "given": [given]}])
    r = httpx.post(
        f"{FHIR_BASE}/Patient",
        content=p.model_dump_json(exclude_unset=True),
        headers={"Content-Type": "application/fhir+json"},
    )
    r.raise_for_status()
    return Patient.model_validate(r.json())


def test_create_patient() -> None:
    created = _post_patient("CreateTst", "Jane")
    assert created.id is not None
    assert created.name[0].family == "CreateTst"


def test_read_patient() -> None:
    created = _post_patient("ReadTst", "Bob")
    r = httpx.get(f"{FHIR_BASE}/Patient/{created.id}")
    assert r.status_code == 200
    fetched = Patient.model_validate(r.json())
    assert fetched.name[0].family == "ReadTst"


def test_update_patient() -> None:
    created = _post_patient("Before", "Sue")
    created.name[0].family = "After"
    r = httpx.put(
        f"{FHIR_BASE}/Patient/{created.id}",
        content=created.model_dump_json(exclude_unset=True),
        headers={"Content-Type": "application/fhir+json"},
    )
    assert r.status_code == 200
    updated = Patient.model_validate(r.json())
    assert updated.name[0].family == "After"


def test_search_patients() -> None:
    _post_patient("SearchTst", "Pat")
    r = httpx.get(f"{FHIR_BASE}/Patient", params={"family": "SearchTst"})
    assert r.status_code == 200
    bundle = r.json()
    assert bundle.get("entry") is not None
    patients = [Patient.model_validate(e["resource"]) for e in bundle["entry"]]
    assert len(patients) >= 1


def test_read_not_found() -> None:
    r = httpx.get(f"{FHIR_BASE}/Patient/does-not-exist-999")
    assert r.status_code == 404
