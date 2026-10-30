"""LOT-32-004: PostgreSQL Campaign rollback, post-commit events and CAS."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from sqlalchemy.orm import Session, sessionmaker

from pycrmkit.campaigns import Campaign, CampaignId, CampaignMember
from pycrmkit.contacts import ContactId
from pycrmkit.core.events import EventId, EventType
from pycrmkit.core.pagination import OffsetPageRequest
from pycrmkit.core.references import EntityReference
from pycrmkit.events import DomainEvent, InProcessEventBus
from pycrmkit.exceptions import ConflictError
from pycrmkit.storage.sqlalchemy import SQLAlchemyUnitOfWork

pytestmark = pytest.mark.postgresql
NOW = datetime(2026, 10, 30, 11, tzinfo=UTC)
CID = CampaignId(UUID(int=3200411))
REF = EntityReference("contact", ContactId(UUID(int=3200412)))


def _campaign(*, revision: int = 1, name: str = "Original") -> Campaign:
    return Campaign(
        id=CID, key="stable-pg-persistence", name=name,
        revision=revision, created_at=NOW,
        updated_at=NOW + timedelta(minutes=revision - 1),
        metadata={"nested": {"revision": revision}},
    )


def _event(number: int) -> DomainEvent:
    return DomainEvent(
        id=EventId(UUID(int=number)),
        type=EventType("campaign.member_added"),
        schema_version=1, aggregate_type="campaign",
        aggregate_id=str(CID), occurred_at=NOW,
    )


def test_stable_pg_rollback_blocks_partial_rows_and_event(
    postgres_session_factory: sessionmaker[Session],
) -> None:
    factory = postgres_session_factory
    bus = InProcessEventBus()
    observed: list[DomainEvent] = []
    bus.subscribe("campaign.member_added", observed.append)
    with pytest.raises(RuntimeError, match="injected stable failure"):
        with SQLAlchemyUnitOfWork(factory, event_publisher=bus) as uow:
            uow.campaigns.save(_campaign())
            uow.campaign_audience.add_member(CampaignMember(CID, REF, NOW))
            uow.add_event(_event(3200413))
            raise RuntimeError("injected stable failure")
    assert observed == []
    with SQLAlchemyUnitOfWork(factory) as reader:
        assert reader.campaigns.find(CID) is None
        assert reader.campaign_audience.list_members(CID, OffsetPageRequest()).total == 0
    with SQLAlchemyUnitOfWork(factory, event_publisher=bus) as uow:
        uow.campaigns.save(_campaign())
        uow.campaign_audience.add_member(CampaignMember(CID, REF, NOW))
        uow.add_event(_event(3200414))
        assert observed == []
        uow.commit()
    assert len(observed) == 1
    with SQLAlchemyUnitOfWork(factory) as reader:
        assert reader.campaigns.get(CID).metadata == {"nested": {"revision": 1}}
        assert reader.campaign_audience.list_members(CID, OffsetPageRequest()).total == 1


def test_stable_pg_stale_revision_does_not_rewrite_committed_row(
    postgres_session_factory: sessionmaker[Session],
) -> None:
    factory = postgres_session_factory
    with SQLAlchemyUnitOfWork(factory) as uow:
        uow.campaigns.save(_campaign())
        uow.commit()
    with SQLAlchemyUnitOfWork(factory) as uow:
        uow.campaigns.save(_campaign(revision=2, name="Committed update"))
        uow.commit()
    with pytest.raises(ConflictError) as exc:
        with SQLAlchemyUnitOfWork(factory) as uow:
            uow.campaigns.save(_campaign(revision=2, name="Stale rewrite"))
            uow.commit()
    assert exc.value.code == "campaign.revision.conflict"
    with SQLAlchemyUnitOfWork(factory) as reader:
        assert reader.campaigns.get(CID).revision == 2
        assert reader.campaigns.get(CID).name == "Committed update"
