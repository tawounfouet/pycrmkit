from __future__ import annotations

from datetime import UTC, datetime

import pytest

from pycrmkit import CRM
from pycrmkit.core import FixedClock
from pycrmkit.contacts import ContactId
from pycrmkit.core.references import EntityReference
from pycrmkit.exceptions import InvalidStateError, ValidationError
from pycrmkit.segments import Predicate, QueryOperator

NOW = datetime(2026, 9, 30, 12, tzinfo=UTC)


def test_campaign_audience_unions_direct_and_captured_segment_members() -> None:
    crm = CRM.memory(clock=FixedClock(NOW), webhook_auto_delivery=False)
    ada = crm.contacts.create(display_name="Ada", source="LinkedIn")
    bob = crm.contacts.create(display_name="Bob", source="Referral")
    campaign = crm.campaigns.create(key="q4", name="Q4")
    bob_ref = EntityReference("contact", bob.id)

    direct = crm.campaigns.add_member(
        campaign.id,
        bob_ref,
        source="sales-list",
    )
    segment = crm.segments.create_dynamic(
        key="linkedin",
        name="LinkedIn",
        entity_kind="contact",
        query=Predicate("source", QueryOperator.EQ, "linkedin"),
    )
    source = crm.campaigns.attach_segment_source(campaign.id, segment.id)

    assert direct.source == "sales-list"
    assert source.member_count == 1
    assert set(crm.campaigns.audience(campaign.id).items) == {
        EntityReference("contact", ada.id),
        bob_ref,
    }
    assert crm.campaigns.members(campaign.id).items == (direct,)
    assert crm.campaigns.segment_sources(campaign.id).items == (source,)
    assert crm.campaigns.audience_count(campaign.id) == 2


def test_segment_source_is_stable_until_explicit_refresh() -> None:
    crm = CRM.memory(clock=FixedClock(NOW), webhook_auto_delivery=False)
    ada = crm.contacts.create(display_name="Ada", source="LinkedIn")
    campaign = crm.campaigns.create(key="launch", name="Launch")
    segment = crm.segments.create_dynamic(
        key="linkedin-refresh",
        name="LinkedIn Refresh",
        entity_kind="contact",
        query=Predicate("source", QueryOperator.EQ, "linkedin"),
    )

    attached = crm.campaigns.attach_segment_source(campaign.id, segment.id)
    grace = crm.contacts.create(display_name="Grace", source="LinkedIn")
    grace_ref = EntityReference("contact", grace.id)

    assert attached.member_count == 1
    assert crm.campaigns.contains(campaign.id, EntityReference("contact", ada.id))
    assert not crm.campaigns.contains(campaign.id, grace_ref)

    refreshed = crm.campaigns.refresh_segment_source(campaign.id, segment.id)

    assert refreshed.attached_at == attached.attached_at
    assert refreshed.member_count == 2
    assert crm.campaigns.contains(campaign.id, grace_ref)


def test_segment_and_direct_membership_are_deduplicated_and_detachable() -> None:
    crm = CRM.memory(clock=FixedClock(NOW), webhook_auto_delivery=False)
    ada = crm.contacts.create(display_name="Ada", source="LinkedIn")
    ada_ref = EntityReference("contact", ada.id)
    campaign = crm.campaigns.create(key="dedupe", name="Dedupe")
    crm.campaigns.add_member(campaign.id, ada_ref)
    segment = crm.segments.create_dynamic(
        key="dedupe-linkedin",
        name="Dedupe LinkedIn",
        entity_kind="contact",
        query=Predicate("source", QueryOperator.EQ, "linkedin"),
    )
    crm.campaigns.attach_segment_source(campaign.id, segment.id)

    assert crm.campaigns.audience_count(campaign.id) == 1
    assert crm.campaigns.detach_segment_source(campaign.id, segment.id)
    assert crm.campaigns.audience(campaign.id).items == (ada_ref,)
    assert crm.campaigns.remove_member(campaign.id, ada_ref)
    assert crm.campaigns.audience_count(campaign.id) == 0


def test_campaign_membership_validates_existing_entities_and_archive_state() -> None:
    crm = CRM.memory(clock=FixedClock(NOW), webhook_auto_delivery=False)
    campaign = crm.campaigns.create(key="guardrails", name="Guardrails")
    missing = EntityReference(
        "contact",
        ContactId.parse("00000000-0000-0000-0000-000000009999"),
    )

    with pytest.raises(ValidationError) as missing_error:
        crm.campaigns.add_member(campaign.id, missing)
    assert missing_error.value.code == "campaign.member.not_found"

    crm.campaigns.archive(campaign.id)

    with pytest.raises(InvalidStateError) as archived_error:
        crm.campaigns.add_member(campaign.id, missing)
    assert archived_error.value.code == "campaign.archived"


def test_campaign_audience_events_are_public_and_post_commit() -> None:
    crm = CRM.memory(clock=FixedClock(NOW), webhook_auto_delivery=False)
    emitted: list[str] = []
    event_types = (
        "campaign.member_added",
        "campaign.member_removed",
        "campaign.segment_source_attached",
        "campaign.segment_source_refreshed",
        "campaign.segment_source_detached",
    )
    for event_type in event_types:
        crm.events.subscribe(
            event_type,
            lambda event, emitted=emitted: emitted.append(str(event.type)),
        )

    ada = crm.contacts.create(display_name="Ada", source="LinkedIn")
    ada_ref = EntityReference("contact", ada.id)
    campaign = crm.campaigns.create(key="events-audience", name="Events Audience")
    segment = crm.segments.create_dynamic(
        key="events-linkedin",
        name="Events LinkedIn",
        entity_kind="contact",
        query=Predicate("source", QueryOperator.EQ, "linkedin"),
    )

    crm.campaigns.add_member(campaign.id, ada_ref)
    crm.campaigns.remove_member(campaign.id, ada_ref)
    crm.campaigns.attach_segment_source(campaign.id, segment.id)
    crm.campaigns.refresh_segment_source(campaign.id, segment.id)
    crm.campaigns.detach_segment_source(campaign.id, segment.id)

    assert emitted == list(event_types)
