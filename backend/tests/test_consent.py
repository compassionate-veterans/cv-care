import datetime

import pytest

from app.fhir import build_consent
from app.models import ConsentType


@pytest.mark.parametrize(
    ("consent_type", "expected_scope", "expected_category"),
    [
        (ConsentType.THERAPY_PARTICIPATION, "treatment", "therapy-participation"),
        (ConsentType.LOCATION_SHARING, "patient-privacy", "location-sharing"),
        (ConsentType.RECORDING_AI, "patient-privacy", "recording-ai"),
        (ConsentType.MMJ_MANAGEMENT, "patient-privacy", "mmj-management"),
    ],
)
def test_build_consent(consent_type: ConsentType, expected_scope: str, expected_category: str) -> None:
    consent = build_consent("Patient/test-123", consent_type)
    assert consent.status == "active"
    assert consent.scope is not None
    assert consent.scope.coding is not None
    assert consent.scope.coding[0].code == expected_scope
    assert consent.category is not None
    assert consent.category[0].coding is not None
    assert consent.category[0].coding[0].code == expected_category
    assert consent.patient is not None
    assert consent.patient.reference == "Patient/test-123"


def test_build_consent_with_expiry() -> None:
    consent = build_consent("Patient/test-123", ConsentType.MMJ_MANAGEMENT, expires_at="2027-12-31")
    assert consent.provision is not None
    assert consent.provision.period is not None
    assert consent.provision.period.end == datetime.date(2027, 12, 31)


def test_build_consent_without_expiry() -> None:
    consent = build_consent("Patient/test-123", ConsentType.MMJ_MANAGEMENT)
    assert consent.provision is None or consent.provision.period is None
