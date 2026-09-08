from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from pycrmkit.contacts import ContactId
from pycrmkit.exceptions import InvalidStateError, ValidationError
from pycrmkit.leads import Lead, LeadId, LeadStatus
from pycrmkit.organizations import OrganizationId

NOW = datetime(2026, 9, 8, 6, 0, tzinfo=UTC)


def make_lead() -> Lead:
    return Lead(
        id=LeadId(UUID("00000000-0000-4000-8000-000000003001")),
        created_at=NOW,
        updated_at=NOW,
        contact_id=ContactId(UUID("00000000-0000-4000-8000-000000003002")),
        organization_id=OrganizationId(UUID("00000000-0000-4000-8000-000000003003")),
        source="  Website   form ",
    )


def test_lead_normalizes_source_and_defaults_to_new() -> None:
    lead = make_lead()
    assert lead.status is LeadStatus.NEW
    assert lead.source == "Website form"


def test_lead_supports_declared_qualification_lifecycle() -> None:
    lead = make_lead()
    lead.open(NOW + timedelta(minutes=1))
    assert lead.status is LeadStatus.OPEN
    lead.mark_contacted(NOW + timedelta(minutes=2))
    assert lead.status is LeadStatus.CONTACTED
    lead.qualify(NOW + timedelta(minutes=3))
    assert lead.status is LeadStatus.QUALIFIED
    lead.mark_converted(NOW + timedelta(minutes=4))
    assert lead.status is LeadStatus.CONVERTED
    assert lead.updated_at == NOW + timedelta(minutes=4)


def test_lead_can_be_qualified_directly_from_new() -> None:
    lead = make_lead()
    lead.qualify(NOW + timedelta(minutes=1))
    assert lead.status is LeadStatus.QUALIFIED


def test_lead_can_be_disqualified_from_qualified() -> None:
    lead = make_lead()
    lead.qualify(NOW + timedelta(minutes=1))
    lead.disqualify(NOW + timedelta(minutes=2))
    assert lead.status is LeadStatus.DISQUALIFIED


def test_terminal_lead_rejects_further_transition() -> None:
    lead = make_lead()
    lead.disqualify(NOW + timedelta(minutes=1))
    with pytest.raises(InvalidStateError) as exc:
        lead.qualify(NOW + timedelta(minutes=2))
    assert exc.value.code == "lead.transition.invalid"


def test_conversion_requires_qualified_lead() -> None:
    lead = make_lead()
    with pytest.raises(InvalidStateError):
        lead.mark_converted(NOW + timedelta(minutes=1))


def test_lead_transition_rejects_timestamp_before_creation() -> None:
    lead = make_lead()
    with pytest.raises(ValidationError) as exc:
        lead.qualify(NOW - timedelta(seconds=1))
    assert exc.value.code == "lead.transition.invalid_timestamp"
