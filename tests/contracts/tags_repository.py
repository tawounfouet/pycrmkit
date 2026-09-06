"""Reusable TagRepository conformance assertions."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from pycrmkit.core.ids import EntityId
from pycrmkit.core.pagination import OffsetPageRequest
from pycrmkit.core.references import EntityReference
from pycrmkit.exceptions import DuplicateError, NotFoundError
from pycrmkit.tags.entities import Tag, TagAssignment, TagAssignmentId, TagId
from pycrmkit.tags.queries import TagQuery
from pycrmkit.tags.repository import TagRepository
from pycrmkit.tags.value_objects import TagName

NOW = datetime(2026, 9, 6, 12, 0, tzinfo=UTC)


def make_tag(number: int, name: str) -> Tag:
    return Tag(
        id=TagId(UUID(int=number)),
        created_at=NOW,
        updated_at=NOW,
        name=TagName(name),
    )


def assert_tag_repository_contract(repository: TagRepository) -> None:
    vip = make_tag(2, "VIP")
    priority = make_tag(1, "Priority")
    repository.save(vip)
    repository.save(priority)

    assert repository.get(vip.id) == vip
    assert repository.find(vip.id) == vip
    assert repository.find(TagId(UUID(int=999))) is None
    assert repository.find_by_normalized("vip") == vip

    with pytest.raises(NotFoundError):
        repository.get(TagId(UUID(int=999)))

    with pytest.raises(DuplicateError):
        repository.save(make_tag(3, " vip "))

    page = repository.search(TagQuery(), OffsetPageRequest(limit=1, offset=0))
    assert page.total == 2
    assert [tag.id for tag in page.items] == [priority.id]

    match = repository.search(
        TagQuery(name=TagName("PRIORITY")),
        OffsetPageRequest(),
    )
    assert match.items == (priority,)

    entity = EntityReference("contact", EntityId(UUID(int=100)))
    assignment = TagAssignment(
        id=TagAssignmentId(UUID(int=10)),
        created_at=NOW,
        updated_at=NOW,
        tag_id=vip.id,
        entity=entity,
    )
    repository.assign(assignment)
    with pytest.raises(DuplicateError):
        repository.assign(
            TagAssignment(
                id=TagAssignmentId(UUID(int=11)),
                created_at=NOW,
                updated_at=NOW,
                tag_id=vip.id,
                entity=entity,
            )
        )
    assert repository.list_for_entity(entity, OffsetPageRequest()).items == (vip,)
    assert repository.remove(vip.id, entity, NOW) is True
    assert repository.remove(vip.id, entity, NOW) is False
