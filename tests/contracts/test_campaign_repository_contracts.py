"""Backend-neutral Campaign repository contract matrix."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

import pytest
from sqlalchemy.orm import Session

from pycrmkit.campaigns import (
    Campaign,
    CampaignAttributionReference,
    CampaignCommunicationLink,
    CampaignId,
    CampaignMember,
    CampaignQuery,
    CampaignSegmentSource,
    CampaignStatus,
)
from pycrmkit.communication import CommunicationRecordId
from pycrmkit.contacts import ContactId
from pycrmkit.core.pagination import OffsetPageRequest
from pycrmkit.core.references import EntityReference
from pycrmkit.exceptions import DuplicateError
from pycrmkit.segments import SegmentId
from pycrmkit.storage.memory import (
    MemoryCampaignAudienceRepository,
    MemoryCampaignLinkageRepository,
    MemoryCampaignRepository,
)
from pycrmkit.storage.sqlalchemy.repositories import (
    SQLAlchemyCampaignAudienceRepository,
    SQLAlchemyCampaignLinkageRepository,
    SQLAlchemyCampaignRepository,
)

Backend = Literal["memory", "sqlalchemy"]
NOW = datetime(2026, 9, 30, 15, tzinfo=UTC)
CAMPAIGN_ID = CampaignId(UUID("00000000-0000-0000-0000-000000000701"))


def _campaign(
    *,
    campaign_id: CampaignId = CAMPAIGN_ID,
    key: str = "contract",
    status: CampaignStatus = CampaignStatus.DRAFT,
    revision: int = 1,
    archived_at: datetime | None = None,
) -> Campaign:
    return Campaign(
        id=campaign_id,
        created_at=NOW,
        updated_at=NOW,
        key=key,
        name=f"Campaign {key}",
        status=status,
        revision=revision,
        archived_at=archived_at,
        starts_at=NOW + timedelta(days=1),
        ends_at=NOW + timedelta(days=2),
        metadata={"nested": {"backend": "contract"}, "flags": [1, 2]},
    )


def _contact(number: int) -> EntityReference:
    return EntityReference(
        "contact",
        ContactId(UUID(int=number)),
    )


def _seed_sql_campaign(session: Session) -> None:
    SQLAlchemyCampaignRepository(session).save(_campaign())
    session.flush()


@pytest.mark.parametrize("backend", ["memory", "sqlalchemy"])
def test_campaign_repository_contract(
    backend: Backend,
    session: Session,
) -> None:
    repository = (
        MemoryCampaignRepository()
        if backend == "memory"
        else SQLAlchemyCampaignRepository(session)
    )
    first = _campaign()
    repository.save(first)
    if backend == "sqlalchemy":
        session.flush()

    restored = repository.get(first.id)
    assert restored == first
    assert restored.metadata == first.metadata
    assert restored.starts_at == first.starts_at
    assert restored.ends_at == first.ends_at
    assert repository.find_by_key(" CONTRACT ") == first

    with pytest.raises(DuplicateError) as duplicate:
        repository.save(
            _campaign(
                campaign_id=CampaignId(
                    UUID("00000000-0000-0000-0000-000000000702")
                ),
                key="contract",
            )
        )
    assert duplicate.value.code == "campaign.key.duplicate"

    archived = _campaign(
        campaign_id=CampaignId(
            UUID("00000000-0000-0000-0000-000000000703")
        ),
        key="archived",
        status=CampaignStatus.ARCHIVED,
        revision=2,
        archived_at=NOW + timedelta(days=3),
    )
    if backend == "memory":
        repository.save(archived)
    else:
        # SQL creation starts at revision 1; persist then advance sequentially.
        initial = _campaign(campaign_id=archived.id, key="archived")
        repository.save(initial)
        session.flush()
        repository.save(archived)
        session.flush()

    assert repository.search(CampaignQuery(), OffsetPageRequest()).items == (first,)
    assert repository.search(
        CampaignQuery(status=CampaignStatus.ARCHIVED),
        OffsetPageRequest(),
    ).total == 0
    assert repository.search(
        CampaignQuery(status=CampaignStatus.ARCHIVED, include_archived=True),
        OffsetPageRequest(),
    ).items == (archived,)


@pytest.mark.parametrize("backend", ["memory", "sqlalchemy"])
def test_campaign_audience_repository_contract(
    backend: Backend,
    session: Session,
) -> None:
    if backend == "memory":
        repository = MemoryCampaignAudienceRepository()
    else:
        _seed_sql_campaign(session)
        repository = SQLAlchemyCampaignAudienceRepository(session)

    shared = _contact(711)
    direct = _contact(712)
    derived = _contact(713)
    member_shared = CampaignMember(CAMPAIGN_ID, shared, NOW)
    member_direct = CampaignMember(
        CAMPAIGN_ID,
        direct,
        NOW + timedelta(minutes=1),
    )

    repository.add_members((member_shared, member_direct))
    if backend == "sqlalchemy":
        session.flush()
    with pytest.raises(DuplicateError) as duplicate:
        repository.add_member(member_shared)
    assert duplicate.value.code == "campaign.member.duplicate"

    source = CampaignSegmentSource(
        campaign_id=CAMPAIGN_ID,
        segment_id=SegmentId(UUID(int=714)),
        segment_revision=1,
        entity_kind="contact",
        attached_at=NOW,
        captured_at=NOW,
        member_count=2,
    )
    repository.add_segment_source(source, (shared, derived))
    if backend == "sqlalchemy":
        session.flush()

    audience = repository.audience(CAMPAIGN_ID, OffsetPageRequest())
    assert audience.items == (shared, direct, derived)
    assert audience.total == 3
    assert repository.audience_count(CAMPAIGN_ID) == 3
    assert repository.contains(CAMPAIGN_ID, derived)

    replacement = CampaignSegmentSource(
        campaign_id=CAMPAIGN_ID,
        segment_id=source.segment_id,
        segment_revision=2,
        entity_kind="contact",
        attached_at=NOW,
        captured_at=NOW + timedelta(minutes=5),
        member_count=1,
    )
    repository.replace_segment_source(replacement, (direct,))
    if backend == "sqlalchemy":
        session.flush()
    assert repository.audience_count(CAMPAIGN_ID) == 2
    assert not repository.contains(CAMPAIGN_ID, derived)


@pytest.mark.parametrize("backend", ["memory", "sqlalchemy"])
def test_campaign_linkage_repository_contract(
    backend: Backend,
    session: Session,
) -> None:
    if backend == "memory":
        repository = MemoryCampaignLinkageRepository()
    else:
        _seed_sql_campaign(session)
        repository = SQLAlchemyCampaignLinkageRepository(session)

    target = _contact(721)
    attribution = CampaignAttributionReference(
        campaign_id=CAMPAIGN_ID,
        target=target,
        source=" LinkedIn  Organic ",
        recorded_at=NOW,
        external_ref=None,
        metadata={"touch": "first"},
    )
    repository.add_attribution(attribution)
    if backend == "sqlalchemy":
        session.flush()

    with pytest.raises(DuplicateError) as duplicate:
        repository.add_attribution(
            CampaignAttributionReference(
                campaign_id=CAMPAIGN_ID,
                target=target,
                source="linkedin organic",
                recorded_at=NOW,
                external_ref=" ",
            )
        )
    assert duplicate.value.code == "campaign.attribution.duplicate"
    assert repository.list_attributions(
        CAMPAIGN_ID,
        OffsetPageRequest(),
    ).items == (attribution,)
    assert repository.remove_attribution(
        CAMPAIGN_ID,
        target,
        " LINKEDIN ORGANIC ",
        None,
    )

    link = CampaignCommunicationLink(
        campaign_id=CAMPAIGN_ID,
        communication_id=CommunicationRecordId(UUID(int=722)),
        linked_at=NOW,
        metadata={"channel": "email"},
    )
    repository.add_communication_link(link)
    if backend == "sqlalchemy":
        session.flush()

    with pytest.raises(DuplicateError) as link_duplicate:
        repository.add_communication_link(link)
    assert link_duplicate.value.code == "campaign.communication_link.duplicate"
    assert repository.list_communication_links(
        CAMPAIGN_ID,
        OffsetPageRequest(),
    ).items == (link,)
    assert repository.remove_communication_link(
        CAMPAIGN_ID,
        link.communication_id,
    )
