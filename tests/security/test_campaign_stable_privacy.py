"""LOT-32-003: Campaign metadata privacy and CSV-consumer boundary checks."""
from __future__ import annotations

import io

import pytest

from examples.data_operations.campaign_csv_spreadsheet_guard import (
    validate_campaign_csv_for_spreadsheet,
)
from pycrmkit import CRM
from pycrmkit.campaigns import export_campaign_records
from pycrmkit.core.references import EntityReference
from pycrmkit.events import DomainEvent, EventSerializer, default_event_registry


def test_campaign_domain_event_payloads_do_not_copy_private_metadata() -> None:
    crm = CRM.memory(webhook_auto_delivery=False)
    observed: list[DomainEvent] = []
    crm.events.subscribe("campaign.created", observed.append)
    crm.events.subscribe("campaign.member_added", observed.append)

    secret = "private-secret-not-for-events-5c3a"
    contact = crm.contacts.create(display_name="Private customer name")
    campaign = crm.campaigns.create(
        key="stable-private-events",
        name="Private campaign name",
        metadata={"api_key": secret, "private_note": "hidden-note-5c3a"},
    )
    crm.campaigns.add_member(
        campaign.id,
        EntityReference("contact", contact.id),
        source="approved",
        metadata={"access_token": secret},
    )
    assert [str(event.type) for event in observed] == [
        "campaign.created", "campaign.member_added",
    ]
    for event in observed:
        encoded = EventSerializer(default_event_registry()).dumps(event)
        assert secret not in encoded
        assert "hidden-note-5c3a" not in encoded
        assert "Private customer name" not in encoded
        assert "Private campaign name" not in encoded


def test_campaign_export_allowlist_and_spreadsheet_consumer_boundary() -> None:
    crm = CRM.memory(webhook_auto_delivery=False)
    contact = crm.contacts.create(display_name="Private customer export name")
    campaign = crm.campaigns.create(
        key="stable-private-export",
        name="Private campaign export name",
    )
    crm.campaigns.add_member(
        campaign.id,
        EntityReference("contact", contact.id),
        source="=2+2",
        metadata={"api_key": "never-export-sensitive-key"},
    )
    direct = io.StringIO()
    audience = io.StringIO()
    assert export_campaign_records(
        crm.campaigns, campaign.id, direct, kind="direct", format="csv",
    ) == 1
    assert export_campaign_records(
        crm.campaigns, campaign.id, audience, kind="audience", format="jsonl",
    ) == 1
    for value in (direct.getvalue(), audience.getvalue()):
        for forbidden in (
            "Private customer export name",
            "Private campaign export name",
            "never-export-sensitive-key",
            "api_key",
            "actor_id",
        ):
            assert forbidden not in value

    # Machine-readable canonical CSV is deliberately not spreadsheet-safe.
    assert "=2+2" in direct.getvalue()
    with pytest.raises(ValueError, match="spreadsheet formula risk"):
        validate_campaign_csv_for_spreadsheet(io.StringIO(direct.getvalue()))
