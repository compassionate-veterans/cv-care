from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, delete, select

from app.core.db import engine, init_db
from app.core.security import create_access_token
from app.main import app
from app.models import (
    AppUser,
    AuthIdentity,
    PipelineRun,
    TextBlast,
    UserRole,
    ZoomSession,
)


@pytest.fixture(scope="session", autouse=True)
def db() -> Generator[Session]:
    with Session(engine) as session:
        init_db(session)
        yield session
        for model in [AuthIdentity, TextBlast, PipelineRun, ZoomSession, AppUser]:
            session.execute(delete(model))
        session.commit()


@pytest.fixture(scope="module")
def client() -> Generator[TestClient]:
    with TestClient(app) as c:
        yield c


def _make_token_headers(user: AppUser) -> dict[str, str]:
    token = create_access_token(user_id=str(user.id), role=user.role.value, fhir_ref=user.fhir_ref)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def superuser_token_headers(db: Session) -> dict[str, str]:
    user = db.exec(select(AppUser).where(AppUser.role == UserRole.SUPER_USER)).first()
    assert user is not None
    return _make_token_headers(user)
