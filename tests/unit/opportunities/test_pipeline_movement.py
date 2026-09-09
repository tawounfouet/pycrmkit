from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest

from pycrmkit.contacts import ContactId
from pycrmkit.exceptions import InvalidStateError, ValidationError
from pycrmkit.opportunities import Opportunity, OpportunityId, OpportunityStatus

NOW = datetime(2026, 9, 9, 8, 0, tzinfo=UTC)


def opportunity() -> Opportunity:
    return Opportunity(
        id=OpportunityId(UUID(int=401)),
        created_at=NOW,
        updated_at=NOW,
        name="Pipeline deal",
        contact_id=ContactId(UUID(int=501)),
        pipeline_id="sales",
        stage_id="new",
        probability=Decimal("0.10"),
    )


def test_stage_entry_timestamp_defaults_to_creation_and_tracks_duration() -> None:
    item = opportunity()
    assert item.stage_entered_at == NOW
    item.move_to_stage(
        "qualified",
        probability=Decimal("0.30"),
        at=NOW + timedelta(hours=2),
    )
    assert item.stage_id == "qualified"
    assert item.stage_entered_at == NOW + timedelta(hours=2)
    assert item.stage_duration(NOW + timedelta(hours=5)) == timedelta(hours=3)


def test_stage_entry_timestamp_cannot_be_after_updated_at() -> None:
    with pytest.raises(ValidationError) as exc:
        Opportunity(
            id=OpportunityId(UUID(int=402)),
            created_at=NOW,
            updated_at=NOW,
            name="Bad timestamps",
            contact_id=ContactId(UUID(int=502)),
            pipeline_id="sales",
            stage_id="new",
            stage_entered_at=NOW + timedelta(hours=1),
        )
    assert exc.value.code == "opportunity.stage_entered_at.after_update"


def test_terminal_stage_outcome_closes_opportunity() -> None:
    item = opportunity()
    item.move_to_stage(
        "won",
        probability=Decimal("1"),
        at=NOW + timedelta(hours=1),
        outcome=OpportunityStatus.WON,
    )
    assert item.status is OpportunityStatus.WON
    assert item.is_terminal
    with pytest.raises(InvalidStateError):
        item.move_to_stage(
            "lost",
            probability=Decimal("0"),
            at=NOW + timedelta(hours=2),
        )
