from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from app.core.config import settings

ALGORITHM = "HS256"

# Role-based token expiry
TOKEN_EXPIRY: dict[str, timedelta] = {
    "PATIENT": timedelta(hours=12),
    "PROVIDER": timedelta(hours=8),
    "ADMIN_CANNABIS": timedelta(hours=8),
    "SUPER_USER": timedelta(hours=8),
}
DEFAULT_EXPIRY = timedelta(hours=8)


def create_access_token(
    user_id: str,
    role: str,
    fhir_ref: str | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    if expires_delta is None:
        expires_delta = TOKEN_EXPIRY.get(role, DEFAULT_EXPIRY)
    expire = datetime.now(UTC) + expires_delta
    to_encode: dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "exp": expire,
    }
    if fhir_ref:
        to_encode["fhir_ref"] = fhir_ref
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
