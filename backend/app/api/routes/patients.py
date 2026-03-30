import uuid

from fastapi import APIRouter, HTTPException
from fhir.resources.R4B.contactpoint import ContactPoint
from fhir.resources.R4B.humanname import HumanName
from fhir.resources.R4B.patient import Patient
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud, fhir, models
from app.api import deps

router = APIRouter(prefix="/patients", tags=["patients"])


async def _resolve_patient(
    current_user: models.AppUser,
    session: AsyncSession,
    patient_id: uuid.UUID,
    fhir_client: fhir.Client | None = None,
) -> models.AppUser:
    patient = await session.get(models.AppUser, patient_id)
    if not patient or patient.role != models.UserRole.PATIENT:
        raise HTTPException(status_code=404, detail="Patient not found")
    if current_user.role in (models.UserRole.PROVIDER, models.UserRole.SUPER_USER):
        return patient
    if current_user.id == patient.id:
        return patient
    if current_user.role == models.UserRole.ADMIN_CANNABIS and fhir_client and patient.fhir_ref:
        if await fhir_client.check_consent(patient.fhir_ref, models.ConsentType.MMJ_MANAGEMENT):
            return patient
        raise HTTPException(status_code=404, detail="Patient not found")
    raise HTTPException(status_code=403, detail="Insufficient privileges")


def _require_fhir_ref(patient: models.AppUser) -> str:
    if not patient.fhir_ref:
        raise HTTPException(status_code=404, detail="Patient not enrolled in FHIR")
    return patient.fhir_ref


@router.post("/", response_model=models.PatientEnrollResponse, status_code=201)
async def enroll_patient(
    session: deps.SessionDep,
    _: deps.RequireProvider,
    fhir_client: deps.FHIRDep,
    body: models.PatientEnrollRequest,
) -> models.PatientEnrollResponse:
    app_user = await crud.create_app_user(
        session=session,
        user_in=models.AppUserCreate(role=models.UserRole.PATIENT, display_name=body.display_name),
    )
    fhir_patient = Patient(
        name=[HumanName(use="official", family=body.display_name)],
        telecom=[ContactPoint(system="phone", value=body.phone, use="mobile")],
    )
    created = await fhir_client.create(fhir_patient)
    fhir_ref = f"Patient/{created.id}"
    await crud.update_app_user(
        session=session,
        db_user=app_user,
        user_in=models.AppUserUpdate(fhir_ref=fhir_ref),
    )
    return models.PatientEnrollResponse(
        id=app_user.id,
        display_name=app_user.display_name,
        fhir_ref=fhir_ref,
        role=app_user.role,
        created_at=app_user.created_at,
    )


@router.get("/", response_model=list[models.PatientEnrollResponse])
async def list_patients(
    session: deps.SessionDep,
    current_user: deps.CurrentUser,
    fhir_client: deps.FHIRDep,
) -> list[models.PatientEnrollResponse]:
    if current_user.role not in (
        models.UserRole.PROVIDER,
        models.UserRole.SUPER_USER,
        models.UserRole.ADMIN_CANNABIS,
    ):
        raise HTTPException(status_code=403, detail="Insufficient privileges")

    result = await session.exec(
        select(models.AppUser).where(
            models.AppUser.role == models.UserRole.PATIENT,
            models.AppUser.fhir_ref.isnot(None),  # type: ignore[union-attr]
        )
    )
    patients = [p for p in result.all() if p.fhir_ref]

    if current_user.role == models.UserRole.ADMIN_CANNABIS:
        filtered = []
        for p in patients:
            assert p.fhir_ref
            if await fhir_client.check_consent(p.fhir_ref, models.ConsentType.MMJ_MANAGEMENT):
                filtered.append(p)
        patients = filtered

    return [
        models.PatientEnrollResponse(
            id=p.id,
            display_name=p.display_name,
            fhir_ref=p.fhir_ref,  # type: ignore[arg-type]
            role=p.role,
            created_at=p.created_at,
        )
        for p in patients
    ]


@router.get("/{patient_id}", response_model=models.PatientEnrollResponse)
async def get_patient(
    session: deps.SessionDep,
    current_user: deps.CurrentUser,
    fhir_client: deps.FHIRDep,
    patient_id: uuid.UUID,
) -> models.PatientEnrollResponse:
    patient = await _resolve_patient(current_user, session, patient_id, fhir_client)
    fhir_ref = _require_fhir_ref(patient)
    return models.PatientEnrollResponse(
        id=patient.id,
        display_name=patient.display_name,
        fhir_ref=fhir_ref,
        role=patient.role,
        created_at=patient.created_at,
    )


@router.get("/{patient_id}/clinical")
async def get_clinical(
    session: deps.SessionDep,
    current_user: deps.CurrentUser,
    fhir_client: deps.FHIRDep,
    patient_id: uuid.UUID,
) -> Patient:
    app_user = await _resolve_patient(current_user, session, patient_id, fhir_client)
    fhir_ref = _require_fhir_ref(app_user)
    await fhir_client.require_consent(fhir_ref, models.ConsentType.THERAPY_PARTICIPATION)
    return await fhir_client.read(Patient, fhir_ref.split("/")[-1])


@router.get("/{patient_id}/mmj", response_model=models.MMJInfoResponse)
async def get_mmj_info(
    session: deps.SessionDep,
    _: deps.RequireAdminCannabis,
    fhir_client: deps.FHIRDep,
    patient_id: uuid.UUID,
) -> models.MMJInfoResponse:
    patient = await session.get(models.AppUser, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    fhir_ref = _require_fhir_ref(patient)
    await fhir_client.require_consent(fhir_ref, models.ConsentType.MMJ_MANAGEMENT)
    fhir_patient = await fhir_client.read(Patient, fhir_ref.split("/")[-1])
    phone = None
    if fhir_patient.telecom:
        for t in fhir_patient.telecom:
            if t.system == "phone":
                phone = t.value
                break
    recompass_id = None
    if fhir_patient.identifier:
        for ident in fhir_patient.identifier:
            if ident.system and "re-compass" in ident.system:
                recompass_id = ident.value
                break
    from fhir.resources.R4B.consent import Consent

    consents = await fhir_client.search(Consent, params={"patient": fhir_ref.split("/")[-1], "status": "active"})
    consent_expires = None
    for c in consents:
        if c.category and c.category[0].coding and c.category[0].coding[0].code == "mmj-management":
            if c.provision and c.provision.period and c.provision.period.end:
                consent_expires = c.provision.period.end
            break
    return models.MMJInfoResponse(
        display_name=patient.display_name,
        phone=phone,
        recompass_patient_id=recompass_id,
        consent_expires=consent_expires,
    )
