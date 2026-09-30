from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from pycrmkit.campaigns import (
    CampaignAttributionReference,
    CampaignCommunicationLink,
    CampaignId,
)
from pycrmkit.communication import CommunicationRecordId
from pycrmkit.contacts import ContactId
from pycrmkit.core.references import EntityReference
from pycrmkit.exceptions import ValidationError

NOW = datetime(2026, 9, 30, 13, tzinfo=UTC)


def test_attribution_normalizes_source_and_external_reference() -> None:
    reference = CampaignAttributionReference(
        campaign_id=CampaignId(UUID("00000000-0000-0000-0000-000000000201")),
        target=EntityReference(
            "contact",
            ContactId(UUID("00000000-0000-0000-0000-000000000202")),
        ),
        source="  LinkedIn   Organic ",
        recorded_at=NOW,
        external_ref="  utm-ABC-01  ",
        metadata={"touch": "source"},
    )

    assert reference.source == "linkedin organic"
    assert reference.external_ref == "utm-ABC-01"
    assert reference.metadata == {"touch": "source"}


def test_attribution_rejects_non_crm_target_kind() -> None:
    with pytest.raises(ValidationError) as error:
        CampaignAttributionReference(
            campaign_id=CampaignId(
                UUID("00000000-0000-0000-0000-000000000203")
            ),
            target=EntityReference(
                "task",
                ContactId(UUID("00000000-0000-0000-0000-000000000204")),
            ),
            source="manual",
            recorded_at=NOW,
        )

    assert error.value.code == "campaign.attribution.target_kind.unsupported"


def test_communication_link_normalizes_role() -> None:
    link = CampaignCommunicationLink(
        campaign_id=CampaignId(UUID("00000000-0000-0000-0000-000000000205")),
        communication_id=CommunicationRecordId(
            UUID("00000000-0000-0000-0000-000000000206")
        ),
        linked_at=NOW,
        role="  Follow Up  ",
    )

    assert link.role == "follow up"
