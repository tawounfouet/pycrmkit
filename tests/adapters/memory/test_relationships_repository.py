"""Run Relationship repository contracts against the official Memory adapter."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from pycrmkit.contacts import ContactId
from pycrmkit.organizations import OrganizationId
from pycrmkit.relationships import (
    Relationship,
    RelationshipEndpoint,
    RelationshipId,
    RelationshipRepository,
    RelationshipType,
)
from pycrmkit.storage.memory import MemoryRelationshipRepository
from ...contracts.relationships_repository import RelationshipRepositoryContract


def _contact_endpoint(value: str) -> RelationshipEndpoint:
    return RelationshipEndpoint.contact(ContactId(UUID(value)))


def _organization_endpoint(value: str) -> RelationshipEndpoint:
    return RelationshipEndpoint.organization(OrganizationId(UUID(value)))


@pytest.fixture
def repository() -> RelationshipRepository:
    repository = MemoryRelationshipRepository()
    assert isinstance(repository, RelationshipRepository)
    return repository


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


class TestMemoryRelationshipRepository(RelationshipRepositoryContract):
    """Official Memory adapter must satisfy the Relationship contract."""


def test_relationship_repository_isolates_mutations(relationship: Relationship) -> None:
    repository = MemoryRelationshipRepository()
    repository.save(relationship)
    relationship.title = "Changed"
    assert repository.get(relationship.id).title == "Account Manager"

    loaded = repository.get(relationship.id)
    loaded.title = "Changed again"
    assert repository.get(relationship.id).title == "Account Manager"
