"""LOT-32-005: stable Campaign DataOps replay, export and spreadsheet gate.

Preserve 1.2.0rc1 contracts. This suite does not claim batch transactions,
distributed idempotency, a point-in-time export, or automatic spreadsheet safety.
"""

from __future__ import annotations

import csv
import io
import json
import unicodedata
from os import replace

import pytest

from examples.data_operations.campaign_csv_spreadsheet_guard import (
    validate_campaign_csv_for_spreadsheet,
)
from pycrmkit import CRM
from pycrmkit.campaigns import export_campaign_records, import_campaign_members
from pycrmkit.core.references import EntityReference
from pycrmkit.exceptions import RepositoryError, ValidationError
from pycrmkit.importers import CSVReader, IterableReader, JSONLReader, JSONReader
from pycrmkit.segments import SegmentMode


def _row(entity_id: object) -> dict[str, object]:
    return {"entity_kind": "contact", "entity_id": str(entity_id)}


def _reader(format: str, rows: list[dict[str, object]]) -> object:
    if format == "csv":
        stream = io.StringIO()
        writer = csv.DictWriter(stream, fieldnames=("entity_kind", "entity_id"))
        writer.writeheader()
        writer.writerows(rows)
        stream.seek(0)
        return CSVReader(stream)
    if format == "json":
        return JSONReader(io.StringIO(json.dumps(rows)))
    if format == "jsonl":
        return JSONLReader(io.StringIO("".join(json.dumps(row) + "\n" for row in rows)))
    raise AssertionError(format)


def _export_rows(stream: io.StringIO, format: str) -> list[dict[str, object]]:
    stream.seek(0)
    if format == "csv":
        return list(csv.DictReader(stream))
    if format == "json":
        return json.load(stream)
    return [json.loads(line) for line in stream if line.strip()]


@pytest.mark.parametrize("format", ("csv", "json", "jsonl"))
def test_partial_commit_recovery_via_full_file_replay(format: str) -> None:
    crm = CRM.memory(webhook_auto_delivery=False)
    contacts = [crm.contacts.create(display_name=f"Recovery {number}") for number in range(3)]
    campaign = crm.campaigns.create(key=f"stable-replay-{format}", name="Replay")
    rows = [_row(contact.id) for contact in contacts]

    class FailingOnce:
        calls = 0

        def get(self, campaign_id: object) -> object:
            return crm.campaigns.get(campaign_id)

        def members(self, campaign_id: object, page: object = None) -> object:
            return crm.campaigns.members(campaign_id, page)

        def add_member(self, campaign_id: object, entity: object, **kwargs: object) -> object:
            self.calls += 1
            if self.calls == 2:
                raise RepositoryError("injected outage", code="storage.injected_failure")
            return crm.campaigns.add_member(campaign_id, entity, **kwargs)

    with pytest.raises(RepositoryError, match="injected outage"):
        import_campaign_members(
            FailingOnce(),
            campaign.id,
            _reader(format, rows),
            source="trusted-import",
        )
    assert crm.campaigns.members(campaign.id).total == 1

    recovered = import_campaign_members(
        crm.campaigns,
        campaign.id,
        _reader(format, rows),
        source="trusted-import",
    )
    assert recovered.as_dict() == {
        "rows_read": 3,
        "rows_created": 2,
        "rows_updated": 0,
        "rows_skipped": 1,
        "duplicates": 1,
        "validation_errors": 0,
    }
    assert crm.campaigns.members(campaign.id).total == 3

    repeated = import_campaign_members(crm.campaigns, campaign.id, _reader(format, rows))
    assert repeated.rows_created == 0
    assert repeated.duplicates == 3
    assert repeated.rows_skipped == 3
    assert {str(member.entity.id) for member in crm.campaigns.members(campaign.id).items} == {
        str(contact.id) for contact in contacts
    }


@pytest.mark.parametrize(
    ("format", "payload", "code"),
    (
        ("csv", "entity_kind,entity_kind\ncontact,contact\n", "import.csv.header.duplicate"),
        ("json", '[{"entity_kind": "contact"},', "import.json.syntax.invalid"),
        ("jsonl", '{"entity_kind":"contact"}\n{invalid-json}\n', "import.jsonl.syntax.invalid"),
    ),
)
def test_malformed_file_fails_preflight_without_partial_memberships(
    format: str,
    payload: str,
    code: str,
) -> None:
    crm = CRM.memory(webhook_auto_delivery=False)
    campaign = crm.campaigns.create(key=f"stable-malformed-{format}", name="Bad")
    stream = io.StringIO(payload)
    reader = {
        "csv": CSVReader,
        "json": JSONReader,
        "jsonl": JSONLReader,
    }[format](stream)
    with pytest.raises(ValidationError) as error:
        import_campaign_members(crm.campaigns, campaign.id, reader)
    assert error.value.code == code
    assert crm.campaigns.members(campaign.id).total == 0


@pytest.mark.parametrize("format", ("csv", "json", "jsonl"))
def test_1001_records_rejected_before_writes_across_formats(format: str) -> None:
    crm = CRM.memory(webhook_auto_delivery=False)
    contact = crm.contacts.create(display_name="Bounded")
    campaign = crm.campaigns.create(key=f"stable-limit-{format}", name="Limit")
    reader = _reader(format, [_row(contact.id) for _ in range(1001)])
    with pytest.raises(ValidationError) as error:
        import_campaign_members(crm.campaigns, campaign.id, reader)
    assert error.value.code == "campaign.import.row_limit"
    assert crm.campaigns.members(campaign.id).total == 0


def test_summary_mode_never_includes_untrusted_row_or_personal_data() -> None:
    crm = CRM.memory(webhook_auto_delivery=False)
    campaign = crm.campaigns.create(key="stable-minimized", name="Minimized")
    canary = "CONFIDENTIAL_ROW_VALUE_NEVER_REPORT"
    rows = [{"entity_kind": "contact", "entity_id": "not-a-uuid", "private_note": canary}]
    report = import_campaign_members(
        crm.campaigns,
        campaign.id,
        IterableReader(rows),
        retain_row_results=False,
    )
    assert report.as_dict() == {
        "rows_read": 1,
        "rows_created": 0,
        "rows_updated": 0,
        "rows_skipped": 1,
        "duplicates": 0,
        "validation_errors": 1,
    }
    assert report.row_results == []
    assert report.errors == ()
    assert canary not in repr(report)


@pytest.mark.parametrize("kind", ("direct", "audience", "sources"))
def test_stable_export_parity_and_provenance_privacy(kind: str) -> None:
    crm = CRM.memory(webhook_auto_delivery=False)
    contact = crm.contacts.create(display_name="PRIVATE_CONTACT_NAME")
    campaign = crm.campaigns.create(key=f"stable-export-{kind}", name="Export")
    ref = EntityReference("contact", contact.id)
    crm.campaigns.add_member(
        campaign.id,
        ref,
        source="customer-list",
        metadata={"token": "SECRET_METADATA_NEVER_EXPORT"},
    )
    segment = crm.segments.create(
        key=f"stable-export-segment-{kind}",
        name="Segment",
        entity_kind="contact",
        mode=SegmentMode.STATIC,
    )
    crm.segments.add_members(segment.id, (ref,))
    crm.campaigns.attach_segment_source(campaign.id, segment.id)

    outputs = {}
    for format in ("csv", "json", "jsonl"):
        stream = io.StringIO()
        count = export_campaign_records(
            crm.campaigns,
            campaign.id,
            stream,
            kind=kind,
            format=format,
            page_size=1,
        )
        assert count == 1
        content = stream.getvalue()
        assert "PRIVATE_CONTACT_NAME" not in content
        assert "SECRET_METADATA_NEVER_EXPORT" not in content
        rows = _export_rows(stream, format)
        assert len(rows) == 1
        assert not ({"email", "actor_id", "metadata", "recipient", "subject"} & rows[0].keys())
        outputs[format] = [{field: str(value) for field, value in row.items()} for row in rows]
    assert outputs["csv"] == outputs["json"] == outputs["jsonl"]
    if kind == "audience":
        assert set(outputs["csv"][0]) == {
            "campaign_id",
            "entity_kind",
            "entity_id",
        }
    elif kind == "direct":
        assert "source" in outputs["csv"][0]
    else:
        assert "member_count" in outputs["csv"][0]


@pytest.mark.parametrize(
    "formula",
    ("=1+1", "+1+1", "-1+1", "@SUM(1,1)", "\t=2+2", "＝3+3"),
)
def test_canonical_csv_is_not_spreadsheet_safe_by_default(formula: str) -> None:
    crm = CRM.memory(webhook_auto_delivery=False)
    contact = crm.contacts.create(display_name="Spreadsheet")
    campaign = crm.campaigns.create(key="stable-spreadsheet", name="Spreadsheet")
    crm.campaigns.add_member(
        campaign.id,
        EntityReference("contact", contact.id),
        source=formula,
    )
    output = io.StringIO()
    assert (
        export_campaign_records(
            crm.campaigns,
            campaign.id,
            output,
            kind="direct",
            format="csv",
        )
        == 1
    )
    # Canonical CSV stays unchanged for machine consumers; the HOST must deny
    # spreadsheet opening rather than silently changing the CRM source field.
    expected_source = unicodedata.normalize("NFKC", formula.strip()).casefold()
    assert _export_rows(output, "csv")[0]["source"] == expected_source
    with pytest.raises(ValueError, match="spreadsheet formula risk"):
        validate_campaign_csv_for_spreadsheet(io.StringIO(output.getvalue()))


def test_host_never_publishes_failed_spreadsheet_validation(tmp_path: object) -> None:
    crm = CRM.memory(webhook_auto_delivery=False)
    person = crm.contacts.create(display_name="Hidden")
    campaign = crm.campaigns.create(key="stable-publish", name="Publish")
    crm.campaigns.add_member(
        campaign.id,
        EntityReference("contact", person.id),
        source="=HYPERLINK(1)",
    )
    staging = tmp_path / "campaign.pending.csv"
    published = tmp_path / "campaign.published.csv"
    try:
        assert (
            export_campaign_records(
                crm.campaigns,
                campaign.id,
                staging,
                kind="direct",
                format="csv",
            )
            == 1
        )
        with staging.open("r", encoding="utf-8", newline="") as stream:
            with pytest.raises(ValueError, match="spreadsheet formula risk"):
                validate_campaign_csv_for_spreadsheet(stream)
        assert not published.exists()
    finally:
        staging.unlink(missing_ok=True)
    assert not staging.exists()
    assert not published.exists()

    # A separate safe CSV can be promoted only after its full validation.
    safe = crm.campaigns.create(key="stable-publish-safe", name="Safe")
    crm.campaigns.add_member(
        safe.id,
        EntityReference("contact", person.id),
        source="reviewed",
    )
    assert (
        export_campaign_records(
            crm.campaigns,
            safe.id,
            staging,
            kind="direct",
            format="csv",
        )
        == 1
    )
    assert (
        export_campaign_records(
            crm.campaigns,
            safe.id,
            staging,
            kind="direct",
            format="csv",
        )
        == 1
    )
    with staging.open("r", encoding="utf-8", newline="") as stream:
        assert validate_campaign_csv_for_spreadsheet(stream) == 1
    replace(staging, published)
    assert published.exists()
    assert not staging.exists()
