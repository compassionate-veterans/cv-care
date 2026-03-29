from datetime import timedelta

import jwt
import pytest

from app.core.config import settings
from app.core.security import ALGORITHM, TOKEN_EXPIRY, create_access_token


def test_create_token_patient_expiry() -> None:
    token = create_access_token(user_id="test-id", role="PATIENT")
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    assert payload["sub"] == "test-id"
    assert payload["role"] == "PATIENT"
    assert "fhir_ref" not in payload


def test_create_token_provider_expiry() -> None:
    token = create_access_token(user_id="test-id", role="PROVIDER")
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    assert payload["role"] == "PROVIDER"


def test_create_token_with_fhir_ref() -> None:
    token = create_access_token(user_id="test-id", role="PATIENT", fhir_ref="Patient/abc-123")
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    assert payload["fhir_ref"] == "Patient/abc-123"


def test_create_token_custom_expiry() -> None:
    token = create_access_token(user_id="test-id", role="PATIENT", expires_delta=timedelta(minutes=5))
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    assert payload["sub"] == "test-id"


def test_expired_token_raises() -> None:
    token = create_access_token(user_id="test-id", role="PATIENT", expires_delta=timedelta(seconds=-1))
    with pytest.raises(jwt.ExpiredSignatureError):
        jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])


def test_role_expiry_values() -> None:
    assert TOKEN_EXPIRY["PATIENT"] == timedelta(hours=12)
    assert TOKEN_EXPIRY["PROVIDER"] == timedelta(hours=8)
    assert TOKEN_EXPIRY["SUPER_USER"] == timedelta(hours=8)
    assert TOKEN_EXPIRY["ADMIN_CANNABIS"] == timedelta(hours=8)
