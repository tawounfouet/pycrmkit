"""LOT-32-006: stable Campaign DataOps contract across persistence adapters.

The same import/replay/export domain journey runs against independent Memory,
real PostgreSQL SQLAlchemy, and Django repositories. No snapshot, durable
exactly-once, or implicit host authentication is claimed.
"""

from __future__ import annotations

import csv
import io
import json
import os
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID

import pytest
from django.db import connection

from pycrmkit import CRM
from pycrmkit.campaigns import CampaignUpdate, export_campaign_records, import_campaign_members
from pycrmkit.config import CRMConfig
from pycrmkit.core.references import EntityReference
from pycrmkit.events import DomainEvent, InProcessEventBus
from pycrmkit.exceptions import ConflictError, InvalidStateError
from pycrmkit.importers import CSVReader, JSONLReader, JSONReader
from pycrmkit.integrations.django.transactions import DjangoTransactionBridge
from pycrmkit.storage.memory import MemoryStore, MemoryUnitOfWork

SQLALCHEMY_TEST_URL = "PYCRMKIT_CROSS_ADAPTER_SQLALCHEMY_URL"


@dataclass
class StableHarness:
    name: str
    uow_factory: Callable[[], Any]
    bus: InProcessEventBus

    def crm(self) -> CRM:
        return CRM(
            uow_factory=self.uow_factory,
            event_bus=self.bus,
            config=CRMConfig(events_enabled=True, audit_enabled=False),
        )


@pytest.fixture(params=("memory", "sqlalchemy", "django"))
def stable_harness(request: pytest.FixtureRequest) -> Iterator[StableHarness]:
    name = str(request.param)
    bus = InProcessEventBus()

    if name == "memory":
        store = MemoryStore()
        yield StableHarness(
            name,
            lambda: MemoryUnitOfWork(store, event_publisher=bus),
            bus,
        )
        return

    if name == "django":
        yield StableHarness(
            name, lambda: DjangoTransactionBridge(event_publisher=bus), bus
        )
        return

    pytest.importorskip("sqlalchemy")
    url = os.environ.get(SQLALCHEMY_TEST_URL)
    if not url:
        pytest.skip("real PostgreSQL cross-adapter SQLAlchemy URL is required")
    if not url.startswith("postgresql+psycopg://"):
        pytest.fail("SQLAlchemy stable qualification requires psycopg PostgreSQL")

    db_name = urlsplit(url).path.lstrip("/")
    if not db_name.startswith("pycrmkit_stable_"):
        pytest.fail("Refusing non-disposable SQLAlchemy qualification database")
    if connection.vendor == "postgresql":
        from django.conf import settings

        assert db_name != settings.DATABASES["default"]["NAME"]

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from pycrmkit.storage.sqlalchemy import Base, SQLAlchemyUnitOfWork

    engine = create_engine(url, pool_pre_ping=True)
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        yield StableHarness(
            name,
            lambda: SQLAlchemyUnitOfWork(sessions, event_publisher=bus),
            bus,
        )
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def _record(entity_id: object) -> dict[str, str]:
    return {"entity_kind": "contact", "entity_id": str(entity_id)}


def _csv(rows: list[dict[str, str]]) -> CSVReader:
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=("entity_kind", "entity_id"))
    writer.writeheader()
    writer.writerows(rows)
    stream.seek(0)
    return CSVReader(stream)


def _jsonl(rows: list[dict[str, str]]) -> JSONLReader:
    return JSONLReader(
        io.StringIO("".join(json.dumps(row) + "\n" for row in rows))
    )


@pytest.mark.parametrize("source_format", ("json", "jsonl", "csv"))
def test_stable_campaign_replay_and_exports_match_across_adapters(
    stable_harness: StableHarness, source_format: str
) -> None:
    crm = stable_harness.crm()
    ada = crm.contacts.create(display_name="Privacy Ada")
    grace = crm.contacts.create(display_name="Privacy Grace")
    campaign = crm.campaigns.create(
        key=f"stable-{source_format}", name="Stable Adapter"
    )
    segment = crm.segments.create_static(
        key="stable-capture", name="Stable Capture", entity_kind="contact"
    )
    crm.segments.add_member(segment.id, EntityReference("contact", ada.id))
    crm.campaigns.attach_segment_source(campaign.id, segment.id)
    assert crm.campaigns.members(campaign.id).total == 0
    assert crm.campaigns.audience_count(campaign.id) == 1

    payload = [
        _record(ada.id),
        _record(grace.id),
        _record(ada.id),
        {"entity_kind": "contact", "entity_id": "bad-uuid"},
        _record(UUID(int=320060000)),
    ]
    encoded = {
        "json": lambda: JSONReader(io.StringIO(json.dumps(payload))),
        "jsonl": lambda: _jsonl(payload),
        "csv": lambda: _csv(payload),
    }[source_format]

    observed: list[DomainEvent] = []
    stable_harness.bus.subscribe("campaign.member_added", observed.append)

    first = import_campaign_members(
        crm.campaigns, campaign.id, encoded(), source="Trusted File"
    )
    assert first.as_dict() == {
        "rows_read": 5,
        "rows_created": 2,
        "rows_updated": 0,
        "rows_skipped": 3,
        "duplicates": 1,
        "validation_errors": 2,
    }
    assert len(observed) == 2
    assert all(event.aggregate_id == str(campaign.id) for event in observed)

    reopened = stable_harness.crm()
    assert reopened.campaigns.members(campaign.id).total == 2
    assert reopened.campaigns.audience_count(campaign.id) == 2
    assert reopened.campaigns.segment_sources(campaign.id).total == 1

    replay = import_campaign_members(
        reopened.campaigns, campaign.id,
        _csv([_record(ada.id), _record(grace.id)]),
    )
    assert replay.rows_created == 0
    assert replay.rows_skipped == 2
    assert replay.duplicates == 2
    assert len(observed) == 2

    expected = {str(ada.id), str(grace.id)}
    outputs: dict[str, list[dict[str, object]]] = {}
    for format in ("csv", "json", "jsonl"):
        dest = io.StringIO()
        count = export_campaign_records(
            reopened.campaigns, campaign.id, dest, kind="audience",
            format=format, page_size=1,
        )
        assert count == 2
        dest.seek(0)
        if format == "csv":
            records = list(csv.DictReader(dest))
        elif format == "json":
            records = json.load(dest)
        else:
            records = [json.loads(line) for line in dest if line.strip()]
        assert {item["entity_id"] for item in records} == expected
        assert all(set(item) == {"campaign_id", "entity_kind", "entity_id"} for item in records)
        outputs[format] = records
    assert outputs["csv"] == outputs["json"] == outputs["jsonl"]

    source_out = io.StringIO()
    assert export_campaign_records(
        reopened.campaigns, campaign.id, source_out,
        kind="sources", format="jsonl", page_size=1,
    ) == 1
    source_record = json.loads(source_out.getvalue())
    assert source_record["member_count"] == 1
    assert "Privacy Ada" not in source_out.getvalue()
    assert "Privacy Grace" not in source_out.getvalue()

    direct_out = io.StringIO()
    assert export_campaign_records(
        reopened.campaigns, campaign.id, direct_out,
        kind="direct", format="csv", page_size=1,
    ) == 2
    assert {row["source"] for row in csv.DictReader(
        io.StringIO(direct_out.getvalue())
    )} == {"trusted file"}
    assert "Privacy Ada" not in direct_out.getvalue()


def test_stable_adapter_rejected_mutations_never_advance_revision_or_events(
    stable_harness: StableHarness,
) -> None:
    crm = stable_harness.crm()
    contact = crm.contacts.create(display_name="Revision")
    campaign = crm.campaigns.create(key="stable-errors", name="Original")
    observed: list[DomainEvent] = []
    for type_name in ("campaign.updated", "campaign.member_added"):
        stable_harness.bus.subscribe(type_name, observed.append)

    changed = crm.campaigns.update(
        campaign.id, CampaignUpdate(name="Updated"), expected_revision=1
    )
    assert changed.revision == 2
    assert len(observed) == 1

    with pytest.raises(ConflictError) as caught:
        crm.campaigns.update(
            campaign.id, CampaignUpdate(name="Lost"), expected_revision=1
        )
    assert caught.value.code == "campaign.revision.conflict"
    assert crm.campaigns.get(campaign.id).name == "Updated"
    assert crm.campaigns.get(campaign.id).revision == 2
    assert len(observed) == 1

    archived = crm.campaigns.archive(campaign.id, expected_revision=2)
    assert archived.revision == 3
    with pytest.raises(InvalidStateError) as denied:
        crm.campaigns.add_member(
            campaign.id, EntityReference("contact", contact.id)
        )
    assert denied.value.code == "campaign.archived"
    assert stable_harness.crm().campaigns.members(campaign.id).total == 0
    assert len(observed) == 1
