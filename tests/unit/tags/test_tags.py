from datetime import UTC, datetime
from uuid import UUID

import pytest

from pycrmkit.core.ids import EntityId
from pycrmkit.core.references import EntityReference
from pycrmkit.core.time import FixedClock
from pycrmkit.exceptions import DuplicateError, NotFoundError
from pycrmkit.tags.entities import TagAssignmentId, TagId
from pycrmkit.tags.queries import TagQuery
from pycrmkit.tags.services import TagService
from pycrmkit.tags.value_objects import TagName
from tests.contracts.test_tags_repository_reference import ReferenceTagRepository


class SequentialFactory:
    def __init__(self) -> None:
        self.counter = 1

    def new(self, id_type):  # type: ignore[no-untyped-def]
        value = UUID(int=self.counter)
        self.counter += 1
        return id_type(value)


def test_tag_name_preserves_label_and_normalizes_comparison() -> None:
    name = TagName("  VIP   Client ")
    assert name.value == "VIP Client"
    assert name.normalized == "vip client"


def test_tag_service_create_assign_list_remove() -> None:
    repository = ReferenceTagRepository()
    service = TagService(
        repository=repository,
        id_factory=SequentialFactory(),
        clock=FixedClock(datetime(2026, 9, 6, 16, 0, tzinfo=UTC)),
    )
    tag = service.create("VIP")
    entity = EntityReference("contact", EntityId(UUID(int=100)))

    assignment = service.assign(tag.id, entity)
    assert isinstance(assignment.id, TagAssignmentId)
    assert service.list_for_entity(entity).items == (tag,)
    assert service.remove(tag.id, entity) is True
    assert service.remove(tag.id, entity) is False
    assert service.list_for_entity(entity).items == ()


def test_duplicate_tag_name_is_rejected_case_insensitively() -> None:
    repository = ReferenceTagRepository()
    service = TagService(repository=repository, id_factory=SequentialFactory())
    service.create("Priority")
    with pytest.raises(DuplicateError):
        service.create(" priority ")


def test_duplicate_assignment_is_rejected() -> None:
    repository = ReferenceTagRepository()
    service = TagService(repository=repository, id_factory=SequentialFactory())
    tag = service.create("Partner")
    entity = EntityReference("organization", EntityId(UUID(int=500)))
    service.assign(tag.id, entity)
    with pytest.raises(DuplicateError):
        service.assign(tag.id, entity)


def test_assign_requires_existing_tag() -> None:
    repository = ReferenceTagRepository()
    service = TagService(repository=repository, id_factory=SequentialFactory())
    with pytest.raises(NotFoundError):
        service.assign(
            TagId(UUID(int=999)),
            EntityReference("contact", EntityId(UUID(int=1))),
        )


def test_tag_search_by_normalized_name() -> None:
    repository = ReferenceTagRepository()
    service = TagService(repository=repository, id_factory=SequentialFactory())
    service.create("Needs Follow Up")
    result = service.search(TagQuery(name=TagName("needs follow up")))
    assert [tag.name.value for tag in result.items] == ["Needs Follow Up"]
