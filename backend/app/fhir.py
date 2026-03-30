from typing import Any

from fastapi import HTTPException
from fhir.resources.R4B.consent import Consent
from fhir.resources.R4B.resource import Resource

from app import models
from app.core.client import HttpxClient

FHIR_HEADERS = {"Content-Type": "application/fhir+json"}

CONSENT_SYSTEM = "http://compassionateveterans.org/fhir/CodeSystem/consent-type"
SCOPE_SYSTEM = "http://terminology.hl7.org/CodeSystem/consentscope"

CONSENT_CONFIG: dict[models.ConsentType, dict[str, str]] = {
    models.ConsentType.THERAPY_PARTICIPATION: {
        "scope": "treatment",
        "category_code": "therapy-participation",
        "display": "Therapy Participation",
    },
    models.ConsentType.LOCATION_SHARING: {
        "scope": "patient-privacy",
        "category_code": "location-sharing",
        "display": "Location Sharing",
    },
    models.ConsentType.RECORDING_AI: {
        "scope": "patient-privacy",
        "category_code": "recording-ai",
        "display": "Recording & AI Processing",
    },
    models.ConsentType.MMJ_MANAGEMENT: {
        "scope": "patient-privacy",
        "category_code": "mmj-management",
        "display": "MMJ Card Management",
    },
}


def build_consent(fhir_ref: str, consent_type: models.ConsentType, expires_at: str | None = None) -> Consent:
    cfg = CONSENT_CONFIG[consent_type]
    data: dict[str, Any] = {
        "status": "active",
        "scope": {"coding": [{"system": SCOPE_SYSTEM, "code": cfg["scope"]}]},
        "category": [{"coding": [{"system": CONSENT_SYSTEM, "code": cfg["category_code"], "display": cfg["display"]}]}],
        "patient": {"reference": fhir_ref},
    }
    if expires_at:
        data["provision"] = {"type": "permit", "period": {"end": expires_at}}
    return Consent.model_validate(data)


class Client:
    def __init__(self, http: HttpxClient, base_url: str) -> None:
        self._http = http
        self._base_url = base_url

    async def close(self) -> None:
        await self._http.close()

    async def read[R: Resource](self, resource_type: type[R], resource_id: str) -> R:
        r = await self._http.get(f"{self._base_url}/{resource_type.__resource_type__}/{resource_id}")
        r.raise_for_status()
        return resource_type.model_validate(r.json())

    async def create[R: Resource](self, resource: R) -> R:
        r = await self._http.post(
            f"{self._base_url}/{resource.__class__.__resource_type__}",
            content=resource.model_dump_json(exclude_unset=True),
            headers=FHIR_HEADERS,
        )
        r.raise_for_status()
        return resource.__class__.model_validate(r.json())

    async def update[R: Resource](self, resource: R) -> R:
        r = await self._http.put(
            f"{self._base_url}/{resource.__class__.__resource_type__}/{resource.id}",
            content=resource.model_dump_json(exclude_unset=True),
            headers=FHIR_HEADERS,
        )
        r.raise_for_status()
        return resource.__class__.model_validate(r.json())

    async def search[R: Resource](self, resource_type: type[R], params: dict[str, str] | None = None) -> list[R]:
        r = await self._http.get(
            f"{self._base_url}/{resource_type.__resource_type__}",
            params=params,
        )
        r.raise_for_status()
        bundle = r.json()
        if not bundle.get("entry"):
            return []
        return [resource_type.model_validate(e["resource"]) for e in bundle["entry"]]

    async def check_consent(self, fhir_ref: str, consent_type: models.ConsentType) -> bool:
        cfg = CONSENT_CONFIG[consent_type]
        patient_id = fhir_ref.split("/")[-1]
        results = await self.search(
            Consent,
            params={
                "patient": f"Patient/{patient_id}",
                "category": f"{CONSENT_SYSTEM}|{cfg['category_code']}",
                "status": "active",
            },
        )
        return len(results) > 0

    async def require_consent(self, fhir_ref: str, consent_type: models.ConsentType) -> None:
        if not await self.check_consent(fhir_ref, consent_type):
            raise HTTPException(status_code=404)
