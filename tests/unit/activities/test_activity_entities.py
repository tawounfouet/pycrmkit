"""Activity entity and value-object invariants."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from pycrmkit.activities import (
    Activity,
    ActivityDirection,
    ActivityId,
    ActivityParticipant,
    ActivityType,
)
from pycrmkit.contacts import ContactId
from pycrmkit.core.references import EntityReference
from pycrmkit.exceptions import ValidationError

NOW = datetime(2026, 9, 7, 7, 30, tzinfo=UTC)


def contact_ref(value: int = 1) -> EntityReference:
    return EntityReference(
        "contact",
        ContactId(UUID(f"00000000-0000-4000-8000-{value:012d}")),
    )


def activity(**changes) -> Activity:
    values = {
        "id": ActivityId(UUID("00000000-0000-4000-8000-000000000101")),
        "created_at": NOW,
        "updated_at": NOW,
        "type": ActivityType.CALL,
        "occurred_at": NOW,
        "subject": "Commercial follow-up",
    }
    values.update(changes)
    return Activity(**values)


def test_activity_base_types_are_frozen_to_phase_scope() -> None:
    assert {item.value for item in ActivityType} == {
        "email",
        "call",
        "meeting",
        "note",
        "message",
        "document",
        "event",
        "custom",
    }


def test_activity_normalizes_direction_and_optional_text() -> None:
    logged = activity(
        type="call",
        direction="outbound",
        subject="  Commercial   follow-up ",
        source="  imported CRM ",
        external_id="  ext-42 ",
    )

    assert logged.type is ActivityType.CALL
    assert logged.direction is ActivityDirection.OUTBOUND
    assert logged.subject == "Commercial follow-up"
    assert logged.source == "imported CRM"
    assert logged.external_id == "ext-42"


def test_activity_accepts_historical_occurred_at_before_import_time() -> None:
    historical = datetime(2020, 1, 2, 9, 0, tzinfo=UTC)

    logged = activity(occurred_at=historical)

    assert logged.occurred_at == historical


def test_activity_requires_meaningful_context() -> None:
    with pytest.raises(ValidationError, match="meaningful"):
        activity(subject=None)


@pytest.mark.parametrize("duration", [-1, 1.5, True])
def test_activity_rejects_invalid_duration(duration) -> None:
    with pytest.raises(ValidationError):
        activity(duration_seconds=duration)


def test_activity_rejects_duplicate_participant_entity() -> None:
    reference = contact_ref()
    with pytest.raises(ValidationError, match="at most once"):
        activity(
            subject=None,
            participants=(
                ActivityParticipant(reference, role="caller"),
                ActivityParticipant(reference, role="customer"),
            ),
        )


def test_activity_rejects_multiple_primary_participants() -> None:
    with pytest.raises(ValidationError, match="at most one primary"):
        activity(
            subject=None,
            participants=(
                ActivityParticipant(contact_ref(1), is_primary=True),
                ActivityParticipant(contact_ref(2), is_primary=True),
            ),
        )


def test_participant_role_is_normalized() -> None:
    participant = ActivityParticipant(contact_ref(), role="  Decision   maker  ")

    assert participant.role == "Decision maker"
