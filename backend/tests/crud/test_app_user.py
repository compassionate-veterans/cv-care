import uuid

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.models import (
    AppUser,
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


async def test_create_app_user_patient(db: AsyncSession) -> None:
    user_in = AppUserCreate(role=UserRole.PATIENT, display_name="Jane Doe")
    user = await crud.create_app_user(session=db, user_in=user_in)
    assert user.role == UserRole.PATIENT
    assert user.display_name == "Jane Doe"
    assert user.fhir_ref is None
    assert user.id is not None
    assert user.created_at is not None


async def test_create_app_user_provider(db: AsyncSession) -> None:
    user_in = AppUserCreate(
        role=UserRole.PROVIDER,
        display_name="Dr. Jones",
        fhir_ref="Practitioner/abc-123",
    )
    user = await crud.create_app_user(session=db, user_in=user_in)
    assert user.role == UserRole.PROVIDER
    assert user.fhir_ref == "Practitioner/abc-123"


async def test_create_app_user_admin_cannabis(db: AsyncSession) -> None:
    user_in = AppUserCreate(role=UserRole.ADMIN_CANNABIS, display_name="Cannabis Admin")
    user = await crud.create_app_user(session=db, user_in=user_in)
    assert user.role == UserRole.ADMIN_CANNABIS


async def test_get_app_user(db: AsyncSession) -> None:
    user_in = AppUserCreate(role=UserRole.PATIENT, display_name="Lookup Test")
    created = await crud.create_app_user(session=db, user_in=user_in)
    found = await crud.get_app_user(session=db, user_id=created.id)
    assert found is not None
    assert found.id == created.id


async def test_update_app_user(db: AsyncSession) -> None:
    user_in = AppUserCreate(role=UserRole.PATIENT, display_name="Before Update")
    user = await crud.create_app_user(session=db, user_in=user_in)
    update_in = AppUserUpdate(display_name="After Update", fhir_ref="Patient/xyz")
    updated = await crud.update_app_user(session=db, db_user=user, user_in=update_in)
    assert updated.display_name == "After Update"
    assert updated.fhir_ref == "Patient/xyz"


async def test_create_auth_identity(db: AsyncSession) -> None:
    user_in = AppUserCreate(role=UserRole.PATIENT, display_name="Auth Test")
    user = await crud.create_app_user(session=db, user_in=user_in)
    identity = await crud.create_auth_identity(
        session=db,
        user_id=user.id,
        provider=AuthProvider.GOOGLE,
        external_id=f"google-sub-{uuid.uuid4().hex[:8]}",
    )
    assert identity.provider == AuthProvider.GOOGLE
    assert identity.external_id.startswith("google-sub-")
    assert identity.user_id == user.id
    assert identity.verified_at is not None


async def test_auth_identity_unique_constraint(engine: AsyncEngine) -> None:
    phone = f"+1510555{uuid.uuid4().hex[:4]}"
    async with AsyncSession(engine, expire_on_commit=False) as s:
        user1 = await crud.create_app_user(
            session=s,
            user_in=AppUserCreate(role=UserRole.PATIENT, display_name="Uniq 1"),
        )
        user2 = await crud.create_app_user(
            session=s,
            user_in=AppUserCreate(role=UserRole.PATIENT, display_name="Uniq 2"),
        )
        await crud.create_auth_identity(session=s, user_id=user1.id, provider=AuthProvider.SMS_OTP, external_id=phone)
    async with AsyncSession(engine) as s2:
        with pytest.raises(IntegrityError):
            await crud.create_auth_identity(
                session=s2, user_id=user2.id, provider=AuthProvider.SMS_OTP, external_id=phone
            )
        await s2.rollback()


async def test_get_user_by_identity(db: AsyncSession) -> None:
    user = await crud.create_app_user(
        session=db,
        user_in=AppUserCreate(role=UserRole.PATIENT, display_name="Lookup By Identity"),
    )
    identity = await crud.create_auth_identity(
        session=db,
        user_id=user.id,
        provider=AuthProvider.APPLE,
        external_id=f"apple-sub-{uuid.uuid4().hex[:8]}",
    )
    found = await crud.get_user_by_identity(session=db, provider=AuthProvider.APPLE, external_id=identity.external_id)
    assert found is not None
    assert found.id == user.id


async def test_get_user_by_identity_not_found(db: AsyncSession) -> None:
    found = await crud.get_user_by_identity(session=db, provider=AuthProvider.GOOGLE, external_id="does-not-exist")
    assert found is None


async def test_touch_last_login(db: AsyncSession) -> None:
    user = await crud.create_app_user(
        session=db,
        user_in=AppUserCreate(role=UserRole.PATIENT, display_name="Login Test"),
    )
    assert user.last_login_at is None
    await crud.touch_last_login(session=db, user=user)
    await db.refresh(user)
    assert user.last_login_at is not None


async def test_cascade_delete_auth_identities(db: AsyncSession) -> None:
    user = await crud.create_app_user(
        session=db,
        user_in=AppUserCreate(role=UserRole.PATIENT, display_name="Cascade Test"),
    )
    await crud.create_auth_identity(
        session=db,
        user_id=user.id,
        provider=AuthProvider.GOOGLE,
        external_id=f"cascade-{uuid.uuid4().hex[:8]}",
    )
    user_id = user.id
    from sqlmodel import delete

    await db.exec(delete(AppUser).where(AppUser.id == user_id))  # type: ignore[call-overload]
    await db.commit()
    result = await db.exec(select(AuthIdentity).where(AuthIdentity.user_id == user_id))
    orphans = result.all()
    assert len(orphans) == 0


async def test_create_zoom_session(db: AsyncSession) -> None:
    zs = ZoomSession(
        encounter_id="enc-001",
        zoom_meeting_id="87654321098",
        status=ZoomSessionStatus.SCHEDULED,
    )
    db.add(zs)
    await db.commit()
    await db.refresh(zs)
    assert zs.id is not None
    assert zs.status == ZoomSessionStatus.SCHEDULED


async def test_create_pipeline_run(db: AsyncSession) -> None:
    pr = PipelineRun(encounter_id="enc-001", stage=PipelineStage.RAW)
    db.add(pr)
    await db.commit()
    await db.refresh(pr)
    assert pr.id is not None
    assert pr.stage == PipelineStage.RAW
    assert pr.community_turns_discarded == 0


async def test_create_text_blast(db: AsyncSession) -> None:
    user = await crud.create_app_user(
        session=db,
        user_in=AppUserCreate(role=UserRole.PROVIDER, display_name="Blast Sender"),
    )
    tb = TextBlast(sent_by=user.id, message="Session at 2pm today", recipient_count=12)
    db.add(tb)
    await db.commit()
    await db.refresh(tb)
    assert tb.id is not None
    assert tb.message == "Session at 2pm today"
    assert tb.recipient_count == 12
