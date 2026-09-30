from __future__ import annotations

from datetime import UTC, datetime, timedelta

from pycrmkit import CRM
from pycrmkit.campaigns import CampaignStatus, CampaignUpdate
from pycrmkit.core import FixedClock

NOW = datetime(2026, 9, 30, 9, tzinfo=UTC)


def test_memory_crm_exposes_campaign_metadata_lifecycle() -> None:
    clock = FixedClock(NOW)
    crm = CRM.memory(clock=clock, webhook_auto_delivery=False)

    campaign = crm.campaigns.create(
        key="autumn-launch",
        name="Autumn Launch",
        description="Campaign metadata only",
        starts_at=NOW + timedelta(days=1),
        ends_at=NOW + timedelta(days=30),
        metadata={"channel_hint": "email"},
    )
    revised = crm.campaigns.update(
        campaign.id,
        CampaignUpdate(name="Autumn Launch 2026"),
        expected_revision=1,
    )
    active = crm.campaigns.activate(revised.id, expected_revision=2)

    assert campaign.status is CampaignStatus.DRAFT
    assert revised.name == "Autumn Launch 2026"
    assert active.status is CampaignStatus.ACTIVE
    assert crm.campaigns.get(campaign.id) == active
    assert crm.campaigns.list().items == (active,)


def test_campaign_mutations_emit_declared_domain_events() -> None:
    crm = CRM.memory(clock=FixedClock(NOW), webhook_auto_delivery=False)
    emitted: list[str] = []
    for event_type in (
        "campaign.created",
        "campaign.updated",
        "campaign.activated",
        "campaign.completed",
        "campaign.archived",
    ):
        crm.events.subscribe(
            event_type,
            lambda event, emitted=emitted: emitted.append(str(event.type)),
        )

    campaign = crm.campaigns.create(key="events", name="Events")
    campaign = crm.campaigns.update(
        campaign.id,
        CampaignUpdate(description="Metadata"),
    )
    campaign = crm.campaigns.activate(campaign.id)
    campaign = crm.campaigns.complete(campaign.id)
    crm.campaigns.archive(campaign.id)

    assert emitted == [
        "campaign.created",
        "campaign.updated",
        "campaign.activated",
        "campaign.completed",
        "campaign.archived",
    ]
