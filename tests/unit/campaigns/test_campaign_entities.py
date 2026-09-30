from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from pycrmkit.campaigns import Campaign, CampaignId, CampaignStatus
from pycrmkit.exceptions import InvalidStateError, ValidationError

NOW = datetime(2026, 9, 30, 0, 0, tzinfo=UTC)


def campaign(**overrides: object) -> Campaign:
    values: dict[str, object] = {
        "id": CampaignId(UUID("00000000-0000-0000-0000-000000000120")),
        "created_at": NOW,
        "updated_at": NOW,
        "key": " Autumn-Launch ",
        "name": "  Autumn   Launch  ",
    }
    values.update(overrides)
    return Campaign(**values)  # type: ignore[arg-type]


def test_campaign_normalizes_identity_metadata_and_schedule() -> None:
    item = campaign(
        description="  Strategic   launch ",
        starts_at=datetime(2026, 10, 1, 8, tzinfo=UTC),
        ends_at=datetime(2026, 10, 31, 18, tzinfo=UTC),
        metadata={"source": "planning"},
    )

    assert item.key == "autumn-launch"
    assert item.name == "Autumn Launch"
    assert item.description == "Strategic launch"
    assert item.status is CampaignStatus.DRAFT
    assert item.revision == 1
    assert item.metadata == {"source": "planning"}


def test_campaign_rejects_invalid_schedule() -> None:
    with pytest.raises(ValidationError) as error:
        campaign(
            starts_at=datetime(2026, 11, 1, tzinfo=UTC),
            ends_at=datetime(2026, 10, 1, tzinfo=UTC),
        )

    assert error.value.code == "campaign.schedule.invalid"


def test_campaign_lifecycle_is_explicit_and_revisioned() -> None:
    item = campaign()

    item.activate(datetime(2026, 10, 1, tzinfo=UTC))
    assert item.status is CampaignStatus.ACTIVE
    assert item.revision == 2

    item.complete(datetime(2026, 10, 31, tzinfo=UTC))
    assert item.status is CampaignStatus.COMPLETED
    assert item.revision == 3

    item.archive(datetime(2026, 11, 1, tzinfo=UTC))
    assert item.status is CampaignStatus.ARCHIVED
    assert item.revision == 4
    assert item.archived_at == datetime(2026, 11, 1, tzinfo=UTC)


def test_campaign_rejects_invalid_lifecycle_transition() -> None:
    item = campaign()

    with pytest.raises(InvalidStateError) as error:
        item.complete(datetime(2026, 10, 1, tzinfo=UTC))

    assert error.value.code == "campaign.complete.invalid_state"


def test_archived_campaign_is_not_mutable() -> None:
    item = campaign()
    item.archive(datetime(2026, 10, 1, tzinfo=UTC))

    with pytest.raises(InvalidStateError) as error:
        item.ensure_mutable()

    assert error.value.code == "campaign.archived"
