import uuid
from datetime import UTC, datetime
from enum import Enum

from sqlalchemy import Column, DateTime, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, Relationship, SQLModel


def utc_now() -> datetime:
    return datetime.now(UTC)


class UserRole(str, Enum):
    PATIENT = "PATIENT"
    ADMIN_CANNABIS = "ADMIN_CANNABIS"
    PROVIDER = "PROVIDER"
    SUPER_USER = "SUPER_USER"


class AuthProvider(str, Enum):
    GOOGLE = "google"
    APPLE = "apple"
    SMS_OTP = "sms_otp"


class PipelineStage(str, Enum):
    RAW = "raw"
    FILTERED = "filtered"
    REDACTED = "redacted"
    NOTE_GENERATED = "note_generated"
    COMPLETE = "complete"
    FAILED = "failed"


class ZoomSessionStatus(str, Enum):
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class AppUserBase(SQLModel):
    fhir_ref: str | None = None
    role: UserRole
    display_name: str | None = None


class AppUser(AppUserBase, table=True):
    __tablename__ = "app_users"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_type=DateTime(timezone=True),  # type: ignore[call-overload]
    )
    last_login_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore[call-overload]
    )
    auth_identities: list["AuthIdentity"] = Relationship(back_populates="user", cascade_delete=True)


class AppUserCreate(AppUserBase):
    pass


class AppUserUpdate(SQLModel):
    fhir_ref: str | None = None
    role: UserRole | None = None
    display_name: str | None = None
    last_login_at: datetime | None = None


class AppUserPublic(AppUserBase):
    id: uuid.UUID
    created_at: datetime


class AuthIdentityBase(SQLModel):
    provider: AuthProvider
    external_id: str


class AuthIdentity(AuthIdentityBase, table=True):
    __tablename__ = "auth_identities"
    __table_args__ = (UniqueConstraint("provider", "external_id"),)
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="app_users.id", nullable=False, ondelete="CASCADE")
    verified_at: datetime = Field(
        default_factory=utc_now,
        sa_type=DateTime(timezone=True),  # type: ignore[call-overload]
    )
    user: AppUser | None = Relationship(back_populates="auth_identities")


class TextBlastBase(SQLModel):
    message: str
    recipient_count: int | None = None


class TextBlast(TextBlastBase, table=True):
    __tablename__ = "text_blasts"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    sent_by: uuid.UUID | None = Field(default=None, foreign_key="app_users.id", ondelete="SET NULL")
    sent_at: datetime = Field(
        default_factory=utc_now,
        sa_type=DateTime(timezone=True),  # type: ignore[call-overload]
    )
    twilio_response: dict | None = Field(default=None, sa_column=Column(JSONB))


class ZoomSessionBase(SQLModel):
    encounter_id: str
    zoom_meeting_id: str
    status: ZoomSessionStatus


class ZoomSession(ZoomSessionBase, table=True):
    __tablename__ = "zoom_sessions"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    started_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore[call-overload]
    )
    ended_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore[call-overload]
    )


class PipelineRunBase(SQLModel):
    encounter_id: str
    stage: PipelineStage


class PipelineRun(PipelineRunBase, table=True):
    __tablename__ = "pipeline_runs"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    task_id: str | None = None
    started_at: datetime = Field(
        default_factory=utc_now,
        sa_type=DateTime(timezone=True),  # type: ignore[call-overload]
    )
    completed_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore[call-overload]
    )
    error: str | None = None
    community_turns_discarded: int = 0
    patient_turns_kept: int = 0


class Message(SQLModel):
    message: str


class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


class TokenPayload(SQLModel):
    sub: str | None = None
    role: str | None = None
    fhir_ref: str | None = None
