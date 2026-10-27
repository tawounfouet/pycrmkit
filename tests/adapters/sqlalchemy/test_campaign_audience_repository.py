"""Contract tests for SQLAlchemy Campaign audience persistence."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from pycrmkit.campaigns import (
    Campaign,
    CampaignId,
    CampaignMember,
    CampaignSegmentSource,
)
from pycrmkit.contacts import ContactId
from pycrmkit.core.pagination import OffsetPageRequest
from pycrmkit.core.references import EntityReference
from pycrmkit.exceptions import DuplicateError, NotFoundError
from pycrmkit.segments import SegmentId
from pycrmkit.storage.sqlalchemy.repositories import (
    SQLAlchemyCampaignAudienceRepository,
    SQLAlchemyCampaignRepository,
)

NOW = datetime(2026, 9, 30, 11, tzinfo=UTC)
CAMPAIGN_ID = CampaignId.parse(
    "00000000-0000-0000-0000-000000000501"
)


def _seed_campaign(session: Session) -> None:
    SQLAlchemyCampaignRepository(session).save(
        Campaign(
            id=CAMPAIGN_ID,
            created_at=NOW,
            updated_at=NOW,
            key="audience-test",
            name="Audience Test",
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


def _member(
    entity: EntityReference,
    *,
    added_at: datetime = NOW,
    source: str = "manual",
) -> CampaignMember:
    return CampaignMember(
        campaign_id=CAMPAIGN_ID,
        entity=entity,
        added_at=added_at,
        source=source,
        metadata={"origin": source},
    )


def _segment_source(
    suffix: int,
    *,
    attached_at: datetime = NOW,
    captured_at: datetime = NOW,
    member_count: int,
    revision: int = 1,
) -> CampaignSegmentSource:
    return CampaignSegmentSource(
        campaign_id=CAMPAIGN_ID,
        segment_id=SegmentId.parse(
            f"00000000-0000-0000-0000-{suffix:012d}"
        ),
        segment_revision=revision,
        entity_kind="contact",
        attached_at=attached_at,
        captured_at=captured_at,
        member_count=member_count,
        metadata={"capture": revision},
    )


def test_direct_members_match_memory_duplicate_batch_remove_and_ordering(
    session: Session,
) -> None:
    _seed_campaign(session)
    repository = SQLAlchemyCampaignAudienceRepository(session)
    first = _member(_contact(511), added_at=NOW + timedelta(minutes=1))
    second = _member(_contact(510), added_at=NOW)
    third = _member(_contact(512), added_at=NOW + timedelta(minutes=2))

    repository.add_members((first, second, third))
    session.flush()

    page = repository.list_members(
        CAMPAIGN_ID,
        OffsetPageRequest(limit=2, offset=0),
    )
    assert page.items == (second, first)
    assert page.total == 3

    with pytest.raises(DuplicateError) as persisted:
        repository.add_member(first)
    assert persisted.value.code == "campaign.member.duplicate"

    duplicate_batch = (_member(_contact(520)), _member(_contact(520)))
    with pytest.raises(DuplicateError) as batch:
        repository.add_members(duplicate_batch)
    assert batch.value.code == "campaign.member.batch_duplicate"

    assert repository.remove_members(
        CAMPAIGN_ID,
        (first.entity, first.entity, third.entity),
    ) == 2
    assert repository.remove_member(CAMPAIGN_ID, third.entity) is False
    assert repository.list_members(
        CAMPAIGN_ID,
        OffsetPageRequest(),
    ).items == (second,)


def test_segment_capture_validates_duplicate_count_and_kind_before_mutation(
    session: Session,
) -> None:
    _seed_campaign(session)
    repository = SQLAlchemyCampaignAudienceRepository(session)
    contact = _contact(531)
    source = _segment_source(532, member_count=2)

    with pytest.raises(DuplicateError) as duplicate:
        repository.add_segment_source(source, (contact, contact))
    assert duplicate.value.code == "campaign.segment_source.members.duplicate"

    invalid_count = _segment_source(533, member_count=2)
    with pytest.raises(ValueError, match="member_count"):
        repository.add_segment_source(invalid_count, (contact,))

    wrong_kind = EntityReference(
        "organization",
        ContactId.parse("00000000-0000-0000-0000-000000000534"),
    )
    invalid_kind = _segment_source(535, member_count=1)
    with pytest.raises(ValueError, match="incompatible entity kind"):
        repository.add_segment_source(invalid_kind, (wrong_kind,))

    assert repository.list_segment_sources(
        CAMPAIGN_ID,
        OffsetPageRequest(),
    ).total == 0


def test_segment_source_add_replace_list_and_remove_are_atomic_at_repository_boundary(
    session: Session,
) -> None:
    _seed_campaign(session)
    repository = SQLAlchemyCampaignAudienceRepository(session)
    first_member = _contact(541)
    second_member = _contact(542)
    source = _segment_source(543, member_count=1)

    repository.add_segment_source(source, (first_member,))
    session.flush()

    assert repository.get_segment_source(
        CAMPAIGN_ID,
        source.segment_id,
    ) == source
    assert repository.contains(CAMPAIGN_ID, first_member)

    replacement = _segment_source(
        543,
        attached_at=source.attached_at,
        captured_at=NOW + timedelta(minutes=1),
        member_count=1,
        revision=2,
    )
    repository.replace_segment_source(replacement, (second_member,))
    session.flush()

    assert repository.get_segment_source(
        CAMPAIGN_ID,
        source.segment_id,
    ) == replacement
    assert not repository.contains(CAMPAIGN_ID, first_member)
    assert repository.contains(CAMPAIGN_ID, second_member)

    missing = _segment_source(544, member_count=0)
    with pytest.raises(NotFoundError) as not_found:
        repository.replace_segment_source(missing, ())
    assert not_found.value.code == "campaign.segment_source.not_found"

    assert repository.remove_segment_source(
        CAMPAIGN_ID,
        source.segment_id,
    )
    assert not repository.contains(CAMPAIGN_ID, second_member)
    assert not repository.remove_segment_source(
        CAMPAIGN_ID,
        source.segment_id,
    )


def test_segment_sources_are_ordered_by_attached_at_then_segment_id(
    session: Session,
) -> None:
    _seed_campaign(session)
    repository = SQLAlchemyCampaignAudienceRepository(session)
    later = _segment_source(
        552,
        attached_at=NOW + timedelta(minutes=1),
        captured_at=NOW + timedelta(minutes=1),
        member_count=0,
    )
    same_time_high_id = _segment_source(553, member_count=0)
    same_time_low_id = _segment_source(551, member_count=0)

    for source in (later, same_time_high_id, same_time_low_id):
        repository.add_segment_source(source, ())
    session.flush()

    page = repository.list_segment_sources(
        CAMPAIGN_ID,
        OffsetPageRequest(limit=2),
    )
    assert page.items == (same_time_low_id, same_time_high_id)
    assert page.total == 3


def test_final_audience_is_deduplicated_union_with_exact_count_contains_and_paging(
    session: Session,
) -> None:
    _seed_campaign(session)
    repository = SQLAlchemyCampaignAudienceRepository(session)
    shared = _contact(561)
    direct_only = _contact(563)
    captured_only = _contact(562)

    repository.add_members(
        (
            _member(shared),
            _member(direct_only),
        )
    )
    source = _segment_source(564, member_count=2)
    repository.add_segment_source(
        source,
        (shared, captured_only),
    )
    session.flush()

    first_page = repository.audience(
        CAMPAIGN_ID,
        OffsetPageRequest(limit=2, offset=0),
    )
    second_page = repository.audience(
        CAMPAIGN_ID,
        OffsetPageRequest(limit=2, offset=2),
    )

    assert first_page.items == (shared, captured_only)
    assert second_page.items == (direct_only,)
    assert first_page.total == 3
    assert second_page.total == 3
    assert repository.audience_count(CAMPAIGN_ID) == 3
    assert repository.contains(CAMPAIGN_ID, shared)
    assert repository.contains(CAMPAIGN_ID, captured_only)
    assert repository.contains(CAMPAIGN_ID, direct_only)
    assert not repository.contains(CAMPAIGN_ID, _contact(599))
