"""Execute RelationshipRepository contracts against a test-only reference adapter."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from uuid import UUID

import pytest

from pycrmkit.contacts import ContactId
from pycrmkit.core import OffsetPageRequest, Page
from pycrmkit.exceptions import NotFoundError
from pycrmkit.organizations import OrganizationId
from pycrmkit.relationships import (
    Relationship,
    RelationshipEndpoint,
    RelationshipId,
    RelationshipQuery,
    RelationshipRepository,
    RelationshipType,
)
from tests.contracts.relationships_repository import RelationshipRepositoryContract


class ReferenceRelationshipRepository:
    """Test-only reference implementation, not the public Memory Adapter."""

    def __init__(self) -> None:
        self._relationships: dict[RelationshipId, Relationship] = {}

    def get(self, relationship_id: RelationshipId) -> Relationship:
        relationship = self.find(relationship_id)
        if relationship is None:
            raise NotFoundError(
                "Relationship not found",
                code="relationship.not_found",
                context={"relationship_id": str(relationship_id)},
            )
        return relationship

    def find(self, relationship_id: RelationshipId) -> Relationship | None:
        relationship = self._relationships.get(relationship_id)
        return deepcopy(relationship) if relationship is not None else None

    def save(self, relationship: Relationship) -> None:
        self._relationships[relationship.id] = deepcopy(relationship)

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
        relationships = list(self._relationships.values())
        if query.active_at is not None:
            relationships = [item for item in relationships if item.is_active(query.active_at)]
        elif not query.include_ended:
            relationships = [item for item in relationships if not item.is_ended]
        if query.entity is not None:
            relationships = [
                item
                for item in relationships
                if item.source == query.entity or item.target == query.entity
            ]
        if query.source is not None:
            relationships = [item for item in relationships if item.source == query.source]
        if query.target is not None:
            relationships = [item for item in relationships if item.target == query.target]
        if query.relationship_type is not None:
            relationships = [
                item
                for item in relationships
                if item.relationship_type == query.relationship_type
            ]
        if query.is_primary is not None:
            relationships = [item for item in relationships if item.is_primary is query.is_primary]
        relationships.sort(key=lambda item: (item.created_at, item.id))
        total = len(relationships)
        selected = relationships[page.offset : page.offset + page.limit]
        return Page(
            items=tuple(deepcopy(selected)),
            limit=page.limit,
            offset=page.offset,
            total=total,
        )


@pytest.fixture
def repository() -> RelationshipRepository:
    repository = ReferenceRelationshipRepository()
    assert isinstance(repository, RelationshipRepository)
    return repository


def _contact_endpoint(value: str) -> RelationshipEndpoint:
    return RelationshipEndpoint.contact(ContactId(UUID(value)))


def _organization_endpoint(value: str) -> RelationshipEndpoint:
    return RelationshipEndpoint.organization(OrganizationId(UUID(value)))


@pytest.fixture
def relationship() -> Relationship:
    now = datetime(2026, 9, 6, 15, 0, tzinfo=UTC)
    return Relationship(
        id=RelationshipId(UUID("00000000-0000-4000-8000-000000000241")),
        created_at=now,
        updated_at=now,
        source=_contact_endpoint("00000000-0000-4000-8000-000000000242"),
        target=_organization_endpoint("00000000-0000-4000-8000-000000000243"),
        relationship_type=RelationshipType("employment"),
        valid_from=now,
        title="Account Manager",
        is_primary=True,
    )


@pytest.fixture
def second_relationship() -> Relationship:
    now = datetime(2026, 9, 6, 15, 1, tzinfo=UTC)
    return Relationship(
        id=RelationshipId(UUID("00000000-0000-4000-8000-000000000244")),
        created_at=now,
        updated_at=now,
        source=_organization_endpoint("00000000-0000-4000-8000-000000000245"),
        target=_organization_endpoint("00000000-0000-4000-8000-000000000246"),
        relationship_type=RelationshipType("subsidiary"),
        valid_from=now,
    )


@pytest.fixture
def missing_relationship_id() -> RelationshipId:
    return RelationshipId(UUID("00000000-0000-4000-8000-000000009999"))


class TestReferenceRelationshipRepository(RelationshipRepositoryContract):
    """Concrete execution of the reusable contract suite."""
