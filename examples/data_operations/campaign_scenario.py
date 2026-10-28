"""Installed-artifact and source-checkout smoke for Campaign Data Operations.

No database, web framework or external service is required. This must execute
in a fresh, core-only installed-wheel environment with PYTHONPATH cleared.
"""

from __future__ import annotations

import csv
import io
import json

from pycrmkit import CRM
from pycrmkit.campaigns import export_campaign_records, import_campaign_members
from pycrmkit.core.references import EntityReference
from pycrmkit.importers import CSVReader, IterableReader


def main() -> None:
    crm = CRM.memory(webhook_auto_delivery=False)
    ada = crm.contacts.create(display_name="Ada")
    grace = crm.contacts.create(display_name="Grace")
    campaign = crm.campaigns.create(key="installed-wheel-campaign", name="DataOps")

    segment = crm.segments.create_static(
        key="installed-capture", name="Captured", entity_kind="contact"
    )
    crm.segments.add_member(
        segment.id, EntityReference("contact", ada.id)
    )
    crm.campaigns.attach_segment_source(campaign.id, segment.id)

    data = io.StringIO(
        "entity_kind,entity_id\n"
        f"contact,{ada.id}\n"
        f"contact,{grace.id}\n"
        f"contact,{ada.id}\n"
    )
    first = import_campaign_members(
        crm.campaigns,
        campaign.id,
        CSVReader(data),
        source="artifact-smoke",
    )
    assert first.rows_created == 2
    assert first.duplicates == 1
    assert crm.campaigns.members(campaign.id).total == 2
    assert crm.campaigns.audience_count(campaign.id) == 2

    replay = import_campaign_members(
        crm.campaigns, campaign.id,
        IterableReader([
            {"entity_kind": "contact", "entity_id": str(ada.id)},
            {"entity_kind": "contact", "entity_id": str(grace.id)},
        ])
    )
    assert replay.rows_created == 0
    assert replay.duplicates == 2

    audience_json = io.StringIO()
    assert export_campaign_records(
        crm.campaigns, campaign.id, audience_json,
        kind="audience", format="json", page_size=1,
    ) == 2
    audience = json.loads(audience_json.getvalue())
    assert len({item["entity_id"] for item in audience}) == 2
    assert all("source" not in item for item in audience)

    direct_csv = io.StringIO()
    assert export_campaign_records(
        crm.campaigns, campaign.id, direct_csv,
        kind="direct", format="csv", page_size=1,
    ) == 2
    direct = list(csv.DictReader(io.StringIO(direct_csv.getvalue())))
    assert len(direct) == 2
    assert {row["source"] for row in direct} == {"artifact-smoke"}

    snapshot_jsonl = io.StringIO()
    assert export_campaign_records(
        crm.campaigns, campaign.id, snapshot_jsonl,
        kind="sources", format="jsonl",
    ) == 1
    captured = json.loads(snapshot_jsonl.getvalue().strip())
    assert captured["member_count"] == 1
    assert "actor_id" not in captured
    print("Campaign DataOps installed-artifact contract: PASS")


if __name__ == "__main__":
    main()
