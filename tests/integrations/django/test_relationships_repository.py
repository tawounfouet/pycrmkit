"""Run RelationshipRepository contracts against the Django ORM adapter."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from pycrmkit.contacts import ContactId
from pycrmkit.integrations.django.repositories import DjangoRelationshipRepository
from pycrmkit.organizations import OrganizationId
from pycrmkit.relationships import (
    Relationship,
    RelationshipEndpoint,
    RelationshipId,
    RelationshipRepository,
    RelationshipType,
)

from tests.contracts.relationships_repository import RelationshipRepositoryContract


def _contact_endpoint(value: str) -> RelationshipEndpoint:
    return RelationshipEndpoint.contact(ContactId(UUID(value)))


def _organization_endpoint(value: str) -> RelationshipEndpoint:
    return RelationshipEndpoint.organization(OrganizationId(UUID(value)))


@pytest.fixture
def repository() -> RelationshipRepository:
    repository = DjangoRelationshipRepository()
    assert isinstance(repository, RelationshipRepository)
    return repository


@pytest.fixture
def relationship() -> Relationship:
    now = datetime(2026, 9, 26, 19, 0, tzinfo=UTC)
    return Relationship(
        id=RelationshipId(UUID("00000000-0000-4000-8000-000000008241")),
        created_at=now,
        updated_at=now,
        source=_contact_endpoint("00000000-0000-4000-8000-000000008242"),
        target=_organization_endpoint("00000000-0000-4000-8000-000000008243"),
        relationship_type=RelationshipType("employment"),
        valid_from=now,
        title="Account Manager",
        is_primary=True,
    )


@pytest.fixture
def second_relationship() -> Relationship:
    now = datetime(2026, 9, 26, 19, 1, tzinfo=UTC)
    return Relationship(
        id=RelationshipId(UUID("00000000-0000-4000-8000-000000008244")),
        created_at=now,
        updated_at=now,
        source=_organization_endpoint("00000000-0000-4000-8000-000000008245"),
        target=_organization_endpoint("00000000-0000-4000-8000-000000008246"),
        relationship_type=RelationshipType("subsidiary"),
        valid_from=now,
    )


@pytest.fixture
def missing_relationship_id() -> RelationshipId:
    return RelationshipId(UUID("00000000-0000-4000-8000-000000008999"))


class TestDjangoRelationshipRepository(RelationshipRepositoryContract):
    """Official Django adapter must satisfy the reusable Relationship contract."""
