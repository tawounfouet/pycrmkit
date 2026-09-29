from __future__ import annotations

from io import StringIO

from pycrmkit import CRM
from pycrmkit.exporters import CSVExporter, JSONLExporter
from pycrmkit.importers import IterableReader
from pycrmkit.segments import (
    Predicate,
    QueryOperator,
    import_segment_members,
    iter_segment_membership_records,
)


def test_segment_membership_import_and_export_bridge_generic_data_operations() -> None:
    crm = CRM.memory(webhook_auto_delivery=False)
    ada = crm.contacts.create(display_name="Ada")
    grace = crm.contacts.create(display_name="Grace")
    segment = crm.segments.create_static(
        key="campaign-wave",
        name="Campaign Wave",
        entity_kind="contact",
    )

    report = import_segment_members(
        crm.segments,
        segment.id,
        IterableReader(
            (
                {"entity_id": str(ada.id), "entity_kind": "contact"},
                {"entity_id": "not-a-uuid", "entity_kind": "contact"},
                {"entity_id": str(grace.id)},
            )
        ),
    )

    assert report.rows_read == 3
    assert report.rows_created == 2
    assert report.rows_skipped == 1
    assert report.validation_errors == 1

    records = tuple(
        iter_segment_membership_records(
            crm.segments,
            segment.id,
            page_size=1,
        )
    )
    assert {record["entity_id"] for record in records} == {
        str(ada.id),
        str(grace.id),
    }
    assert {record["segment_mode"] for record in records} == {"static"}

    csv_output = StringIO()
    jsonl_output = StringIO()
    assert CSVExporter(csv_output).write(records) == 2
    assert JSONLExporter(jsonl_output).write(records) == 2
    assert "segment_id" in csv_output.getvalue()
    assert len(jsonl_output.getvalue().strip().splitlines()) == 2


def test_dynamic_export_is_live_while_snapshot_export_is_stable() -> None:
    crm = CRM.memory(webhook_auto_delivery=False)
    ada = crm.contacts.create(display_name="Ada", source="LinkedIn")
    dynamic = crm.segments.create_dynamic(
        key="linkedin",
        name="LinkedIn",
        entity_kind="contact",
        query=Predicate(
            "source",
            QueryOperator.EQ,
            "linkedin",
        ),
    )
    snapshot = crm.segments.snapshot(
        dynamic.id,
        key="linkedin-frozen",
        name="LinkedIn Frozen",
    )
    grace = crm.contacts.create(display_name="Grace", source="LinkedIn")

    live_ids = {
        row["entity_id"]
        for row in iter_segment_membership_records(
            crm.segments,
            dynamic.id,
        )
    }
    snapshot_ids = {
        row["entity_id"]
        for row in iter_segment_membership_records(
            crm.segments,
            snapshot.id,
        )
    }

    assert live_ids == {str(ada.id), str(grace.id)}
    assert snapshot_ids == {str(ada.id)}
