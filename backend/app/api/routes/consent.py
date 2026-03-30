import uuid

from fastapi import APIRouter, HTTPException
from fhir.resources.R4B.consent import Consent

from app import fhir, models
from app.api import deps
from app.api.routes.patients import _resolve_patient

router = APIRouter(prefix="/patients/{patient_id}/consents", tags=["consent"])


@router.post("/", response_model=models.ConsentPublic, status_code=201)
async def create_consent(
    session: deps.SessionDep,
    current_user: deps.CurrentUser,
    fhir_client: deps.FHIRDep,
    patient_id: uuid.UUID,
    body: models.ConsentCreateRequest,
) -> models.ConsentPublic:
    patient = await _resolve_patient(current_user, session, patient_id)
    if not patient.fhir_ref:
        raise HTTPException(status_code=404, detail="Patient not enrolled in FHIR")
    expires_at = body.expires_at.isoformat() if body.expires_at else None
    consent = fhir.build_consent(patient.fhir_ref, body.consent_type, expires_at=expires_at)
    created = await fhir_client.create(consent)
    return _to_public(created, body.consent_type)


@router.get("/", response_model=list[models.ConsentPublic])
async def list_consents(
    session: deps.SessionDep,
    current_user: deps.CurrentUser,
    fhir_client: deps.FHIRDep,
    patient_id: uuid.UUID,
) -> list[models.ConsentPublic]:
    patient = await _resolve_patient(current_user, session, patient_id)
    if not patient.fhir_ref:
        raise HTTPException(status_code=404, detail="Patient not enrolled in FHIR")
    patient_fhir_id = patient.fhir_ref.split("/")[-1]
    results = await fhir_client.search(Consent, params={"patient": patient_fhir_id})
    return [_to_public_from_fhir(c) for c in results]


@router.post("/{consent_id}/revoke", response_model=models.ConsentPublic)
async def revoke_consent(
    session: deps.SessionDep,
    current_user: deps.CurrentUser,
    fhir_client: deps.FHIRDep,
    patient_id: uuid.UUID,
    consent_id: str,
) -> models.ConsentPublic:
    patient = await _resolve_patient(current_user, session, patient_id)
    if not patient.fhir_ref:
        raise HTTPException(status_code=404, detail="Patient not enrolled in FHIR")
    consent = await fhir_client.read(Consent, consent_id)
    if consent.patient is None or consent.patient.reference != patient.fhir_ref:
        raise HTTPException(status_code=404, detail="Consent not found for this patient")
    consent.status = "inactive"
    updated = await fhir_client.update(consent)
    return _to_public_from_fhir(updated)


def _to_public(consent: Consent, consent_type: models.ConsentType) -> models.ConsentPublic:
    cfg = fhir.CONSENT_CONFIG[consent_type]
    expires_at = None
    if consent.provision and consent.provision.period and consent.provision.period.end:
        expires_at = consent.provision.period.end
    return models.ConsentPublic(
        id=consent.id or "",
        consent_type=cfg["category_code"],
        status=consent.status or "",
        date_time=consent.dateTime,
        expires_at=expires_at,
    )


def _to_public_from_fhir(consent: Consent) -> models.ConsentPublic:
    category_code = ""
    if consent.category and consent.category[0].coding:
        category_code = consent.category[0].coding[0].code or ""
    expires_at = None
    if consent.provision and consent.provision.period and consent.provision.period.end:
        expires_at = consent.provision.period.end
    return models.ConsentPublic(
        id=consent.id or "",
        consent_type=category_code,
        status=consent.status or "",
        date_time=consent.dateTime,
        expires_at=expires_at,
    )
