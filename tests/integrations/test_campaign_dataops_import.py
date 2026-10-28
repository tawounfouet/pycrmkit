"""Campaign DataOps integration contracts across formats and facade boundaries."""

from __future__ import annotations

import csv
import io
import json
from uuid import uuid4

import pytest

from pycrmkit import CRM
from pycrmkit.campaigns import (
    import_campaign_members,
    iter_campaign_audience_records,
)
from pycrmkit.core.references import EntityReference
from pycrmkit.exceptions import RepositoryError, ValidationError
from pycrmkit.importers import (
    CSVReader,
    FieldMapping,
    ImportStage,
    IterableReader,
    JSONLReader,
    JSONReader,
    RecordMapper,
)
from pycrmkit.segments import SegmentMode


def _row(contact_id: object) -> dict[str, object]:
    return {"entity_kind": "contact", "entity_id": str(contact_id)}


def test_campaign_import_replay_duplicate_and_missing_entity_reports() -> None:
    crm = CRM.memory(webhook_auto_delivery=False)
    ada = crm.contacts.create(display_name="Ada")
    grace = crm.contacts.create(display_name="Grace")
    campaign = crm.campaigns.create(key="campaign-import", name="Import")

    records = [
        _row(ada.id),
        _row(ada.id),
        _row(uuid4()),  # CRM entity is missing despite valid UUID.
        {"entity_kind": "contact", "entity_id": "invalid-uuid"},
        _row(grace.id),
    ]
    report = import_campaign_members(
        crm.campaigns,
        campaign.id,
        IterableReader(records),
        source="trusted-file",
    )
    assert report.as_dict() == {
        "rows_read": 5,
        "rows_created": 2,
        "rows_updated": 0,
        "rows_skipped": 3,
        "duplicates": 1,
        "validation_errors": 2,
    }
    assert [item.row_number for item in report.row_results] == [1, 2, 3, 4, 5]
    assert report.row_results[1].duplicate is True
    assert [(error.row_number, error.stage) for error in report.errors] == [
        (3, ImportStage.PERSIST),
        (4, ImportStage.VALIDATE),
    ]
    assert crm.campaigns.members(campaign.id).total == 2

    replay = import_campaign_members(
        crm.campaigns,
        campaign.id,
        IterableReader([_row(ada.id), _row(grace.id)]),
    )
    assert replay.rows_created == 0
    assert replay.duplicates == 2
    assert replay.rows_skipped == 2
    assert crm.campaigns.members(campaign.id).total == 2


def test_campaign_import_segment_capture_is_not_a_direct_duplicate() -> None:
    crm = CRM.memory(webhook_auto_delivery=False)
    person = crm.contacts.create(display_name="Captured")
    campaign = crm.campaigns.create(key="captured", name="Captured")
    segment = crm.segments.create(
        key="seed-captured", name="Seed", entity_kind="contact",
        mode=SegmentMode.STATIC,
    )
    crm.segments.add_members(
        segment.id, (EntityReference("contact", person.id),)
    )
    crm.campaigns.attach_segment_source(campaign.id, segment.id)
    assert crm.campaigns.audience_count(campaign.id) == 1
    assert crm.campaigns.members(campaign.id).total == 0

    imported = import_campaign_members(
        crm.campaigns,
        campaign.id,
        IterableReader([_row(person.id)]),
    )
    assert imported.rows_created == 1
    assert imported.duplicates == 0
    assert crm.campaigns.members(campaign.id).total == 1
    assert crm.campaigns.audience_count(campaign.id) == 1
    assert crm.campaigns.segment_sources(campaign.id).total == 1


@pytest.mark.parametrize("format", ["csv", "json", "jsonl"])
def test_campaign_import_accepts_existing_portable_readers(format: str) -> None:
    crm = CRM.memory(webhook_auto_delivery=False)
    contact = crm.contacts.create(display_name="Format")
    campaign = crm.campaigns.create(key="format-test", name="Format")
    data = [_row(contact.id)]
    if format == "csv":
        stream = io.StringIO()
        writer = csv.DictWriter(
            stream, fieldnames=["entity_kind", "entity_id"]
        )
        writer.writeheader()
        writer.writerows(data)
        stream.seek(0)
        reader = CSVReader(stream)
    elif format == "json":
        reader = JSONReader(io.StringIO(json.dumps(data)))
    else:
        reader = JSONLReader(io.StringIO(json.dumps(data[0]) + "\n"))

    report = import_campaign_members(crm.campaigns, campaign.id, reader)
    assert report.rows_created == 1
    assert crm.campaigns.members(campaign.id).total == 1


def test_campaign_import_respects_explicit_record_mapping() -> None:
    crm = CRM.memory(webhook_auto_delivery=False)
    person = crm.contacts.create(display_name="Mapped")
    campaign = crm.campaigns.create(key="mapped-test", name="Mapped")
    mapping = RecordMapper((
        FieldMapping("type", "entity_kind"),
        FieldMapping("uuid", "entity_id"),
    ))
    report = import_campaign_members(
        crm.campaigns,
        campaign.id,
        IterableReader([{"type": "contact", "uuid": str(person.id)}]),
        mapper=mapping,
    )
    assert report.rows_created == 1


def test_campaign_import_limit_is_checked_before_any_write() -> None:
    crm = CRM.memory(webhook_auto_delivery=False)
    campaign = crm.campaigns.create(key="limited", name="Limited")
    rows = [_row(uuid4()), _row(uuid4())]
    with pytest.raises(ValidationError) as error:
        import_campaign_members(
            crm.campaigns,
            campaign.id,
            IterableReader(rows),
            max_rows=1,
        )
    assert error.value.code == "campaign.import.row_limit"
    assert crm.campaigns.members(campaign.id).total == 0

    with pytest.raises(ValidationError):
        import_campaign_members(
            crm.campaigns,
            campaign.id,
            IterableReader([]),
            max_rows=1001,
        )


def test_campaign_import_archived_campaign_is_fatal_before_row_processing() -> None:
    crm = CRM.memory(webhook_auto_delivery=False)
    campaign = crm.campaigns.create(key="archived-import", name="Archived")
    campaign = crm.campaigns.archive(
        campaign.id, expected_revision=campaign.revision
    )
    with pytest.raises(Exception) as caught:
        import_campaign_members(
            crm.campaigns,
            campaign.id,
            IterableReader([_row(uuid4())]),
        )
    assert getattr(caught.value, "code", None) == "campaign.archived"
    assert crm.campaigns.members(campaign.id).total == 0


def test_campaign_import_propagates_repository_failure_with_partial_commits() -> None:
    crm = CRM.memory(webhook_auto_delivery=False)
    first = crm.contacts.create(display_name="First")
    second = crm.contacts.create(display_name="Second")
    campaign = crm.campaigns.create(key="partial-failure", name="Partial")

    class FaultyFacade:
        def __init__(self) -> None:
            self.counter = 0

        def get(self, campaign_id: object) -> object:
            return crm.campaigns.get(campaign_id)

        def members(self, campaign_id: object, page: object = None) -> object:
            return crm.campaigns.members(campaign_id, page)

        def add_member(self, campaign_id: object, entity: object, **kwargs: object) -> object:
            self.counter += 1
            if self.counter == 2:
                raise RepositoryError(
                    "simulated storage outage", code="storage.simulated"
                )
            return crm.campaigns.add_member(campaign_id, entity, **kwargs)

    faulty = FaultyFacade()
    with pytest.raises(RepositoryError):
        import_campaign_members(
            faulty,
            campaign.id,
            IterableReader([_row(first.id), _row(second.id)]),
        )
    assert crm.campaigns.members(campaign.id).total == 1


def test_campaign_import_retain_row_results_false_keeps_counters() -> None:
    crm = CRM.memory(webhook_auto_delivery=False)
    campaign = crm.campaigns.create(key="summary", name="Summary")
    report = import_campaign_members(
        crm.campaigns,
        campaign.id,
        IterableReader([{"entity_kind": "contact", "entity_id": "bad"}]),
        retain_row_results=False,
    )
    assert report.validation_errors == 1
    assert report.rows_skipped == 1
    assert report.row_results == []
    assert report.errors == ()


def test_campaign_audience_export_excludes_snapshot_provenance() -> None:
    crm = CRM.memory(webhook_auto_delivery=False)
    person = crm.contacts.create(display_name="Audience")
    campaign = crm.campaigns.create(key="audience-only", name="Audience")
    crm.campaigns.add_member(
        campaign.id, EntityReference("contact", person.id)
    )
    rows = list(iter_campaign_audience_records(crm.campaigns, campaign.id))
    assert rows == [{
        "campaign_id": str(campaign.id),
        "entity_kind": "contact",
        "entity_id": str(person.id),
    }]
