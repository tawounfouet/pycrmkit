"""LOT-31-008 - qualified Campaign export schemas, pagination, privacy and failure.

No snapshot isolation or spreadsheet-formula protection is implicitly claimed.
"""
from __future__ import annotations

import csv
import io
import json

import pytest

from examples.data_operations.campaign_csv_spreadsheet_guard import (
    validate_campaign_csv_for_spreadsheet,
)
from pycrmkit import CRM
from pycrmkit.campaigns import export_campaign_records
from pycrmkit.core.references import EntityReference
from pycrmkit.segments import SegmentMode

FIELDS = {
    "direct": ("campaign_id", "entity_kind", "entity_id", "source", "added_at"),
    "audience": ("campaign_id", "entity_kind", "entity_id"),
    "sources": (
        "campaign_id", "segment_id", "segment_revision", "entity_kind",
        "attached_at", "captured_at", "member_count",
    ),
}


def _read(stream: io.StringIO, kind: str, format: str) -> list[dict[str, object]]:
    stream.seek(0)
    if format == "csv":
        reader = csv.DictReader(stream)
        assert tuple(reader.fieldnames or ()) == FIELDS[kind]
        return list(reader)
    if format == "json":
        return json.load(stream)
    return [json.loads(line) for line in stream]


@pytest.fixture(scope="module")
def populated() -> tuple[CRM, object]:
    crm = CRM.memory(webhook_auto_delivery=False)
    campaign = crm.campaigns.create(key="rc-export-volume", name="Export")
    first = None
    for index in range(205):
        contact = crm.contacts.create(display_name=f"Private Name {index}")
        ref = EntityReference("contact", contact.id)
        crm.campaigns.add_member(campaign.id, ref, source="approved")
        if first is None:
            first = ref
    assert first is not None
    segment = crm.segments.create(
        key="rc-export-capture", name="Capture", entity_kind="contact",
        mode=SegmentMode.STATIC,
    )
    crm.segments.add_members(segment.id, (first,))
    crm.campaigns.attach_segment_source(campaign.id, segment.id)
    return crm, campaign.id


@pytest.mark.parametrize("kind", ["direct", "audience", "sources"])
def test_all_formats_exact_parity_and_field_allowlist(
    populated: tuple[CRM, object], kind: str,
) -> None:
    crm, cid = populated
    results: dict[str, list[dict[str, str]]] = {}
    for format in ("csv", "json", "jsonl"):
        stream = io.StringIO()
        count = export_campaign_records(
            crm.campaigns, cid, stream, kind=kind, format=format, page_size=50
        )
        rows = _read(stream, kind, format)
        assert count == len(rows) == (1 if kind == "sources" else 205)
        for row in rows:
            assert tuple(row) == FIELDS[kind]
            assert not {"actor_id", "email", "phone", "subject",
                        "body", "metadata", "access_token"} & row.keys()
            assert "Private Name" not in str(row)
        results[format] = [
            {key: str(value) for key, value in row.items()} for row in rows
        ]
    assert results["csv"] == results["json"] == results["jsonl"]


@pytest.mark.parametrize("kind", ["direct", "audience", "sources"])
@pytest.mark.parametrize("format", ["csv", "json", "jsonl"])
def test_empty_and_single_result(kind: str, format: str) -> None:
    crm = CRM.memory(webhook_auto_delivery=False)
    campaign = crm.campaigns.create(
        key=f"rc-export-{kind}-{format}", name="Empty",
    )
    empty = io.StringIO()
    assert export_campaign_records(
        crm.campaigns, campaign.id, empty, kind=kind, format=format,
    ) == 0
    assert _read(empty, kind, format) == []
    contact = crm.contacts.create(display_name="Single")
    ref = EntityReference("contact", contact.id)
    if kind == "sources":
        segment = crm.segments.create(
            key="rc-export-single-segment", name="Segment",
            entity_kind="contact", mode=SegmentMode.STATIC,
        )
        crm.segments.add_members(segment.id, (ref,))
        crm.campaigns.attach_segment_source(campaign.id, segment.id)
    else:
        crm.campaigns.add_member(campaign.id, ref)
    one = io.StringIO()
    assert export_campaign_records(
        crm.campaigns, campaign.id, one, kind=kind, format=format,
    ) == 1
    assert tuple(_read(one, kind, format)[0]) == FIELDS[kind]


@pytest.mark.parametrize("page_size", [1, 50, 100, 200])
def test_large_export_requests_bounded_pages(
    populated: tuple[CRM, object], page_size: int,
) -> None:
    crm, cid = populated

    class RecordingFacade:
        def __init__(self) -> None:
            self.offsets: list[int] = []

        def get(self, campaign_id: object) -> object:
            return crm.campaigns.get(campaign_id)

        def members(self, campaign_id: object, page: object) -> object:
            assert page.limit == page_size
            self.offsets.append(page.offset)
            return crm.campaigns.members(campaign_id, page)

    facade = RecordingFacade()
    result = io.StringIO()
    assert export_campaign_records(
        facade, cid, result, kind="direct",
        format="jsonl", page_size=page_size,
    ) == 205
    rows = _read(result, "direct", "jsonl")
    assert len({row["entity_id"] for row in rows}) == 205
    assert facade.offsets == list(range(0, 205, page_size))


def test_mutating_offset_pages_do_not_form_a_snapshot() -> None:
    crm = CRM.memory(webhook_auto_delivery=False)
    campaign = crm.campaigns.create(key="rc-churn", name="Churn")
    for index in range(3):
        contact = crm.contacts.create(display_name=f"Churn {index}")
        crm.campaigns.add_member(
            campaign.id, EntityReference("contact", contact.id)
        )
    initial = {
        str(m.entity.id) for m in crm.campaigns.members(campaign.id).items
    }
    assert len(initial) == 3

    class ChurnFacade:
        def __init__(self) -> None:
            self.calls = 0

        def get(self, campaign_id: object) -> object:
            return crm.campaigns.get(campaign_id)

        def members(self, campaign_id: object, page: object) -> object:
            result = crm.campaigns.members(campaign_id, page)
            self.calls += 1
            if self.calls == 1:
                crm.campaigns.remove_member(
                    campaign_id, result.items[0].entity,
                )
            return result

    result = io.StringIO()
    assert export_campaign_records(
        ChurnFacade(), campaign.id, result,
        kind="direct", format="json", page_size=1,
    ) == 2
    exported = {row["entity_id"] for row in _read(result, "direct", "json")}
    remaining = {
        str(m.entity.id) for m in crm.campaigns.members(campaign.id).items
    }
    assert exported != initial
    assert exported != remaining  # It contains a member now deleted.


@pytest.mark.parametrize(
    "source", ["=1+1", "+1+1", "-1+1", "@SUM(1,1)", "\t=2+2", "＝3+3"]
)
def test_csv_formula_sources_fail_host_spreadsheet_guard(source: str) -> None:
    crm = CRM.memory(webhook_auto_delivery=False)
    contact = crm.contacts.create(display_name="Secret Name")
    campaign = crm.campaigns.create(key="rc-formula-risk", name="Formula")
    crm.campaigns.add_member(
        campaign.id, EntityReference("contact", contact.id),
        source=source, metadata={"access_token": "NEVER-EXPORT-ME"},
    )
    out = io.StringIO()
    assert export_campaign_records(
        crm.campaigns, campaign.id, out, kind="direct", format="csv",
    ) == 1
    assert "NEVER-EXPORT-ME" not in out.getvalue()
    assert _read(out, "direct", "csv")[0]["source"].startswith(
        ("=", "+", "-", "@")
    )
    with pytest.raises(ValueError, match="spreadsheet formula risk"):
        validate_campaign_csv_for_spreadsheet(io.StringIO(out.getvalue()))


def test_host_spreadsheet_guard_accepts_known_nonformula_values(
    populated: tuple[CRM, object],
) -> None:
    crm, cid = populated
    out = io.StringIO()
    assert export_campaign_records(
        crm.campaigns, cid, out, kind="direct", format="csv",
    ) == 205
    assert validate_campaign_csv_for_spreadsheet(
        io.StringIO(out.getvalue())
    ) == 205


@pytest.mark.parametrize("format", ["csv", "json", "jsonl"])
def test_partial_destination_failure_is_not_reported_as_success(format: str) -> None:
    crm = CRM.memory(webhook_auto_delivery=False)
    contact = crm.contacts.create(display_name="Write failure")
    campaign = crm.campaigns.create(key="rc-write-fail", name="Failure")
    crm.campaigns.add_member(
        campaign.id, EntityReference("contact", contact.id)
    )

    class FailingDestination(io.StringIO):
        def __init__(self) -> None:
            super().__init__()
            self.writes = 0

        def write(self, value: str) -> int:
            self.writes += 1
            if self.writes > 1:
                raise OSError("simulated destination failure")
            return super().write(value)

    output = FailingDestination()
    with pytest.raises(OSError, match="destination failure"):
        export_campaign_records(
            crm.campaigns, campaign.id, output,
            kind="direct", format=format,
        )
    assert output.getvalue()  # A partial file must be quarantined.
