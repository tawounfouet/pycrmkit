"""Run Organization repository contracts against the official Memory adapter."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from pycrmkit.organizations import (
    Organization,
    OrganizationDomain,
    OrganizationId,
    OrganizationRepository,
)
from pycrmkit.storage.memory import MemoryOrganizationRepository

from ...contracts.organizations_repository import OrganizationRepositoryContract


@pytest.fixture
def repository() -> OrganizationRepository:
    repository = MemoryOrganizationRepository()
    assert isinstance(repository, OrganizationRepository)
    return repository


@pytest.fixture
def organization() -> Organization:
    now = datetime(2026, 9, 6, 12, 0, tzinfo=UTC)
    return Organization(
        id=OrganizationId(UUID("00000000-0000-4000-8000-000000000111")),
        created_at=now,
        updated_at=now,
        legal_name="Alpha SAS",
        domains=(OrganizationDomain("example.com", is_primary=True),),
    )


@pytest.fixture
def second_organization() -> Organization:
    now = datetime(2026, 9, 6, 12, 1, tzinfo=UTC)
    return Organization(
        id=OrganizationId(UUID("00000000-0000-4000-8000-000000000112")),
        created_at=now,
        updated_at=now,
        legal_name="Beta SAS",
    )


@pytest.fixture
def missing_organization_id() -> OrganizationId:
    return OrganizationId(UUID("00000000-0000-4000-8000-000000009999"))


class TestMemoryOrganizationRepository(OrganizationRepositoryContract):
    """Official Memory adapter must satisfy the Organization contract."""


def test_organization_repository_isolates_mutations(organization: Organization) -> None:
    repository = MemoryOrganizationRepository()
    repository.save(organization)
    organization.source = "changed"
    assert repository.get(organization.id).source is None

    loaded = repository.get(organization.id)
    loaded.source = "changed-again"
    assert repository.get(organization.id).source is None
