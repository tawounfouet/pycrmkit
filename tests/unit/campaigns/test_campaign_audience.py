from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from pycrmkit.campaigns import CampaignId, CampaignMember, CampaignSegmentSource
from pycrmkit.contacts import ContactId
from pycrmkit.core.references import EntityReference
from pycrmkit.exceptions import ValidationError
from pycrmkit.segments import SegmentId

NOW = datetime(2026, 9, 30, 11, tzinfo=UTC)


def test_campaign_member_normalizes_source_and_copies_metadata() -> None:
    metadata = {"origin": "manual"}
    member = CampaignMember(
        campaign_id=CampaignId(UUID("00000000-0000-0000-0000-000000000101")),
        entity=EntityReference(
            "contact",
            ContactId(UUID("00000000-0000-0000-0000-000000000102")),
        ),
        added_at=NOW,
        source="  Sales   List ",
        metadata=metadata,
    )
    metadata["origin"] = "changed"

    assert member.source == "sales list"
    assert member.metadata == {"origin": "manual"}


def test_campaign_member_rejects_unsupported_entity_kind() -> None:
    with pytest.raises(ValidationError) as error:
        CampaignMember(
            campaign_id=CampaignId(
                UUID("00000000-0000-0000-0000-000000000103")
            ),
            entity=EntityReference(
                "task",
                ContactId(UUID("00000000-0000-0000-0000-000000000104")),
            ),
            added_at=NOW,
        )

    assert error.value.code == "campaign.member.kind.unsupported"


def test_segment_source_validates_capture_metadata() -> None:
    source = CampaignSegmentSource(
        campaign_id=CampaignId(UUID("00000000-0000-0000-0000-000000000105")),
        segment_id=SegmentId(UUID("00000000-0000-0000-0000-000000000106")),
        segment_revision=2,
        entity_kind="CONTACT",
        attached_at=NOW,
        captured_at=NOW,
        member_count=3,
        metadata={"purpose": "launch"},
    )

    assert source.entity_kind == "contact"
    assert source.segment_revision == 2
    assert source.member_count == 3
