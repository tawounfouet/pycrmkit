"""LOT-32-004: Campaign UoW atomicity and post-commit events in Memory."""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from pycrmkit.campaigns import Campaign, CampaignId, CampaignMember
from pycrmkit.contacts import ContactId
from pycrmkit.core.events import EventId, EventType
from pycrmkit.core.pagination import OffsetPageRequest
from pycrmkit.core.references import EntityReference
from pycrmkit.events import DomainEvent, InProcessEventBus
from pycrmkit.exceptions import NotFoundError
from pycrmkit.storage.memory import MemoryStore, MemoryUnitOfWork

NOW = datetime(2026, 10, 30, 11, tzinfo=UTC)
CID = CampaignId(UUID(int=3200401))
REF = EntityReference("contact", ContactId(UUID(int=3200402)))


def _campaign() -> Campaign:
    return Campaign(
        id=CID, key="stable-memory-persistence", name="Memory committed",
        created_at=NOW, updated_at=NOW,
        metadata={"nested": {"revision": 1, "flags": [True, False]}},
    )


def _event(number: int) -> DomainEvent:
    return DomainEvent(
        id=EventId(UUID(int=number)),
        type=EventType("campaign.member_added"), schema_version=1,
        aggregate_type="campaign", aggregate_id=str(CID),
        occurred_at=NOW,
    )


def test_stable_memory_commit_is_atomic_and_events_follow_commit() -> None:
    store = MemoryStore()
    bus = InProcessEventBus()
    seen: list[DomainEvent] = []
    bus.subscribe("campaign.member_added", seen.append)
    with MemoryUnitOfWork(store, event_publisher=bus) as uow:
        uow.campaigns.save(_campaign())
        uow.campaign_audience.add_member(CampaignMember(CID, REF, NOW))
        uow.add_event(_event(3200403))
        assert seen == []
        uow.commit()
    assert [str(e.type) for e in seen] == ["campaign.member_added"]
    with MemoryUnitOfWork(store) as reader:
        restored = reader.campaigns.get(CID)
        assert restored.name == "Memory committed"
        assert restored.metadata == {"nested": {"revision": 1, "flags": [True, False]}}
        assert reader.campaign_audience.list_members(CID, OffsetPageRequest()).total == 1


def test_stable_memory_rollback_discards_member_and_event() -> None:
    store = MemoryStore()
    bus = InProcessEventBus()
    observed: list[DomainEvent] = []
    bus.subscribe("campaign.member_added", observed.append)
    with pytest.raises(RuntimeError, match="injected rollback"):
        with MemoryUnitOfWork(store, event_publisher=bus) as uow:
            uow.campaigns.save(_campaign())
            uow.campaign_audience.add_member(CampaignMember(CID, REF, NOW))
            uow.add_event(_event(3200404))
            raise RuntimeError("injected rollback")
    assert observed == []
    with MemoryUnitOfWork(store) as reader:
        with pytest.raises(NotFoundError) as missing:
            reader.campaigns.get(CID)
        assert missing.value.code == "campaign.not_found"
        assert reader.campaign_audience.list_members(CID, OffsetPageRequest()).total == 0
