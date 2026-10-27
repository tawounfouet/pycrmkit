"""Round-trip qualification for Campaign SQLAlchemy codecs."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from uuid import UUID

import pytest

from pycrmkit.campaigns import (
    Campaign,
    CampaignAttributionReference,
    CampaignCommunicationLink,
    CampaignId,
    CampaignMember,
    CampaignSegmentSource,
    CampaignStatus,
)
from pycrmkit.communication import CommunicationRecordId
from pycrmkit.contacts import ContactId
from pycrmkit.core.ids import EntityId, UUIDId
from pycrmkit.core.references import EntityReference
from pycrmkit.leads import LeadId
from pycrmkit.opportunities import OpportunityId
from pycrmkit.organizations import OrganizationId
from pycrmkit.segments import SegmentId
from pycrmkit.storage.sqlalchemy.campaign_codec import (
    campaign_attribution_from_model,
    campaign_attribution_to_model,
    campaign_communication_link_from_model,
    campaign_communication_link_to_model,
    campaign_from_model,
    campaign_member_from_model,
    campaign_member_to_model,
    campaign_segment_member_from_model,
    campaign_segment_member_to_model,
    campaign_segment_source_from_model,
    campaign_segment_source_to_model,
    campaign_to_model,
)

CAMPAIGN_ID = CampaignId(UUID("00000000-0000-0000-0000-000000000301"))
SEGMENT_ID = SegmentId(UUID("00000000-0000-0000-0000-000000000302"))
OWNER_ID = EntityId(UUID("00000000-0000-0000-0000-000000000303"))
COMMUNICATION_ID = CommunicationRecordId(
    UUID("00000000-0000-0000-0000-000000000304")
)
PARIS = timezone(timedelta(hours=2))
CREATED = datetime(2026, 9, 30, 8, 0, tzinfo=PARIS)
UPDATED = datetime(2026, 9, 30, 9, 0, tzinfo=PARIS)


def test_campaign_round_trip_preserves_domain_state_and_utc_times() -> None:
    campaign = Campaign(
        id=CAMPAIGN_ID,
        created_at=CREATED,
        updated_at=UPDATED,
        key="autumn-2026",
        name="Autumn 2026",
        description="Qualified campaign",
        status=CampaignStatus.ACTIVE,
        starts_at=datetime(2026, 10, 1, 9, 0, tzinfo=PARIS),
        ends_at=datetime(2026, 10, 31, 18, 0, tzinfo=PARIS),
        owner_id=OWNER_ID,
        revision=4,
        metadata={"nested": {"tags": ["crm", "campaign"]}},
    )

    model = campaign_to_model(campaign)
    restored = campaign_from_model(model)

    assert restored.id == campaign.id
    assert restored.key == campaign.key
    assert restored.name == campaign.name
    assert restored.description == campaign.description
    assert restored.status is CampaignStatus.ACTIVE
    assert restored.starts_at == campaign.starts_at
    assert restored.ends_at == campaign.ends_at
    assert restored.owner_id == OWNER_ID
    assert restored.revision == 4
    assert restored.created_at == campaign.created_at
    assert restored.updated_at == campaign.updated_at
    assert restored.metadata == campaign.metadata
    assert restored.metadata is not model.metadata_json
    assert restored.created_at.tzinfo is UTC
    assert restored.updated_at.tzinfo is UTC
    assert restored.starts_at is not None and restored.starts_at.tzinfo is UTC
    assert restored.ends_at is not None and restored.ends_at.tzinfo is UTC


def test_campaign_from_model_treats_sqlite_naive_times_as_utc() -> None:
    campaign = Campaign(
        id=CAMPAIGN_ID,
        created_at=datetime(2026, 9, 30, 8, tzinfo=UTC),
        updated_at=datetime(2026, 9, 30, 9, tzinfo=UTC),
        key="archived",
        name="Archived",
        status=CampaignStatus.ARCHIVED,
        archived_at=datetime(2026, 9, 30, 9, tzinfo=UTC),
    )
    model = campaign_to_model(campaign)
    model.created_at = model.created_at.replace(tzinfo=None)
    model.updated_at = model.updated_at.replace(tzinfo=None)
    assert model.archived_at is not None
    model.archived_at = model.archived_at.replace(tzinfo=None)

    restored = campaign_from_model(model)

    assert restored.created_at.tzinfo is UTC
    assert restored.updated_at.tzinfo is UTC
    assert restored.archived_at is not None
    assert restored.archived_at.tzinfo is UTC


REFERENCE_CASES = (
    ("contact", ContactId, "00000000-0000-0000-0000-000000000311"),
    ("organization", OrganizationId, "00000000-0000-0000-0000-000000000312"),
    ("lead", LeadId, "00000000-0000-0000-0000-000000000313"),
    ("opportunity", OpportunityId, "00000000-0000-0000-0000-000000000314"),
)


@pytest.mark.parametrize(("kind", "id_type", "raw_id"), REFERENCE_CASES)
def test_campaign_member_round_trip_restores_typed_reference(
    kind: str,
    id_type: type[UUIDId],
    raw_id: str,
) -> None:
    reference = EntityReference(kind, id_type.parse(raw_id))
    member = CampaignMember(
        campaign_id=CAMPAIGN_ID,
        entity=reference,
        added_at=CREATED,
        source="manual",
        actor_id="user:42",
        metadata={"origin": "test"},
    )

    restored = campaign_member_from_model(campaign_member_to_model(member))

    assert restored == member
    assert type(restored.entity.id) is id_type
    assert restored.added_at.tzinfo is UTC


def test_campaign_segment_source_and_captured_member_round_trip() -> None:
    source = CampaignSegmentSource(
        campaign_id=CAMPAIGN_ID,
        segment_id=SEGMENT_ID,
        segment_revision=7,
        entity_kind="contact",
        attached_at=CREATED,
        captured_at=UPDATED,
        member_count=1,
        actor_id="user:42",
        metadata={"snapshot": {"revision": 7}},
    )
    source_model = campaign_segment_source_to_model(source)
    restored_source = campaign_segment_source_from_model(source_model)

    member = EntityReference(
        "contact",
        ContactId.parse("00000000-0000-0000-0000-000000000315"),
    )
    member_model = campaign_segment_member_to_model(
        CAMPAIGN_ID,
        SEGMENT_ID,
        member,
    )
    restored_member = campaign_segment_member_from_model(member_model)

    assert restored_source == source
    assert restored_source.attached_at.tzinfo is UTC
    assert restored_source.captured_at.tzinfo is UTC
    assert restored_source.metadata is not source_model.metadata_json
    assert restored_member == member
    assert type(restored_member.id) is ContactId


@pytest.mark.parametrize(("kind", "id_type", "raw_id"), REFERENCE_CASES)
def test_campaign_attribution_round_trip_restores_typed_reference(
    kind: str,
    id_type: type[UUIDId],
    raw_id: str,
) -> None:
    attribution = CampaignAttributionReference(
        campaign_id=CAMPAIGN_ID,
        target=EntityReference(kind, id_type.parse(raw_id)),
        source="organic",
        recorded_at=CREATED,
        external_ref="touch-001",
        actor_id="user:42",
        metadata={"weighting": "none"},
    )

    restored = campaign_attribution_from_model(
        campaign_attribution_to_model(attribution)
    )

    assert restored == attribution
    assert type(restored.target.id) is id_type
    assert restored.recorded_at.tzinfo is UTC


def test_campaign_attribution_none_external_ref_uses_non_null_db_representation() -> None:
    attribution = CampaignAttributionReference(
        campaign_id=CAMPAIGN_ID,
        target=EntityReference(
            "contact",
            ContactId.parse("00000000-0000-0000-0000-000000000316"),
        ),
        source="organic",
        recorded_at=CREATED,
        external_ref=None,
    )

    model = campaign_attribution_to_model(attribution)
    restored = campaign_attribution_from_model(model)

    assert model.external_ref == ""
    assert restored.external_ref is None


def test_campaign_communication_link_round_trip() -> None:
    link = CampaignCommunicationLink(
        campaign_id=CAMPAIGN_ID,
        communication_id=COMMUNICATION_ID,
        linked_at=CREATED,
        role="follow-up",
        actor_id="user:42",
        metadata={"channel": "email"},
    )

    model = campaign_communication_link_to_model(link)
    restored = campaign_communication_link_from_model(model)

    assert restored == link
    assert type(restored.communication_id) is CommunicationRecordId
    assert restored.linked_at.tzinfo is UTC
    assert restored.metadata is not model.metadata_json
