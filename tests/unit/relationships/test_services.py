from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from uuid import UUID

from pycrmkit.contacts import ContactId
from pycrmkit.core import FixedClock, OffsetPageRequest, Page
from pycrmkit.exceptions import NotFoundError
from pycrmkit.organizations import OrganizationId
from pycrmkit.relationships import (
    Relationship,
    RelationshipEndpoint,
    RelationshipId,
    RelationshipQuery,
    RelationshipRepository,
    RelationshipService,
    RelationshipType,
    RelationshipUpdate,
)


class DeterministicIdFactory:
    def new(self, id_type):
        return id_type(UUID("00000000-0000-4000-8000-000000000231"))


class ServiceRepository:
    def __init__(self) -> None:
        self.relationships: dict[RelationshipId, Relationship] = {}

    def get(self, relationship_id: RelationshipId) -> Relationship:
        relationship = self.find(relationship_id)
        if relationship is None:
            raise NotFoundError("Relationship not found", code="relationship.not_found")
        return relationship

    def find(self, relationship_id: RelationshipId) -> Relationship | None:
        relationship = self.relationships.get(relationship_id)
        return deepcopy(relationship) if relationship else None

    def save(self, relationship: Relationship) -> None:
        self.relationships[relationship.id] = deepcopy(relationship)

    def end(self, relationship_id: RelationshipId, ended_at: datetime) -> Relationship:
        relationship = self.get(relationship_id)
        relationship.end(ended_at)
        self.save(relationship)
        return relationship

    def search(
        self,
        query: RelationshipQuery,
        page: OffsetPageRequest,
    ) -> Page[Relationship]:
        items = list(self.relationships.values())
        if not query.include_ended and query.active_at is None:
            items = [item for item in items if not item.is_ended]
        if query.active_at is not None:
            items = [item for item in items if item.is_active(query.active_at)]
        items.sort(key=lambda item: (item.created_at, item.id))
        selected = items[page.offset : page.offset + page.limit]
        return Page(tuple(deepcopy(selected)), page.limit, page.offset, len(items))


def test_relationship_service_create_update_end_and_search() -> None:
    repository = ServiceRepository()
    assert isinstance(repository, RelationshipRepository)
    clock = FixedClock(datetime(2026, 9, 6, 15, 0, tzinfo=UTC))
    service = RelationshipService(
        repository=repository,
        id_factory=DeterministicIdFactory(),
        clock=clock,
    )
    source = RelationshipEndpoint.contact(
        ContactId(UUID("00000000-0000-4000-8000-000000000232"))
    )
    target = RelationshipEndpoint.organization(
        OrganizationId(UUID("00000000-0000-4000-8000-000000000233"))
    )

    relationship = service.create(
        source=source,
        target=target,
        relationship_type=RelationshipType("employment"),
        role="Customer Success",
        title="Account Manager",
        is_primary=True,
    )

    assert str(relationship.id) == "00000000-0000-4000-8000-000000000231"
    assert relationship.valid_from == clock.now()
    assert service.get(relationship.id) == relationship

    clock.advance(timedelta(minutes=5))
    updated = service.update(
        relationship.id,
        RelationshipUpdate(title="Senior Account Manager", is_primary=False),
    )
    assert updated.title == "Senior Account Manager"
    assert updated.is_primary is False
    assert service.search().items == (updated,)

    clock.advance(timedelta(minutes=5))
    ended = service.end(relationship.id)
    assert ended.valid_until == clock.now()
    assert service.search().items == ()
    assert service.search(RelationshipQuery(include_ended=True)).items == (ended,)
