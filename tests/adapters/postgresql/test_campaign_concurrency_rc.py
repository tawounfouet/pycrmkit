"""LOT-31-009 - Real PostgreSQL Campaign integrity/concurrency qualification.

PostgreSQL 16/17 + SQLAlchemy/psycopg matrix: two distinct transactions,
database-enforced uniqueness, CAS, atomic rollback and FK/orphan checks.
The postgres_session_factory fixture provisions a disposable test schema.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from uuid import UUID

import pytest
from sqlalchemy import Engine, delete, func, inspect, select
from sqlalchemy.orm import Session, sessionmaker

from pycrmkit.campaigns import (
    Campaign,
    CampaignAttributionReference,
    CampaignId,
    CampaignMember,
    CampaignSegmentSource,
)
from pycrmkit.contacts import ContactId
from pycrmkit.core.events import EventId, EventType
from pycrmkit.core.pagination import OffsetPageRequest
from pycrmkit.core.references import EntityReference
from pycrmkit.events import DomainEvent, InProcessEventBus
from pycrmkit.exceptions import ConflictError, DuplicateError
from pycrmkit.segments import SegmentId
from pycrmkit.storage.sqlalchemy import SQLAlchemyUnitOfWork
from pycrmkit.storage.sqlalchemy.models.campaign import (
    CampaignAttributionModel,
    CampaignMemberModel,
    CampaignModel,
    CampaignSegmentMemberModel,
    CampaignSegmentSourceModel,
)

pytestmark = pytest.mark.postgresql

NOW = datetime(2026, 10, 29, 7, tzinfo=UTC)
CID = CampaignId(UUID(int=91001))


def _seed(factory: sessionmaker[Session]) -> None:
    with SQLAlchemyUnitOfWork(factory) as uow:
        uow.campaigns.save(Campaign(
            id=CID,
            key="rc-live-pg-race",
            name="Original",
            created_at=NOW,
            updated_at=NOW,
        ))
        uow.commit()


def _ref(number: int) -> EntityReference:
    return EntityReference("contact", ContactId(UUID(int=number)))


def _event(kind: str, number: int) -> DomainEvent:
    return DomainEvent(
        id=EventId(UUID(int=number)),
        type=EventType(kind),
        schema_version=1,
        aggregate_type="campaign",
        aggregate_id=str(CID),
        occurred_at=NOW,
    )


def _source(segment_id: SegmentId, *, members: int = 1) -> CampaignSegmentSource:
    return CampaignSegmentSource(
        campaign_id=CID,
        segment_id=segment_id,
        segment_revision=1,
        entity_kind="contact",
        attached_at=NOW,
        captured_at=NOW,
        member_count=members,
    )


def test_live_campaign_constraints_and_foreign_keys(
    postgres_engine: Engine,
) -> None:
    db = inspect(postgres_engine)
    campaign_unique = db.get_unique_constraints("pycrmkit_campaigns")
    assert any(
        set(record["column_names"]) == {"key"} for record in campaign_unique
    )
    member_unique = db.get_unique_constraints("pycrmkit_campaign_members")
    assert any(
        record["name"] == "uq_pycrmkit_campaign_members_target"
        and set(record["column_names"]) == {
            "campaign_id", "entity_kind", "entity_id"
        }
        for record in member_unique
    )
    source_pk = db.get_pk_constraint("pycrmkit_campaign_segment_sources")
    assert set(source_pk["constrained_columns"]) == {"campaign_id", "segment_id"}

    snapshot_unique = db.get_unique_constraints("pycrmkit_campaign_segment_members")
    assert any(
        record["name"] == "uq_pycrmkit_campaign_segment_members_target"
        for record in snapshot_unique
    )
    snapshots_fk = db.get_foreign_keys("pycrmkit_campaign_segment_members")
    assert any(
        fk["referred_table"] == "pycrmkit_campaign_segment_sources"
        and set(fk["constrained_columns"]) == {"campaign_id", "segment_id"}
        and fk.get("options", {}).get("ondelete") == "CASCADE"
        for fk in snapshots_fk
    )
    for table in (
        "pycrmkit_campaign_members",
        "pycrmkit_campaign_attributions",
        "pycrmkit_campaign_segment_sources",
        "pycrmkit_campaign_communication_links",
    ):
        assert any(
            fk["referred_table"] == "pycrmkit_campaigns"
            and fk.get("options", {}).get("ondelete") == "CASCADE"
            for fk in db.get_foreign_keys(table)
        )


def test_two_postgresql_writers_cannot_lose_campaign_update(
    postgres_session_factory: sessionmaker[Session],
) -> None:
    factory = postgres_session_factory
    _seed(factory)
    gate = Barrier(2, timeout=15)
    bus = InProcessEventBus()
    published: list[str] = []
    bus.subscribe("campaign.updated", lambda event: published.append(str(event.type)))

    def writer(name: str, event_number: int) -> tuple[str, str]:
        with SQLAlchemyUnitOfWork(factory, event_publisher=bus) as uow:
            before = uow.campaigns.get(CID)
            assert before.revision == 1
            candidate = Campaign(
                id=before.id,
                key=before.key,
                name=name,
                created_at=before.created_at,
                updated_at=NOW + timedelta(minutes=1),
                revision=2,
                metadata={"writer": name},
            )
            uow.add_event(_event("campaign.updated", event_number))
            gate.wait()
            try:
                uow.campaigns.save(candidate)
                uow.commit()
            except ConflictError as error:
                return "conflict", error.code
            return "committed", name

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(
            lambda inputs: writer(*inputs), (("Writer A", 91101), ("Writer B", 91102))
        ))

    winner = [name for result, name in results if result == "committed"]
    assert len(winner) == 1
    assert [code for result, code in results if result == "conflict"] == [
        "campaign.revision.conflict"
    ]
    with SQLAlchemyUnitOfWork(factory) as uow:
        loaded = uow.campaigns.get(CID)
    assert loaded.revision == 2
    assert loaded.name == winner[0]
    assert loaded.metadata == {"writer": winner[0]}
    assert published == ["campaign.updated"]


def test_two_postgresql_member_writers_emit_only_committed_event(
    postgres_session_factory: sessionmaker[Session],
) -> None:
    factory = postgres_session_factory
    _seed(factory)
    gate = Barrier(2, timeout=15)
    bus = InProcessEventBus()
    published: list[str] = []
    bus.subscribe("campaign.member_added", lambda e: published.append(str(e.type)))
    member = CampaignMember(CID, _ref(91201), NOW)

    def writer(number: int) -> str:
        with SQLAlchemyUnitOfWork(factory, event_publisher=bus) as uow:
            uow.campaign_audience.add_member(member)
            uow.add_event(_event("campaign.member_added", number))
            gate.wait()
            try:
                uow.commit()
            except DuplicateError as error:
                assert error.code == "repository.duplicate"
                assert error.context.get("sqlstate") == "23505"
                assert "statement" not in error.context
                assert "params" not in error.context
                return "duplicate"
            return "committed"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(writer, (91202, 91203)))
    assert sorted(outcomes) == ["committed", "duplicate"]
    with SQLAlchemyUnitOfWork(factory) as uow:
        assert uow.campaign_audience.list_members(
            CID, OffsetPageRequest()
        ).total == 1
    assert published == ["campaign.member_added"]


def test_segment_source_race_keeps_one_parent_and_one_snapshot(
    postgres_session_factory: sessionmaker[Session],
) -> None:
    factory = postgres_session_factory
    _seed(factory)
    gate = Barrier(2, timeout=15)
    segment = SegmentId(UUID(int=91301))
    source = _source(segment)
    member = _ref(91302)

    def writer(_: int) -> str:
        with SQLAlchemyUnitOfWork(factory) as uow:
            assert uow.campaigns.get(CID).revision == 1
            gate.wait()
            try:
                uow.campaign_audience.add_segment_source(source, (member,))
                uow.commit()
            except DuplicateError as error:
                assert error.code in {
                    "repository.duplicate", "campaign.segment_source.duplicate"
                }
                return "duplicate"
            return "committed"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(writer, (1, 2)))
    assert sorted(outcomes) == ["committed", "duplicate"]
    with SQLAlchemyUnitOfWork(factory) as uow:
        sources = uow.campaign_audience.list_segment_sources(
            CID, OffsetPageRequest()
        )
        assert sources.total == 1
        assert sources.items[0].member_count == 1
        assert uow.campaign_audience.audience_count(CID) == 1
    with factory() as session:
        assert session.scalar(
            select(func.count()).select_from(CampaignSegmentMemberModel)
        ) == 1


def test_atomic_rollback_removes_all_queued_side_effects(
    postgres_session_factory: sessionmaker[Session],
) -> None:
    factory = postgres_session_factory
    _seed(factory)
    bus = InProcessEventBus()
    published: list[str] = []
    for kind in (
        "campaign.member_added",
        "campaign.segment_source_attached",
        "campaign.attribution_added",
    ):
        bus.subscribe(kind, lambda e: published.append(str(e.type)))
    member = _ref(91401)
    segment = SegmentId(UUID(int=91402))
    source = _source(segment)
    attribution = CampaignAttributionReference(
        campaign_id=CID,
        target=member,
        source="qualification",
        recorded_at=NOW,
    )
    with pytest.raises(DuplicateError):
        with SQLAlchemyUnitOfWork(factory, event_publisher=bus) as uow:
            uow.campaign_audience.add_member(CampaignMember(CID, member, NOW))
            uow.campaign_audience.add_segment_source(source, (member,))
            uow.campaign_linkage.add_attribution(attribution)
            uow.add_event(_event("campaign.member_added", 91411))
            uow.add_event(_event("campaign.segment_source_attached", 91412))
            uow.add_event(_event("campaign.attribution_added", 91413))
            uow.campaign_audience.session.add(CampaignSegmentMemberModel(
                campaign_id=str(CID),
                segment_id=str(segment),
                entity_kind=member.kind,
                entity_id=str(member.id),
            ))
            uow.commit()
    with factory() as session:
        for model in (
            CampaignMemberModel, CampaignSegmentSourceModel,
            CampaignSegmentMemberModel, CampaignAttributionModel,
        ):
            assert session.scalar(select(func.count()).select_from(model)) == 0
    assert published == []


def test_postgresql_on_delete_cascade_has_no_campaign_orphans(
    postgres_session_factory: sessionmaker[Session],
) -> None:
    factory = postgres_session_factory
    _seed(factory)
    member = _ref(91501)
    segment = SegmentId(UUID(int=91502))
    with SQLAlchemyUnitOfWork(factory) as uow:
        uow.campaign_audience.add_member(CampaignMember(CID, member, NOW))
        uow.campaign_audience.add_segment_source(_source(segment), (member,))
        uow.commit()
    with factory() as session:
        session.execute(delete(CampaignModel).where(CampaignModel.id == str(CID)))
        session.commit()
    with factory() as session:
        for model in (
            CampaignMemberModel, CampaignSegmentSourceModel,
            CampaignSegmentMemberModel,
        ):
            assert session.scalar(select(func.count()).select_from(model)) == 0
        assert session.scalar(select(func.count()).select_from(CampaignModel)) == 0
