"""Real PostgreSQL Campaign persistence, concurrency and rollback qualification."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta, timezone
from threading import Barrier
from uuid import UUID

import pytest
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from pycrmkit.campaigns import (
    Campaign,
    CampaignAttributionReference,
    CampaignCommunicationLink,
    CampaignId,
    CampaignMember,
    CampaignSegmentSource,
)
from pycrmkit.communication import CommunicationRecordId
from pycrmkit.contacts import ContactId
from pycrmkit.core.events import EventId, EventType
from pycrmkit.core.pagination import OffsetPageRequest
from pycrmkit.core.references import EntityReference
from pycrmkit.events import DomainEvent, InProcessEventBus
from pycrmkit.exceptions import ConflictError, DuplicateError, NotFoundError
from pycrmkit.segments import SegmentId
from pycrmkit.storage.sqlalchemy import Base, SQLAlchemyUnitOfWork
from pycrmkit.storage.sqlalchemy.models.campaign import CampaignSegmentMemberModel

pytestmark = pytest.mark.postgresql

DATABASE_ENV = "PYCRMKIT_TEST_POSTGRES_URL"
NOW = datetime(2026, 9, 30, 16, tzinfo=UTC)
CAMPAIGN_ID = CampaignId(UUID("00000000-0000-4000-8000-00000000c001"))


@pytest.fixture
def campaign_postgres_engine() -> Engine:
    database_url = os.environ.get(DATABASE_ENV)
    if not database_url:
        pytest.skip(f"{DATABASE_ENV} is required for PostgreSQL qualification")
    engine = create_engine(database_url, pool_pre_ping=True)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def _factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


def _campaign(
    *,
    revision: int = 1,
    name: str = "Concurrent Campaign",
    updated_at: datetime = NOW,
) -> Campaign:
    return Campaign(
        id=CAMPAIGN_ID,
        created_at=NOW,
        updated_at=updated_at,
        key="concurrent-campaign",
        name=name,
        revision=revision,
        metadata={"nested": {"qualification": True}},
    )


def _contact(number: int) -> EntityReference:
    return EntityReference("contact", ContactId(UUID(int=number)))


def _seed_campaign(factory: sessionmaker[Session]) -> None:
    with SQLAlchemyUnitOfWork(factory) as uow:
        uow.campaigns.save(_campaign())
        uow.commit()


def test_postgresql_campaign_revision_race_detects_stale_writer(
    campaign_postgres_engine: Engine,
) -> None:
    factory = _factory(campaign_postgres_engine)
    _seed_campaign(factory)
    barrier = Barrier(2)

    def writer(name: str) -> str:
        with SQLAlchemyUnitOfWork(factory) as uow:
            current = uow.campaigns.get(CAMPAIGN_ID)
            revised = Campaign(
                id=current.id,
                created_at=current.created_at,
                updated_at=NOW + timedelta(minutes=1),
                key=current.key,
                name=name,
                revision=current.revision + 1,
                metadata=dict(current.metadata),
            )
            barrier.wait()
            try:
                uow.campaigns.save(revised)
                uow.commit()
            except ConflictError as error:
                return error.code
            return "committed"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = set(pool.map(writer, ("Writer A", "Writer B")))

    assert outcomes == {"committed", "campaign.revision.conflict"}
    with SQLAlchemyUnitOfWork(factory) as uow:
        assert uow.campaigns.get(CAMPAIGN_ID).revision == 2


def test_postgresql_concurrent_duplicate_member_and_attribution_converge(
    campaign_postgres_engine: Engine,
) -> None:
    factory = _factory(campaign_postgres_engine)
    _seed_campaign(factory)
    member_barrier = Barrier(2)
    entity = _contact(8101)
    member = CampaignMember(CAMPAIGN_ID, entity, NOW)

    def add_member() -> str:
        with SQLAlchemyUnitOfWork(factory) as uow:
            uow.campaign_audience.add_member(member)
            member_barrier.wait()
            try:
                uow.commit()
            except DuplicateError:
                return "duplicate"
            return "committed"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert set(pool.map(lambda _: add_member(), range(2))) == {
            "committed",
            "duplicate",
        }

    attribution_barrier = Barrier(2)
    reference = CampaignAttributionReference(
        campaign_id=CAMPAIGN_ID,
        target=entity,
        source="organic",
        external_ref=None,
        recorded_at=NOW,
    )

    def add_attribution() -> str:
        with SQLAlchemyUnitOfWork(factory) as uow:
            uow.campaign_linkage.add_attribution(reference)
            attribution_barrier.wait()
            try:
                uow.commit()
            except DuplicateError:
                return "duplicate"
            return "committed"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert set(pool.map(lambda _: add_attribution(), range(2))) == {
            "committed",
            "duplicate",
        }

    with SQLAlchemyUnitOfWork(factory) as uow:
        assert uow.campaign_audience.list_members(
            CAMPAIGN_ID,
            OffsetPageRequest(),
        ).total == 1
        assert uow.campaign_linkage.list_attributions(
            CAMPAIGN_ID,
            OffsetPageRequest(),
        ).total == 1


def test_postgresql_segment_capture_failure_rolls_back_source_members_and_event(
    campaign_postgres_engine: Engine,
) -> None:
    factory = _factory(campaign_postgres_engine)
    _seed_campaign(factory)
    bus = InProcessEventBus()
    published: list[DomainEvent] = []
    bus.subscribe("campaign.segment_source.attached", published.append)

    source = CampaignSegmentSource(
        campaign_id=CAMPAIGN_ID,
        segment_id=SegmentId(UUID(int=8201)),
        segment_revision=1,
        entity_kind="contact",
        attached_at=NOW,
        captured_at=NOW,
        member_count=1,
    )
    entity = _contact(8202)
    event = DomainEvent(
        id=EventId(UUID(int=8203)),
        type=EventType("campaign.segment_source.attached"),
        schema_version=1,
        aggregate_type="campaign",
        aggregate_id=str(CAMPAIGN_ID),
        occurred_at=NOW,
    )

    with pytest.raises(DuplicateError):
        with SQLAlchemyUnitOfWork(factory, event_publisher=bus) as uow:
            uow.campaign_audience.add_segment_source(source, (entity,))
            uow.campaign_audience.session.add(
                CampaignSegmentMemberModel(
                    campaign_id=str(CAMPAIGN_ID),
                    segment_id=str(source.segment_id),
                    entity_kind=entity.kind,
                    entity_id=str(entity.id),
                )
            )
            uow.add_event(event)
            uow.commit()

    assert published == []
    with SQLAlchemyUnitOfWork(factory) as uow:
        with pytest.raises(NotFoundError):
            uow.campaign_audience.get_segment_source(
                CAMPAIGN_ID,
                source.segment_id,
            )
        assert uow.campaign_audience.audience_count(CAMPAIGN_ID) == 0


def test_postgresql_campaign_timezone_and_json_round_trip(
    campaign_postgres_engine: Engine,
) -> None:
    factory = _factory(campaign_postgres_engine)
    paris = timezone(timedelta(hours=2))
    local_time = datetime(2026, 9, 30, 18, tzinfo=paris)
    campaign = Campaign(
        id=CAMPAIGN_ID,
        created_at=local_time,
        updated_at=local_time,
        key="timezone-campaign",
        name="Timezone Campaign",
        starts_at=local_time + timedelta(hours=1),
        ends_at=local_time + timedelta(hours=2),
        metadata={"nested": {"values": [1, "two", True]}},
    )
    entity = _contact(8301)
    member = CampaignMember(CAMPAIGN_ID, entity, local_time)
    source = CampaignSegmentSource(
        campaign_id=CAMPAIGN_ID,
        segment_id=SegmentId(UUID(int=8302)),
        segment_revision=1,
        entity_kind="contact",
        attached_at=local_time,
        captured_at=local_time,
        member_count=1,
        metadata={"capture": {"kind": "snapshot"}},
    )
    attribution = CampaignAttributionReference(
        campaign_id=CAMPAIGN_ID,
        target=entity,
        source="organic",
        recorded_at=local_time,
        metadata={"touch": {"score": 1}},
    )
    link = CampaignCommunicationLink(
        campaign_id=CAMPAIGN_ID,
        communication_id=CommunicationRecordId(UUID(int=8303)),
        linked_at=local_time,
        metadata={"channel": "email"},
    )

    with SQLAlchemyUnitOfWork(factory) as uow:
        uow.campaigns.save(campaign)
        uow.campaign_audience.add_member(member)
        uow.campaign_audience.add_segment_source(source, (entity,))
        uow.campaign_linkage.add_attribution(attribution)
        uow.campaign_linkage.add_communication_link(link)
        uow.commit()

    with SQLAlchemyUnitOfWork(factory) as uow:
        restored = uow.campaigns.get(CAMPAIGN_ID)
        restored_member = uow.campaign_audience.list_members(
            CAMPAIGN_ID,
            OffsetPageRequest(),
        ).items[0]
        restored_source = uow.campaign_audience.get_segment_source(
            CAMPAIGN_ID,
            source.segment_id,
        )
        restored_attribution = uow.campaign_linkage.list_attributions(
            CAMPAIGN_ID,
            OffsetPageRequest(),
        ).items[0]
        restored_link = uow.campaign_linkage.list_communication_links(
            CAMPAIGN_ID,
            OffsetPageRequest(),
        ).items[0]

    assert restored.created_at.tzinfo is UTC
    assert restored.updated_at.tzinfo is UTC
    assert restored.starts_at is not None and restored.starts_at.tzinfo is UTC
    assert restored.ends_at is not None and restored.ends_at.tzinfo is UTC
    assert restored_member.added_at.tzinfo is UTC
    assert restored_source.attached_at.tzinfo is UTC
    assert restored_source.captured_at.tzinfo is UTC
    assert restored_attribution.recorded_at.tzinfo is UTC
    assert restored_link.linked_at.tzinfo is UTC
    assert restored.metadata == campaign.metadata
    assert restored_source.metadata == source.metadata
