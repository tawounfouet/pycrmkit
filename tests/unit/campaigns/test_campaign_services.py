from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from pycrmkit.campaigns import (
    CampaignQuery,
    CampaignService,
    CampaignStatus,
    CampaignUpdate,
)
from pycrmkit.core.time import FixedClock
from pycrmkit.exceptions import ConflictError, DuplicateError
from pycrmkit.storage.memory import MemoryCampaignRepository

NOW = datetime(2026, 9, 30, 8, tzinfo=UTC)


def service() -> tuple[CampaignService, FixedClock]:
    clock = FixedClock(NOW)
    return CampaignService(MemoryCampaignRepository(), clock=clock), clock


def test_campaign_service_create_update_and_query() -> None:
    campaigns, clock = service()
    created = campaigns.create(
        key="q4-enterprise",
        name="Q4 Enterprise",
        description="Initial metadata",
        starts_at=NOW + timedelta(days=1),
        metadata={"objective": "pipeline"},
    )

    clock.advance(timedelta(hours=1))
    updated = campaigns.update(
        created.id,
        CampaignUpdate(
            name="Q4 Enterprise France",
            description=None,
            metadata={"objective": "pipeline", "region": "fr"},
        ),
        expected_revision=1,
    )

    page = campaigns.list(CampaignQuery(status=CampaignStatus.DRAFT))

    assert updated.id == created.id
    assert updated.revision == 2
    assert updated.name == "Q4 Enterprise France"
    assert updated.description is None
    assert updated.metadata["region"] == "fr"
    assert page.items == (updated,)


def test_campaign_service_enforces_unique_keys_and_revision_preconditions() -> None:
    campaigns, _ = service()
    first = campaigns.create(key="launch", name="Launch")

    with pytest.raises(DuplicateError) as duplicate:
        campaigns.create(key="LAUNCH", name="Duplicate")
    assert duplicate.value.code == "campaign.key.duplicate"

    with pytest.raises(ConflictError) as conflict:
        campaigns.update(
            first.id,
            CampaignUpdate(name="Changed"),
            expected_revision=99,
        )
    assert conflict.value.code == "campaign.revision.conflict"


def test_campaign_service_lifecycle_and_archived_filter() -> None:
    campaigns, clock = service()
    item = campaigns.create(key="event-2026", name="Event 2026")

    clock.advance(timedelta(days=1))
    active = campaigns.activate(item.id, expected_revision=1)
    clock.advance(timedelta(days=1))
    completed = campaigns.complete(active.id, expected_revision=2)
    clock.advance(timedelta(days=1))
    archived = campaigns.archive(completed.id, expected_revision=3)

    assert archived.status is CampaignStatus.ARCHIVED
    assert archived.revision == 4
    assert campaigns.list().total == 0
    assert campaigns.list(CampaignQuery(include_archived=True)).items == (archived,)
