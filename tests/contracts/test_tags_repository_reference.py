"""Execute Tag repository contracts against a test-only reference repository."""

from __future__ import annotations

from datetime import datetime

from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.core.references import EntityReference
from pycrmkit.exceptions import DuplicateError, NotFoundError
from pycrmkit.tags.entities import Tag, TagAssignment, TagId
from pycrmkit.tags.queries import TagQuery
from tests.contracts.tags_repository import assert_tag_repository_contract


class ReferenceTagRepository:
    """Minimal test-only implementation; not the future Memory adapter."""

    def __init__(self) -> None:
        self.tags: dict[TagId, Tag] = {}
        self.assignments: dict[tuple[TagId, EntityReference], TagAssignment] = {}

    def get(self, tag_id: TagId) -> Tag:
        found = self.find(tag_id)
        if found is None:
            raise NotFoundError("tag not found", code="tag.not_found")
        return found

    def find(self, tag_id: TagId) -> Tag | None:
        return self.tags.get(tag_id)

    def find_by_normalized(self, normalized_name: str) -> Tag | None:
        return next(
            (tag for tag in self.tags.values() if tag.name.normalized == normalized_name),
            None,
        )

    def save(self, tag: Tag) -> None:
        existing = self.find_by_normalized(tag.name.normalized)
        if existing is not None and existing.id != tag.id:
            raise DuplicateError("duplicate tag", code="tag.duplicate")
        self.tags[tag.id] = tag

    def search(self, query: TagQuery, page: OffsetPageRequest) -> Page[Tag]:
        items = list(self.tags.values())
        if query.name is not None:
            items = [item for item in items if item.name.normalized == query.name.normalized]
        items.sort(key=lambda item: (item.created_at, str(item.id)))
        total = len(items)
        selected = tuple(items[page.offset : page.offset + page.limit])
        return Page(items=selected, limit=page.limit, offset=page.offset, total=total)

    def assign(self, assignment: TagAssignment) -> TagAssignment:
        key = (assignment.tag_id, assignment.entity)
        if key in self.assignments:
            raise DuplicateError("duplicate assignment", code="tag.assignment.duplicate")
        self.assignments[key] = assignment
        return assignment

    def remove(self, tag_id: TagId, entity: EntityReference, removed_at: datetime) -> bool:
        del removed_at
        return self.assignments.pop((tag_id, entity), None) is not None

    def list_for_entity(
        self,
        entity: EntityReference,
        page: OffsetPageRequest,
    ) -> Page[Tag]:
        tag_ids = {
            tag_id
            for (tag_id, assigned_entity), _assignment in self.assignments.items()
            if assigned_entity == entity
        }
        items = [tag for tag in self.tags.values() if tag.id in tag_ids]
        items.sort(key=lambda item: (item.name.normalized, str(item.id)))
        total = len(items)
        selected = tuple(items[page.offset : page.offset + page.limit])
        return Page(items=selected, limit=page.limit, offset=page.offset, total=total)


def test_reference_repository_passes_contract() -> None:
    assert_tag_repository_contract(ReferenceTagRepository())
