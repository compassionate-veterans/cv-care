import uuid

from fastapi import APIRouter, HTTPException
from fhir.resources.R4B.humanname import HumanName
from fhir.resources.R4B.observation import Observation
from fhir.resources.R4B.patient import Patient

from app import models
from app.api import deps
from app.api.routes.patients import _require_fhir_ref

router = APIRouter(prefix="/attendance", tags=["attendance"])

ATTENDANCE_CODE_SYSTEM = "http://compassionateveterans.org/fhir/CodeSystem/custom"
ATTENDANCE_CODE = "group-therapy-attendance"


def _build_observation(patient_fhir_ref: str, encounter_id: str, attended: bool = True) -> Observation:
    return Observation.model_validate(
        {
            "status": "final",
            "code": {"coding": [{"system": ATTENDANCE_CODE_SYSTEM, "code": ATTENDANCE_CODE}]},
            "subject": {"reference": patient_fhir_ref},
            "encounter": {"reference": f"Encounter/{encounter_id}"},
            "valueBoolean": attended,
        }
    )


def _to_public(obs: Observation) -> models.AttendancePublic:
    return models.AttendancePublic(
        id=obs.id or "",
        patient_fhir_ref=obs.subject.reference if obs.subject else "",
        encounter_id=obs.encounter.reference.split("/")[-1] if obs.encounter and obs.encounter.reference else "",
        attended=obs.valueBoolean if obs.valueBoolean is not None else False,
        status=obs.status or "",
        effective_date_time=obs.effectiveDateTime,
    )


async def _resolve_fhir_ref(
    session: deps.SessionDep,
    fhir_client: deps.FHIRDep,
    body: models.AttendanceCreateRequest,
) -> str:
    if body.patient_id:
        patient = await session.get(models.AppUser, body.patient_id)
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")
        return _require_fhir_ref(patient)
    if body.display_name:
        fhir_patient = Patient(name=[HumanName(use="usual", text=body.display_name)])
        created = await fhir_client.create(fhir_patient)
        return f"Patient/{created.id}"
    raise HTTPException(status_code=422, detail="Provide patient_id or display_name")


@router.post("/", response_model=models.AttendancePublic, status_code=201)
async def mark_attendance(
    session: deps.SessionDep,
    _: deps.RequireProvider,
    fhir_client: deps.FHIRDep,
    body: models.AttendanceCreateRequest,
) -> models.AttendancePublic:
    fhir_ref = await _resolve_fhir_ref(session, fhir_client, body)
    obs = _build_observation(fhir_ref, body.encounter_id, body.attended)
    created = await fhir_client.create(obs)
    return _to_public(created)


@router.put("/{observation_id}/undo", response_model=models.AttendancePublic)
async def undo_attendance(
    _: deps.RequireProvider,
    fhir_client: deps.FHIRDep,
    observation_id: str,
) -> models.AttendancePublic:
    obs = await fhir_client.read(Observation, observation_id)
    obs.status = "entered-in-error"
    updated = await fhir_client.update(obs)
    return _to_public(updated)


@router.get("/", response_model=list[models.AttendancePublic])
async def list_attendance(
    session: deps.SessionDep,
    _: deps.RequireProvider,
    fhir_client: deps.FHIRDep,
    patient_id: uuid.UUID | None = None,
    encounter_id: str | None = None,
) -> list[models.AttendancePublic]:
    if not patient_id and not encounter_id:
        raise HTTPException(status_code=422, detail="Provide patient_id or encounter_id")
    params: dict[str, str] = {"code": f"{ATTENDANCE_CODE_SYSTEM}|{ATTENDANCE_CODE}", "status": "final"}
    if encounter_id:
        params["encounter"] = f"Encounter/{encounter_id}"
    if patient_id:
        patient = await session.get(models.AppUser, patient_id)
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")
        fhir_ref = _require_fhir_ref(patient)
        params["subject"] = fhir_ref
    results = await fhir_client.search(Observation, params=params)
    return [_to_public(obs) for obs in results]
