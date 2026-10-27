"""Contract tests for SQLAlchemy Campaign linkage persistence."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from pycrmkit.campaigns import (
    Campaign,
    CampaignAttributionReference,
    CampaignCommunicationLink,
    CampaignId,
)
from pycrmkit.communication import CommunicationRecordId
from pycrmkit.contacts import ContactId
from pycrmkit.core.pagination import OffsetPageRequest
from pycrmkit.core.references import EntityReference
from pycrmkit.exceptions import DuplicateError
from pycrmkit.storage.sqlalchemy.repositories import (
    SQLAlchemyCampaignLinkageRepository,
    SQLAlchemyCampaignRepository,
)

NOW = datetime(2026, 9, 30, 13, tzinfo=UTC)
CAMPAIGN_ID = CampaignId.parse(
    "00000000-0000-0000-0000-000000000601"
)


def _seed_campaign(session: Session) -> None:
    SQLAlchemyCampaignRepository(session).save(
        Campaign(
            id=CAMPAIGN_ID,
            created_at=NOW,
            updated_at=NOW,
            key="linkage-test",
            name="Linkage Test",
        )
    )
    session.flush()


def _contact(suffix: int) -> EntityReference:
    return EntityReference(
        "contact",
        ContactId.parse(
            f"00000000-0000-0000-0000-{suffix:012d}"
        ),
    )


def _attribution(
    target: EntityReference,
    *,
    source: str = "organic",
    external_ref: str | None = None,
    recorded_at: datetime = NOW,
) -> CampaignAttributionReference:
    return CampaignAttributionReference(
        campaign_id=CAMPAIGN_ID,
        target=target,
        source=source,
        external_ref=external_ref,
        recorded_at=recorded_at,
        metadata={"source": source},
    )


def _communication_link(
    suffix: int,
    *,
    linked_at: datetime = NOW,
    role: str = "touchpoint",
) -> CampaignCommunicationLink:
    return CampaignCommunicationLink(
        campaign_id=CAMPAIGN_ID,
        communication_id=CommunicationRecordId.parse(
            f"00000000-0000-0000-0000-{suffix:012d}"
        ),
        linked_at=linked_at,
        role=role,
        metadata={"role": role},
    )


def test_attribution_duplicate_semantics_include_none_external_ref(
    session: Session,
) -> None:
    _seed_campaign(session)
    repository = SQLAlchemyCampaignLinkageRepository(session)
    target = _contact(611)
    without_external_ref = _attribution(
        target,
        source="  LinkedIn   Organic ",
        external_ref=None,
    )
    repository.add_attribution(without_external_ref)
    session.flush()

    with pytest.raises(DuplicateError) as none_duplicate:
        repository.add_attribution(
            _attribution(
                target,
                source="linkedin organic",
                external_ref="   ",
            )
        )
    assert none_duplicate.value.code == "campaign.attribution.duplicate"

    explicit = _attribution(
        target,
        source="linkedin organic",
        external_ref="touch-001",
    )
    repository.add_attribution(explicit)
    session.flush()

    with pytest.raises(DuplicateError) as explicit_duplicate:
        repository.add_attribution(
            _attribution(
                target,
                source="LINKEDIN ORGANIC",
                external_ref=" touch-001 ",
            )
        )
    assert explicit_duplicate.value.code == "campaign.attribution.duplicate"

    other_external_ref = _attribution(
        target,
        source="linkedin organic",
        external_ref="touch-002",
    )
    repository.add_attribution(other_external_ref)
    session.flush()

    page = repository.list_attributions(
        CAMPAIGN_ID,
        OffsetPageRequest(),
    )
    assert page.total == 3
    assert {item.external_ref for item in page.items} == {
        None,
        "touch-001",
        "touch-002",
    }


def test_remove_attribution_normalizes_source_and_external_reference(
    session: Session,
) -> None:
    _seed_campaign(session)
    repository = SQLAlchemyCampaignLinkageRepository(session)
    target = _contact(621)
    none_ref = _attribution(
        target,
        source="LinkedIn Organic",
        external_ref=None,
    )
    explicit_ref = _attribution(
        target,
        source="Manual",
        external_ref="utm-ABC",
    )
    repository.add_attribution(none_ref)
    repository.add_attribution(explicit_ref)
    session.flush()

    assert repository.remove_attribution(
        CAMPAIGN_ID,
        target,
        "  LINKEDIN   ORGANIC ",
        "   ",
    )
    assert repository.remove_attribution(
        CAMPAIGN_ID,
        target,
        " manual ",
        "  utm-ABC  ",
    )
    assert not repository.remove_attribution(
        CAMPAIGN_ID,
        target,
        "manual",
        "utm-ABC",
    )
    assert repository.list_attributions(
        CAMPAIGN_ID,
        OffsetPageRequest(),
    ).total == 0


def test_attributions_use_exact_memory_order_and_preserve_metadata(
    session: Session,
) -> None:
    _seed_campaign(session)
    repository = SQLAlchemyCampaignLinkageRepository(session)
    later = _attribution(
        _contact(633),
        source="alpha",
        external_ref="b",
        recorded_at=NOW + timedelta(minutes=1),
    )
    same_time_source_b = _attribution(
        _contact(632),
        source="bravo",
        recorded_at=NOW,
    )
    same_time_source_a_ref_b = _attribution(
        _contact(631),
        source="alpha",
        external_ref="b",
        recorded_at=NOW,
    )
    same_time_source_a_ref_a = _attribution(
        _contact(631),
        source="alpha",
        external_ref="a",
        recorded_at=NOW,
    )

    for item in (
        later,
        same_time_source_b,
        same_time_source_a_ref_b,
        same_time_source_a_ref_a,
    ):
        repository.add_attribution(item)
    session.flush()

    page = repository.list_attributions(
        CAMPAIGN_ID,
        OffsetPageRequest(limit=3),
    )

    assert page.items == (
        same_time_source_a_ref_a,
        same_time_source_a_ref_b,
        same_time_source_b,
    )
    assert page.total == 4
    assert page.items[0].metadata == {"source": "alpha"}


def test_communication_links_duplicate_remove_order_and_metadata(
    session: Session,
) -> None:
    _seed_campaign(session)
    repository = SQLAlchemyCampaignLinkageRepository(session)
    later = _communication_link(
        643,
        linked_at=NOW + timedelta(minutes=1),
        role="follow up",
    )
    same_time_high_id = _communication_link(642, role="primary")
    same_time_low_id = _communication_link(641, role="touchpoint")

    for link in (later, same_time_high_id, same_time_low_id):
        repository.add_communication_link(link)
    session.flush()

    with pytest.raises(DuplicateError) as duplicate:
        repository.add_communication_link(
            _communication_link(641, role="other")
        )
    assert duplicate.value.code == "campaign.communication_link.duplicate"

    page = repository.list_communication_links(
        CAMPAIGN_ID,
        OffsetPageRequest(limit=2),
    )
    assert page.items == (same_time_low_id, same_time_high_id)
    assert page.total == 3
    assert page.items[0].metadata == {"role": "touchpoint"}

    assert repository.remove_communication_link(
        CAMPAIGN_ID,
        same_time_high_id.communication_id,
    )
    assert not repository.remove_communication_link(
        CAMPAIGN_ID,
        same_time_high_id.communication_id,
    )
    assert repository.list_communication_links(
        CAMPAIGN_ID,
        OffsetPageRequest(),
    ).items == (same_time_low_id, later)
