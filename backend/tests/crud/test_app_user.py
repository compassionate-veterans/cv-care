import uuid

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app import crud
from app.models import (
    AppUserCreate,
    AppUserUpdate,
    AuthIdentity,
    AuthProvider,
    PipelineRun,
    PipelineStage,
    TextBlast,
    UserRole,
    ZoomSession,
    ZoomSessionStatus,
)


def test_create_app_user_patient(db: Session) -> None:
    user_in = AppUserCreate(role=UserRole.PATIENT, display_name="Jane Doe")
    user = crud.create_app_user(session=db, user_in=user_in)
    assert user.role == UserRole.PATIENT
    assert user.display_name == "Jane Doe"
    assert user.fhir_ref is None
    assert user.id is not None
    assert user.created_at is not None


def test_create_app_user_provider(db: Session) -> None:
    user_in = AppUserCreate(
        role=UserRole.PROVIDER,
        display_name="Dr. Jones",
        fhir_ref="Practitioner/abc-123",
    )
    user = crud.create_app_user(session=db, user_in=user_in)
    assert user.role == UserRole.PROVIDER
    assert user.fhir_ref == "Practitioner/abc-123"


def test_create_app_user_admin_cannabis(db: Session) -> None:
    user_in = AppUserCreate(role=UserRole.ADMIN_CANNABIS, display_name="Cannabis Admin")
    user = crud.create_app_user(session=db, user_in=user_in)
    assert user.role == UserRole.ADMIN_CANNABIS


def test_get_app_user(db: Session) -> None:
    user_in = AppUserCreate(role=UserRole.PATIENT, display_name="Lookup Test")
    created = crud.create_app_user(session=db, user_in=user_in)
    found = crud.get_app_user(session=db, user_id=created.id)
    assert found is not None
    assert found.id == created.id


def test_update_app_user(db: Session) -> None:
    user_in = AppUserCreate(role=UserRole.PATIENT, display_name="Before Update")
    user = crud.create_app_user(session=db, user_in=user_in)
    update_in = AppUserUpdate(display_name="After Update", fhir_ref="Patient/xyz")
    updated = crud.update_app_user(session=db, db_user=user, user_in=update_in)
    assert updated.display_name == "After Update"
    assert updated.fhir_ref == "Patient/xyz"


def test_create_auth_identity(db: Session) -> None:
    user_in = AppUserCreate(role=UserRole.PATIENT, display_name="Auth Test")
    user = crud.create_app_user(session=db, user_in=user_in)
    identity = crud.create_auth_identity(
        session=db,
        user_id=user.id,
        provider=AuthProvider.GOOGLE,
        external_id="google-sub-123",
    )
    assert identity.provider == AuthProvider.GOOGLE
    assert identity.external_id == "google-sub-123"
    assert identity.user_id == user.id
    assert identity.verified_at is not None


def test_auth_identity_unique_constraint(db: Session) -> None:
    user1 = crud.create_app_user(
        session=db,
        user_in=AppUserCreate(role=UserRole.PATIENT, display_name="User 1"),
    )
    user2 = crud.create_app_user(
        session=db,
        user_in=AppUserCreate(role=UserRole.PATIENT, display_name="User 2"),
    )
    crud.create_auth_identity(
        session=db,
        user_id=user1.id,
        provider=AuthProvider.SMS_OTP,
        external_id="+15105550001",
    )
    with pytest.raises(IntegrityError):
        crud.create_auth_identity(
            session=db,
            user_id=user2.id,
            provider=AuthProvider.SMS_OTP,
            external_id="+15105550001",
        )
    db.rollback()


def test_get_user_by_identity(db: Session) -> None:
    user = crud.create_app_user(
        session=db,
        user_in=AppUserCreate(role=UserRole.PATIENT, display_name="Lookup By Identity"),
    )
    crud.create_auth_identity(
        session=db,
        user_id=user.id,
        provider=AuthProvider.APPLE,
        external_id="apple-sub-456",
    )
    found = crud.get_user_by_identity(session=db, provider=AuthProvider.APPLE, external_id="apple-sub-456")
    assert found is not None
    assert found.id == user.id


def test_get_user_by_identity_not_found(db: Session) -> None:
    found = crud.get_user_by_identity(session=db, provider=AuthProvider.GOOGLE, external_id="does-not-exist")
    assert found is None


def test_touch_last_login(db: Session) -> None:
    user = crud.create_app_user(
        session=db,
        user_in=AppUserCreate(role=UserRole.PATIENT, display_name="Login Test"),
    )
    assert user.last_login_at is None
    crud.touch_last_login(session=db, user=user)
    db.refresh(user)
    assert user.last_login_at is not None


def test_cascade_delete_auth_identities(db: Session) -> None:
    user = crud.create_app_user(
        session=db,
        user_in=AppUserCreate(role=UserRole.PATIENT, display_name="Cascade Test"),
    )
    crud.create_auth_identity(
        session=db,
        user_id=user.id,
        provider=AuthProvider.GOOGLE,
        external_id=f"cascade-{uuid.uuid4().hex[:8]}",
    )
    user_id = user.id
    db.delete(user)
    db.commit()
    orphans = db.exec(select(AuthIdentity).where(AuthIdentity.user_id == user_id)).all()
    assert len(orphans) == 0


def test_create_zoom_session(db: Session) -> None:
    zs = ZoomSession(
        encounter_id="enc-001",
        zoom_meeting_id="87654321098",
        status=ZoomSessionStatus.SCHEDULED,
    )
    db.add(zs)
    db.commit()
    db.refresh(zs)
    assert zs.id is not None
    assert zs.status == ZoomSessionStatus.SCHEDULED


def test_create_pipeline_run(db: Session) -> None:
    pr = PipelineRun(encounter_id="enc-001", stage=PipelineStage.RAW)
    db.add(pr)
    db.commit()
    db.refresh(pr)
    assert pr.id is not None
    assert pr.stage == PipelineStage.RAW
    assert pr.community_turns_discarded == 0


def test_create_text_blast(db: Session) -> None:
    user = crud.create_app_user(
        session=db,
        user_in=AppUserCreate(role=UserRole.PROVIDER, display_name="Blast Sender"),
    )
    tb = TextBlast(sent_by=user.id, message="Session at 2pm today", recipient_count=12)
    db.add(tb)
    db.commit()
    db.refresh(tb)
    assert tb.id is not None
    assert tb.message == "Session at 2pm today"
    assert tb.recipient_count == 12
