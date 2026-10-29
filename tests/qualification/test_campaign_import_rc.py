"""LOT-31-007 - Campaign import replay, recovery and failure qualification.

These scenarios exercise the shipped Python DataOps API, not a file-upload HTTP
endpoint. Each accepted member commits independently; replay is deduplicated by
existing DIRECT membership. The tests never claim batch atomicity/exactly-once.
"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Mapping

import pytest

from pycrmkit import CRM
from pycrmkit.campaigns import import_campaign_members
from pycrmkit.core.references import EntityReference
from pycrmkit.exceptions import DuplicateError, RepositoryError, ValidationError
from pycrmkit.importers import (
    CSVReader,
    FieldMapping,
    ImportRow,
    ImportStage,
    IterableReader,
    JSONLReader,
    JSONReader,
    RecordMapper,
)
from pycrmkit.segments import SegmentMode


def _row(entity_id: object) -> dict[str, object]:
    return {"entity_kind": "contact", "entity_id": str(entity_id)}


def _reader(format: str, rows: list[dict[str, object]]) -> object:
    if format == "csv":
        stream = io.StringIO()
        writer = csv.DictWriter(
            stream, fieldnames=["entity_kind", "entity_id"], extrasaction="ignore"
        )
        writer.writeheader()
        writer.writerows(rows)
        stream.seek(0)
        return CSVReader(stream)
    if format == "json":
        return JSONReader(io.StringIO(json.dumps(rows)))
    if format == "jsonl":
        return JSONLReader(
            io.StringIO("".join(json.dumps(row) + "\n" for row in rows))
        )
    raise AssertionError(format)


@pytest.mark.parametrize("format", ["csv", "json", "jsonl"])
def test_shared_corpus_reports_and_replays_without_new_direct_members(
    format: str,
) -> None:
    crm = CRM.memory(webhook_auto_delivery=False)
    first = crm.contacts.create(display_name="First")
    second = crm.contacts.create(display_name="Second")
    campaign = crm.campaigns.create(key="rc-replay-" + format, name="Replay")
    rows = [
        _row(first.id),
        _row(first.id),
        {"entity_kind": "contact", "entity_id": "not-a-uuid"},
        _row(second.id),
    ]
    first_run = import_campaign_members(
        crm.campaigns, campaign.id, _reader(format, rows)
    )
    assert first_run.as_dict() == {
        "rows_read": 4,
        "rows_created": 2,
        "rows_updated": 0,
        "rows_skipped": 2,
        "duplicates": 1,
        "validation_errors": 1,
    }
    assert [row.row_number for row in first_run.row_results] == [1, 2, 3, 4]
    assert first_run.row_results[1].duplicate is True
    assert [
        (error.row_number, error.code, error.stage)
        for error in first_run.errors
    ] == [
        (3, "campaign.import.entity_id.invalid", ImportStage.VALIDATE),
    ]
    snapshot = crm.campaigns.members(campaign.id)
    assert snapshot.total == 2

    replay = import_campaign_members(
        crm.campaigns, campaign.id, _reader(format, rows)
    )
    assert replay.as_dict() == {
        "rows_read": 4,
        "rows_created": 0,
        "rows_updated": 0,
        "rows_skipped": 4,
        "duplicates": 3,
        "validation_errors": 1,
    }
    assert crm.campaigns.members(campaign.id).items == snapshot.items


@pytest.mark.parametrize("format", ["csv", "json", "jsonl"])
def test_source_field_mapping_is_identical_across_formats(format: str) -> None:
    crm = CRM.memory(webhook_auto_delivery=False)
    person = crm.contacts.create(display_name="Mapped")
    campaign = crm.campaigns.create(key="rc-mapping-" + format, name="Mapping")
    raw = [{"entity_kind": "contact", "entity_id": str(person.id)}]
    mapping = RecordMapper((
        FieldMapping("entity_kind", "entity_kind"),
        FieldMapping("entity_id", "entity_id"),
    ))
    report = import_campaign_members(
        crm.campaigns, campaign.id, _reader(format, raw), mapper=mapping
    )
    assert report.rows_created == 1
    assert crm.campaigns.members(campaign.id).total == 1


def test_mapping_failure_is_row_local_with_precise_stage() -> None:
    crm = CRM.memory(webhook_auto_delivery=False)
    contact = crm.contacts.create(display_name="Mapped")
    campaign = crm.campaigns.create(key="mapping-row-error", name="Mapping")

    class RejectSpecificRow:
        def map(self, row: ImportRow) -> ImportRow:
            if row.number == 2:
                raise ValidationError(
                    "mapping rejected row", code="test.mapping.rejected"
                )
            return row

    report = import_campaign_members(
        crm.campaigns,
        campaign.id,
        IterableReader([_row(contact.id), _row(contact.id)]),
        mapper=RejectSpecificRow(),
    )
    assert report.as_dict() == {
        "rows_read": 2,
        "rows_created": 1,
        "rows_updated": 0,
        "rows_skipped": 1,
        "duplicates": 0,
        "validation_errors": 1,
    }
    assert [(e.row_number, e.stage, e.code) for e in report.errors] == [
        (2, ImportStage.MAP, "test.mapping.rejected"),
    ]


def test_limit_1000_is_accepted_and_1001_is_preflight_rejected() -> None:
    crm = CRM.memory(webhook_auto_delivery=False)
    one = crm.contacts.create(display_name="One")
    another = crm.contacts.create(display_name="Another")
    campaign = crm.campaigns.create(key="rc-1000", name="Boundaries")
    rows = [_row(one.id)] * 999 + [_row(another.id)]

    accepted = import_campaign_members(
        crm.campaigns, campaign.id, IterableReader(rows), max_rows=1000,
        retain_row_results=False,
    )
    assert accepted.rows_read == 1000
    assert accepted.rows_created == 2
    assert accepted.duplicates == 998
    assert accepted.rows_skipped == 998
    assert accepted.row_results == []
    assert crm.campaigns.members(campaign.id).total == 2

    new_campaign = crm.campaigns.create(key="rc-1001", name="Rejected")
    with pytest.raises(ValidationError) as error:
        import_campaign_members(
            crm.campaigns,
            new_campaign.id,
            IterableReader(rows + [_row(one.id)]),
            max_rows=1000,
        )
    assert error.value.code == "campaign.import.row_limit"
    assert crm.campaigns.members(new_campaign.id).total == 0


@pytest.mark.parametrize(
    ("reader", "expected_code"),
    [
        (
            lambda valid: JSONReader(io.StringIO(
                json.dumps([valid])[:-1] + ","
            )),
            "import.json.syntax.invalid",
        ),
        (
            lambda valid: JSONLReader(io.StringIO(
                json.dumps(valid) + "\n{broken json}\n"
            )),
            "import.jsonl.syntax.invalid",
        ),
        (
            lambda valid: CSVReader(io.StringIO(
                "entity_kind,entity_id\n"
                + f"{valid['entity_kind']},{valid['entity_id']}\n"
                + "contact,extra,unexpected\n"
            )),
            "import.csv.columns.extra",
        ),
    ],
    ids=["json-malformed", "jsonl-malformed", "csv-extra-column"],
)
def test_late_reader_parse_failure_prevents_any_writes(
    reader: object, expected_code: str,
) -> None:
    crm = CRM.memory(webhook_auto_delivery=False)
    contact = crm.contacts.create(display_name="Valid")
    campaign = crm.campaigns.create(key="rc-invalid-file", name="Invalid")
    observed: list[str] = []
    crm.events.subscribe(
        "campaign.member_added", lambda event: observed.append(str(event.type))
    )
    with pytest.raises(ValidationError) as error:
        import_campaign_members(
            crm.campaigns, campaign.id, reader(_row(contact.id))
        )
    assert error.value.code == expected_code
    assert crm.campaigns.members(campaign.id).total == 0
    assert observed == []


def test_early_storage_failure_partial_commit_then_replay_from_original() -> None:
    crm = CRM.memory(webhook_auto_delivery=False)
    first = crm.contacts.create(display_name="First")
    second = crm.contacts.create(display_name="Second")
    third = crm.contacts.create(display_name="Third")
    campaign = crm.campaigns.create(key="rc-partial-recovery", name="Recovery")
    rows = [_row(first.id), _row(second.id), _row(third.id)]
    observed: list[str] = []
    crm.events.subscribe(
        "campaign.member_added", lambda event: observed.append(str(event.type))
    )

    class FaultingFacade:
        attempts = 0

        def get(self, campaign_id: object) -> object:
            return crm.campaigns.get(campaign_id)

        def members(self, campaign_id: object, page: object = None) -> object:
            return crm.campaigns.members(campaign_id, page)

        def add_member(
            self, campaign_id: object, entity: object,
            **kwargs: object,
        ) -> object:
            self.attempts += 1
            if self.attempts == 2:
                raise RepositoryError(
                    "injected storage outage", code="storage.injected"
                )
            return crm.campaigns.add_member(campaign_id, entity, **kwargs)

    facade = FaultingFacade()
    with pytest.raises(RepositoryError) as error:
        import_campaign_members(
            facade, campaign.id, IterableReader(rows)
        )
    assert error.value.code == "storage.injected"
    assert facade.attempts == 2
    assert crm.campaigns.members(campaign.id).total == 1
    assert observed == ["campaign.member_added"]

    recovered = import_campaign_members(
        crm.campaigns, campaign.id, IterableReader(rows)
    )
    assert recovered.as_dict() == {
        "rows_read": 3,
        "rows_created": 2,
        "rows_updated": 0,
        "rows_skipped": 1,
        "duplicates": 1,
        "validation_errors": 0,
    }
    assert recovered.row_results[0].duplicate is True
    assert crm.campaigns.members(campaign.id).total == 3
    assert observed == ["campaign.member_added"] * 3

    repeated = import_campaign_members(
        crm.campaigns, campaign.id, IterableReader(rows)
    )
    assert repeated.rows_created == 0
    assert repeated.duplicates == 3
    assert observed == ["campaign.member_added"] * 3


def test_concurrent_unique_conflict_propagates_and_replay_does_not_guess() -> None:
    crm = CRM.memory(webhook_auto_delivery=False)
    person = crm.contacts.create(display_name="Potential race")
    campaign = crm.campaigns.create(key="rc-race", name="Race")

    class InjectUniqueConflict:
        def get(self, campaign_id: object) -> object:
            return crm.campaigns.get(campaign_id)

        def members(self, campaign_id: object, page: object = None) -> object:
            return crm.campaigns.members(campaign_id, page)

        def add_member(
            self, campaign_id: object, entity: object, **kwargs: object
        ) -> object:
            raise DuplicateError(
                "simulated competing transaction",
                code="campaign.member.duplicate",
            )

    with pytest.raises(DuplicateError) as error:
        import_campaign_members(
            InjectUniqueConflict(), campaign.id,
            IterableReader([_row(person.id)]),
        )
    assert error.value.code == "campaign.member.duplicate"
    assert crm.campaigns.members(campaign.id).total == 0
    clean = import_campaign_members(
        crm.campaigns, campaign.id, IterableReader([_row(person.id)])
    )
    assert clean.rows_created == 1
    assert clean.duplicates == 0


def test_snapshot_membership_not_modified_by_direct_import_and_replay() -> None:
    crm = CRM.memory(webhook_auto_delivery=False)
    person = crm.contacts.create(display_name="Segment captured")
    campaign = crm.campaigns.create(key="rc-capture", name="Capture")
    segment = crm.segments.create(
        key="rc-segment-source", name="Segment", entity_kind="contact",
        mode=SegmentMode.STATIC,
    )
    crm.segments.add_members(
        segment.id, (EntityReference("contact", person.id),)
    )
    crm.campaigns.attach_segment_source(campaign.id, segment.id)
    original_sources = crm.campaigns.segment_sources(campaign.id)
    assert crm.campaigns.members(campaign.id).total == 0
    assert crm.campaigns.audience_count(campaign.id) == 1

    first = import_campaign_members(
        crm.campaigns, campaign.id, IterableReader([_row(person.id)])
    )
    second = import_campaign_members(
        crm.campaigns, campaign.id, IterableReader([_row(person.id)])
    )
    assert first.rows_created == 1
    assert second.rows_created == 0
    assert second.duplicates == 1
    assert crm.campaigns.members(campaign.id).total == 1
    assert crm.campaigns.audience_count(campaign.id) == 1
    assert crm.campaigns.segment_sources(campaign.id).items == original_sources.items


def test_row_level_missing_uuid_and_existing_uuid_have_distinct_outcomes() -> None:
    crm = CRM.memory(webhook_auto_delivery=False)
    contact = crm.contacts.create(display_name="Known")
    campaign = crm.campaigns.create(key="rc-missing", name="Missing")
    missing = "00000000-0000-4000-8000-000000070007"
    report = import_campaign_members(
        crm.campaigns, campaign.id,
        IterableReader([_row(missing), _row(contact.id)]),
    )
    assert report.rows_read == 2
    assert report.rows_created == 1
    assert report.rows_skipped == 1
    assert report.validation_errors == 1
    assert [(e.row_number, e.code, e.field) for e in report.errors] == [
        (1, "campaign.member.not_found", "entity_id"),
    ]
    assert crm.campaigns.members(campaign.id).total == 1
