"""LOT-31-011: one Campaign facade and UoW contract across three real adapters.

Django and SQLAlchemy never share a physical Campaign schema in these tests.
SQLAlchemy runs against its own live PostgreSQL database in the RC CI gate.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest
from django.db import connection

from pycrmkit import CRM
from pycrmkit.campaigns import Campaign, CampaignId, CampaignMember, CampaignUpdate
from pycrmkit.config import CRMConfig
from pycrmkit.contacts import ContactId
from pycrmkit.core.events import EventId, EventType
from pycrmkit.core.pagination import OffsetPageRequest
from pycrmkit.core.references import EntityReference
from pycrmkit.core.time import FixedClock
from pycrmkit.events import DomainEvent, InProcessEventBus
from pycrmkit.exceptions import (
    ConflictError,
    DuplicateError,
    InvalidStateError,
    NotFoundError,
    ValidationError,
)
from pycrmkit.integrations.django.transactions import DjangoTransactionBridge
from pycrmkit.storage.memory import MemoryStore, MemoryUnitOfWork

NOW = datetime(2026, 10, 29, 16, 0, tzinfo=UTC)
START = NOW + timedelta(days=2)
END = NOW + timedelta(days=3)
SQLALCHEMY_TEST_URL = "PYCRMKIT_CROSS_ADAPTER_SQLALCHEMY_URL"


@dataclass
class Harness:
    name: str
    uow_factory: Callable[[], Any]
    bus: InProcessEventBus

    def crm(self) -> CRM:
        return CRM(
            uow_factory=self.uow_factory,
            event_bus=self.bus,
            clock=FixedClock(NOW),
            config=CRMConfig(events_enabled=True, audit_enabled=False),
            webhook_auto_delivery=False,
        )


@pytest.fixture(params=["memory", "django", "sqlalchemy"], ids=str)
def harness(request: pytest.FixtureRequest) -> Iterator[Harness]:
    name = str(request.param)
    bus = InProcessEventBus()
    if name == "memory":
        store = MemoryStore()
        yield Harness(
            name, lambda: MemoryUnitOfWork(store, event_publisher=bus), bus
        )
        return

    if name == "django":
        yield Harness(
            name, lambda: DjangoTransactionBridge(event_publisher=bus), bus
        )
        return

    # An independent *real* PostgreSQL schema, not a SQLite simulation or
    # Django-managed schema. Absence means SKIP, not a false green PG result.
    pytest.importorskip("sqlalchemy")
    url = os.environ.get(SQLALCHEMY_TEST_URL)
    if not url:
        pytest.skip(f"{SQLALCHEMY_TEST_URL} required for live cross-adapter matrix")
    if not url.startswith("postgresql+psycopg://"):
        pytest.fail("Cross-adapter SQLAlchemy URI must use live psycopg PostgreSQL")
    if connection.vendor == "postgresql":
        from django.conf import settings

        django_db = settings.DATABASES["default"]["NAME"]
        from urllib.parse import urlsplit

        sqlalchemy_db = urlsplit(url).path.lstrip("/")
        assert sqlalchemy_db != django_db, "Django/Alembic table collision risk"

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from pycrmkit.storage.sqlalchemy import Base, SQLAlchemyUnitOfWork

    engine = create_engine(url, pool_pre_ping=True)
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        yield Harness(
            name,
            lambda: SQLAlchemyUnitOfWork(sessions, event_publisher=bus),
            bus,
        )
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def _reference(number: int) -> EntityReference:
    return EntityReference("contact", ContactId(UUID(int=number)))


def _campaign(number: int) -> Campaign:
    return Campaign(
        id=CampaignId(UUID(int=number)),
        created_at=NOW,
        updated_at=NOW,
        key=f"rc-adapter-{number}",
        name="Cross-adapter aggregate",
        metadata={"deep": {"flags": [True, "stored"]}},
        starts_at=START,
        ends_at=END,
    )


def _event(number: int, campaign: Campaign) -> DomainEvent:
    return DomainEvent(
        id=EventId(UUID(int=number)),
        type=EventType("campaign.member_added"),
        schema_version=1,
        aggregate_type="campaign",
        aggregate_id=str(campaign.id),
        occurred_at=NOW,
        correlation_id="rc-adapter-qualification",
    )


def _page_aliases(
    crm: CRM, campaign: Campaign, aliases: dict[str, str], page_size: int
) -> tuple[list[str], int]:
    records: list[str] = []
    offset = 0
    total = -1
    while True:
        page = crm.campaigns.audience(
            campaign.id, OffsetPageRequest(limit=page_size, offset=offset)
        )
        if total == -1:
            total = page.total
        else:
            assert total == page.total, "stationary pagination unexpectedly drifted"
        records.extend(aliases[str(entity.id)] for entity in page.items)
        if not page.has_next:
            break
        assert page.items, "page.next must not return an empty page"
        offset += len(page.items)
    return records, total


def test_campaign_full_facade_journey_is_backend_neutral(harness: Harness) -> None:
    """Same entrypoints, same normalized semantic output on 3 independent stores."""
    crm = harness.crm()
    ada = crm.contacts.create(display_name="Ada", source="qual-rc")
    grace = crm.contacts.create(display_name="Grace", source="qual-rc")
    linus = crm.contacts.create(display_name="Linus", source="qual-rc")
    ref_ada = EntityReference("contact", ada.id)
    ref_grace = EntityReference("contact", grace.id)
    ref_linus = EntityReference("contact", linus.id)
    aliases = {str(ada.id): "ada", str(grace.id): "grace", str(linus.id): "linus"}

    created = crm.campaigns.create(
        key="  RC-ADAPTER-JOURNEY  ",
        name="  Cross   Adapter  ",
        starts_at=START,
        ends_at=END,
        metadata={"nested": {"weights": [1, 2], "active": True}},
    )
    assert created.key == "rc-adapter-journey"
    assert created.name == "Cross Adapter"
    assert created.revision == 1
    assert created.created_at == NOW

    direct_ada = crm.campaigns.add_member(
        created.id, ref_ada, source="organic", metadata={"from": "direct"}
    )
    crm.campaigns.add_member(created.id, ref_linus)
    assert direct_ada.metadata == {"from": "direct"}
    assert crm.campaigns.members(created.id).total == 2

    segment = crm.segments.create_static(
        key="rc-adapter-static-segment", name="Captured", entity_kind="contact"
    )
    crm.segments.add_member(segment.id, ref_ada)
    crm.segments.add_member(segment.id, ref_grace)
    captured = crm.campaigns.attach_segment_source(
        created.id, segment.id, metadata={"selection": "snapshot"}
    )
    assert captured.member_count == 2
    assert captured.metadata == {"selection": "snapshot"}
    assert crm.campaigns.segment_sources(created.id).total == 1
    assert crm.campaigns.audience_count(created.id) == 3
    assert crm.campaigns.contains(created.id, ref_grace)

    paged, total = _page_aliases(crm, created, aliases, 1)
    full, _ = _page_aliases(crm, created, aliases, 100)
    assert total == 3
    assert paged == full
    assert sorted(paged) == ["ada", "grace", "linus"]

    # Snapshots do not silently track a changing live Segment.
    crm.segments.remove_member(segment.id, ref_grace)
    assert crm.campaigns.contains(created.id, ref_grace)
    refreshed = crm.campaigns.refresh_segment_source(created.id, segment.id)
    assert refreshed.member_count == 1
    assert refreshed.metadata == captured.metadata
    assert crm.campaigns.audience_count(created.id) == 2
    assert not crm.campaigns.contains(created.id, ref_grace)

    attribution = crm.campaigns.add_attribution(
        created.id, ref_ada,
        source=" LinkedIn   Organic ",
        metadata={"origin": {"name": "qualification"}},
    )
    assert crm.campaigns.attributions(created.id).total == 1
    assert crm.campaigns.attributions(created.id).items == (attribution,)

    updated = crm.campaigns.update(
        created.id,
        CampaignUpdate(name="  Updated  Campaign ", description="ready"),
        expected_revision=1,
    )
    assert updated.revision == 2
    assert updated.name == "Updated Campaign"
    active = crm.campaigns.activate(created.id, expected_revision=2)
    assert active.revision == 3
    assert active.status.value == "active"

    # Every persisted adapter must survive reopening the facade/UoW.
    restored_crm = harness.crm()
    restored = restored_crm.campaigns.get(created.id)
    assert restored.id == created.id
    assert restored.key == created.key
    assert restored.metadata == created.metadata
    assert restored.starts_at == START
    assert restored.ends_at == END
    assert restored.created_at.tzinfo is not None
    assert restored.updated_at.tzinfo is not None
    assert restored.status.value == "active"
    assert restored.revision == 3
    assert restored_crm.campaigns.members(created.id).total == 2
    assert restored_crm.campaigns.segment_sources(created.id).total == 1
    assert restored_crm.campaigns.attributions(created.id).total == 1
    assert restored_crm.campaigns.audience_count(created.id) == 2

    assert restored_crm.campaigns.detach_segment_source(created.id, segment.id)
    assert restored_crm.campaigns.audience_count(created.id) == 2
    assert restored_crm.campaigns.remove_member(created.id, ref_linus)
    assert restored_crm.campaigns.audience_count(created.id) == 1
    archived = restored_crm.campaigns.archive(created.id, expected_revision=3)
    assert archived.status.value == "archived"
    assert archived.archived_at == NOW
    assert archived.revision == 4
    assert restored_crm.campaigns.list().total == 0
    assert restored_crm.campaigns.get(created.id).revision == 4


def test_campaign_duplicate_and_revision_errors_have_same_codes(harness: Harness) -> None:
    crm = harness.crm()
    contact = crm.contacts.create(display_name="Cross-adapter errors")
    target = EntityReference("contact", contact.id)
    campaign = crm.campaigns.create(key="rc-adapter-errors", name="Errors")
    with pytest.raises(DuplicateError) as duplicate:
        crm.campaigns.create(key="RC-ADAPTER-ERRORS", name="duplicate")
    assert duplicate.value.code == "campaign.key.duplicate"

    crm.campaigns.add_member(campaign.id, target)
    with pytest.raises(DuplicateError) as duplicate_member:
        crm.campaigns.add_member(campaign.id, target)
    assert duplicate_member.value.code == "campaign.member.duplicate"

    segment = crm.segments.create_static(
        key="rc-error-segment", name="Error segment", entity_kind="contact"
    )
    crm.segments.add_member(segment.id, target)
    crm.campaigns.attach_segment_source(campaign.id, segment.id)
    with pytest.raises(DuplicateError) as duplicate_source:
        crm.campaigns.attach_segment_source(campaign.id, segment.id)
    assert duplicate_source.value.code == "campaign.segment_source.duplicate"

    crm.campaigns.add_attribution(
        campaign.id, target, source=" LinkedIn  Organic ", external_ref=None,
    )
    with pytest.raises(DuplicateError) as duplicate_attribution:
        crm.campaigns.add_attribution(
            campaign.id, target, source="linkedin organic", external_ref=" ",
        )
    assert duplicate_attribution.value.code == "campaign.attribution.duplicate"

    with pytest.raises(ConflictError) as stale:
        crm.campaigns.update(
            campaign.id, CampaignUpdate(name="stale"), expected_revision=999,
        )
    assert stale.value.code == "campaign.revision.conflict"

    missing_target = _reference(3199999)
    with pytest.raises(ValidationError) as unknown:
        crm.campaigns.add_member(campaign.id, missing_target)
    assert unknown.value.code == "campaign.member.not_found"

    with pytest.raises(NotFoundError) as missing_campaign:
        crm.campaigns.get(CampaignId(UUID(int=3199998)))
    assert missing_campaign.value.code == "campaign.not_found"

    crm.campaigns.archive(campaign.id)
    with pytest.raises(InvalidStateError) as archived:
        crm.campaigns.add_member(campaign.id, target)
    assert archived.value.code == "campaign.archived"


def test_campaign_uow_rollback_and_post_commit_event_are_consistent(
    harness: Harness,
) -> None:
    bus = harness.bus
    delivered: list[DomainEvent] = []
    bus.subscribe("campaign.member_added", delivered.append)

    discarded = _campaign(311101)
    with pytest.raises(RuntimeError, match="inject rollback"):
        with harness.uow_factory() as uow:
            uow.campaigns.save(discarded)
            uow.campaign_audience.add_member(
                CampaignMember(discarded.id, _reference(311102), NOW)
            )
            uow.add_event(_event(311103, discarded))
            assert delivered == []
            raise RuntimeError("inject rollback")
    assert delivered == []
    with harness.uow_factory() as uow:
        assert uow.campaigns.find(discarded.id) is None
        assert uow.campaign_audience.list_members(
            discarded.id, OffsetPageRequest()
        ).total == 0

    committed = _campaign(311104)
    event = _event(311105, committed)
    with harness.uow_factory() as uow:
        uow.campaigns.save(committed)
        uow.add_event(event)
        assert delivered == []
        uow.commit()
    assert delivered == [event]
    with harness.uow_factory() as uow:
        row = uow.campaigns.get(committed.id)
        assert row == committed
        assert row.metadata == committed.metadata
        assert row.created_at == NOW
        assert row.created_at.tzinfo is not None
