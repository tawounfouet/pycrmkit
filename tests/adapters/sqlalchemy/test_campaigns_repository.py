"""Contract tests for SQLAlchemy CampaignRepository."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from pycrmkit.campaigns import (
    Campaign,
    CampaignId,
    CampaignQuery,
    CampaignStatus,
)
from pycrmkit.core.ids import EntityId
from pycrmkit.core.pagination import OffsetPageRequest
from pycrmkit.exceptions import ConflictError, DuplicateError, NotFoundError
from pycrmkit.storage.sqlalchemy.repositories import SQLAlchemyCampaignRepository

NOW = datetime(2026, 9, 30, 8, tzinfo=UTC)


def _campaign(
    suffix: int,
    *,
    key: str,
    name: str,
    created_at: datetime = NOW,
    owner_id: EntityId | None = None,
    revision: int = 1,
    status: CampaignStatus = CampaignStatus.DRAFT,
    archived_at: datetime | None = None,
) -> Campaign:
    return Campaign(
        id=CampaignId.parse(
            f"00000000-0000-0000-0000-{suffix:012d}"
        ),
        created_at=created_at,
        updated_at=created_at,
        key=key,
        name=name,
        owner_id=owner_id,
        revision=revision,
        status=status,
        archived_at=archived_at,
        metadata={"source": "repository-test"},
    )


def test_campaign_repository_get_find_key_and_duplicate_semantics(
    session: Session,
) -> None:
    repository = SQLAlchemyCampaignRepository(session)
    first = _campaign(401, key="launch", name="Launch")
    repository.save(first)
    session.flush()

    assert repository.get(first.id) == first
    assert repository.find(first.id) == first
    assert repository.find_by_key("  LAUNCH  ") == first

    missing_id = CampaignId.parse(
        "00000000-0000-0000-0000-000000000499"
    )
    assert repository.find(missing_id) is None
    with pytest.raises(NotFoundError) as missing:
        repository.get(missing_id)
    assert missing.value.code == "campaign.not_found"

    duplicate = _campaign(402, key="launch", name="Duplicate")
    with pytest.raises(DuplicateError) as error:
        repository.save(duplicate)
    assert error.value.code == "campaign.key.duplicate"


def test_campaign_repository_search_matches_memory_filter_order_and_pagination(
    session: Session,
) -> None:
    repository = SQLAlchemyCampaignRepository(session)
    owner = EntityId.parse("00000000-0000-0000-0000-000000000450")
    other_owner = EntityId.parse("00000000-0000-0000-0000-000000000451")

    first = _campaign(
        411,
        key="first",
        name="First",
        created_at=NOW,
        owner_id=owner,
    )
    second = _campaign(
        410,
        key="second",
        name="Second",
        created_at=NOW,
        owner_id=owner,
        status=CampaignStatus.ACTIVE,
    )
    third = _campaign(
        412,
        key="third",
        name="Third",
        created_at=NOW + timedelta(minutes=1),
        owner_id=other_owner,
    )
    archived_at = NOW + timedelta(minutes=2)
    archived = _campaign(
        413,
        key="archived",
        name="Archived",
        created_at=NOW + timedelta(minutes=2),
        owner_id=owner,
        revision=2,
        status=CampaignStatus.ARCHIVED,
        archived_at=archived_at,
    )

    for item in (first, second, third, archived):
        repository.save(item)
    session.flush()

    default_page = repository.search(
        CampaignQuery(),
        OffsetPageRequest(limit=2, offset=0),
    )
    second_page = repository.search(
        CampaignQuery(),
        OffsetPageRequest(limit=2, offset=2),
    )
    owner_page = repository.search(
        CampaignQuery(owner_id=owner),
        OffsetPageRequest(),
    )
    archived_hidden = repository.search(
        CampaignQuery(status=CampaignStatus.ARCHIVED),
        OffsetPageRequest(),
    )
    archived_visible = repository.search(
        CampaignQuery(
            status=CampaignStatus.ARCHIVED,
            include_archived=True,
        ),
        OffsetPageRequest(),
    )

    assert default_page.items == (second, first)
    assert default_page.total == 3
    assert second_page.items == (third,)
    assert second_page.total == 3
    assert owner_page.items == (second, first)
    assert archived_hidden.total == 0
    assert archived_visible.items == (archived,)


def test_campaign_repository_revision_progression_and_idempotent_same_state(
    session: Session,
) -> None:
    repository = SQLAlchemyCampaignRepository(session)
    first = _campaign(421, key="revision", name="Revision")
    repository.save(first)
    session.flush()

    repository.save(repository.get(first.id))

    same_revision_different_state = Campaign(
        id=first.id,
        created_at=first.created_at,
        updated_at=first.updated_at,
        key=first.key,
        name="Changed without revision",
        revision=1,
        metadata=dict(first.metadata),
    )
    with pytest.raises(ConflictError) as same_revision:
        repository.save(same_revision_different_state)
    assert same_revision.value.code == "campaign.revision.conflict"

    skipped_revision = Campaign(
        id=first.id,
        created_at=first.created_at,
        updated_at=first.updated_at + timedelta(minutes=1),
        key=first.key,
        name="Skipped",
        revision=3,
        metadata=dict(first.metadata),
    )
    with pytest.raises(ConflictError) as skipped:
        repository.save(skipped_revision)
    assert skipped.value.code == "campaign.revision.conflict"

    revised = Campaign(
        id=first.id,
        created_at=first.created_at,
        updated_at=first.updated_at + timedelta(minutes=1),
        key=first.key,
        name="Revision 2",
        revision=2,
        metadata={"source": "revision-2"},
    )
    repository.save(revised)
    session.flush()

    assert repository.get(first.id) == revised
    assert repository.get(first.id).revision == 2


def test_campaign_repository_rejects_non_initial_revision_on_insert(
    session: Session,
) -> None:
    repository = SQLAlchemyCampaignRepository(session)
    invalid = _campaign(
        431,
        key="invalid-initial-revision",
        name="Invalid Initial Revision",
        revision=2,
    )

    with pytest.raises(ConflictError) as error:
        repository.save(invalid)

    assert error.value.code == "campaign.revision.conflict"
    assert error.value.context == {"expected": 1, "actual": 2}
