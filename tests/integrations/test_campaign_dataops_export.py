"""Campaign DataOps export parity across CSV, JSON and JSONL."""

from __future__ import annotations

import csv
import io
import json

import pytest

from pycrmkit import CRM
from pycrmkit.campaigns import (
    export_campaign_records,
    iter_campaign_audience_records,
    iter_campaign_direct_member_records,
    iter_campaign_segment_source_records,
)
from pycrmkit.core.references import EntityReference
from pycrmkit.exceptions import ValidationError
from pycrmkit.segments import SegmentMode


def _scenario() -> tuple[CRM, object]:
    crm = CRM.memory(webhook_auto_delivery=False)
    ada = crm.contacts.create(display_name="Ada")
    grace = crm.contacts.create(display_name="Grace")
    campaign = crm.campaigns.create(key="export-scenario", name="Export")
    crm.campaigns.add_members(
        campaign.id,
        (EntityReference("contact", ada.id), EntityReference("contact", grace.id)),
        source="campaign-file",
    )
    segment = crm.segments.create(
        key="export-segment", name="Segment", entity_kind="contact",
        mode=SegmentMode.STATIC,
    )
    crm.segments.add_members(
        segment.id, (EntityReference("contact", ada.id),)
    )
    crm.campaigns.attach_segment_source(campaign.id, segment.id)
    return crm, campaign.id


@pytest.mark.parametrize("kind", ["direct", "audience", "sources"])
def test_campaign_export_csv_json_jsonl_payloads_match(kind: str) -> None:
    crm, cid = _scenario()
    written: dict[str, list[dict[str, str]]] = {}
    for format in ("csv", "json", "jsonl"):
        stream = io.StringIO()
        count = export_campaign_records(
            crm.campaigns,
            cid,
            stream,
            kind=kind,
            format=format,
            page_size=1,
        )
        stream.seek(0)
        if format == "csv":
            rows = list(csv.DictReader(stream))
        elif format == "json":
            rows = json.load(stream)
        else:
            rows = [json.loads(line) for line in stream]
        assert count == len(rows)
        written[format] = [{key: str(value) for key, value in row.items()}
                           for row in rows]
    assert written["csv"] == written["json"] == written["jsonl"]
    assert len(written["csv"]) == {"direct": 2, "audience": 2, "sources": 1}[kind]
    for record in written["csv"]:
        assert "actor_id" not in record
        assert "subject" not in record
        assert "email" not in record


def test_campaign_export_preserves_origin_separation() -> None:
    crm, cid = _scenario()
    direct = list(iter_campaign_direct_member_records(
        crm.campaigns, cid, page_size=1
    ))
    audience = list(iter_campaign_audience_records(
        crm.campaigns, cid, page_size=1
    ))
    sources = list(iter_campaign_segment_source_records(
        crm.campaigns, cid, page_size=1
    ))
    assert len(direct) == 2
    assert len(audience) == 2
    assert len(sources) == 1
    assert "source" in direct[0]
    assert "source" not in audience[0]
    assert sources[0]["member_count"] == 1


def test_campaign_empty_export_outputs_csv_headers_and_valid_json() -> None:
    crm = CRM.memory(webhook_auto_delivery=False)
    cid = crm.campaigns.create(key="empty-export", name="Empty").id
    stream = io.StringIO()
    count = export_campaign_records(
        crm.campaigns, cid, stream, kind="direct", format="csv"
    )
    assert count == 0
    assert stream.getvalue().startswith(
        "campaign_id,entity_kind,entity_id,source,added_at"
    )
    output = io.StringIO()
    assert export_campaign_records(
        crm.campaigns, cid, output, kind="sources", format="json"
    ) == 0
    assert json.loads(output.getvalue()) == []


def test_campaign_export_over_two_hundred_members_is_paged_without_loss() -> None:
    crm = CRM.memory(webhook_auto_delivery=False)
    campaign = crm.campaigns.create(key="paging-export", name="Paging")
    for idx in range(205):
        contact = crm.contacts.create(display_name=f"Member {idx}")
        crm.campaigns.add_member(
            campaign.id, EntityReference("contact", contact.id)
        )
    lines = list(iter_campaign_direct_member_records(
        crm.campaigns, campaign.id, page_size=100
    ))
    assert len(lines) == 205
    assert len({row["entity_id"] for row in lines}) == 205
    stream = io.StringIO()
    assert export_campaign_records(
        crm.campaigns,
        campaign.id,
        stream,
        kind="audience",
        format="jsonl",
        page_size=100,
    ) == 205


def test_campaign_export_rejects_invalid_configuration_before_writing() -> None:
    crm = CRM.memory(webhook_auto_delivery=False)
    cid = crm.campaigns.create(key="invalid-export", name="Invalid").id
    for kwargs in (
        {"kind": "unsupported", "format": "json"},
        {"kind": "direct", "format": "xml"},
        {"kind": "direct", "format": "csv", "page_size": 201},
        {"kind": "sources", "format": "json", "page_size": 0},
    ):
        stream = io.StringIO()
        with pytest.raises(ValidationError):
            export_campaign_records(crm.campaigns, cid, stream, **kwargs)
        assert stream.getvalue() == ""
