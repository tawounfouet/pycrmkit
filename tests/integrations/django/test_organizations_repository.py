"""Run OrganizationRepository contracts against the Django ORM adapter."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from pycrmkit.integrations.django.repositories import DjangoOrganizationRepository
from pycrmkit.organizations import (
    Organization,
    OrganizationDomain,
    OrganizationId,
    OrganizationRepository,
)
from tests.contracts.organizations_repository import OrganizationRepositoryContract


@pytest.fixture
def repository() -> OrganizationRepository:
    repository = DjangoOrganizationRepository()
    assert isinstance(repository, OrganizationRepository)
    return repository


@pytest.fixture
def organization() -> Organization:
    now = datetime(2026, 9, 26, 18, 0, tzinfo=UTC)
    return Organization(
        id=OrganizationId(UUID("00000000-0000-4000-8000-000000008111")),
        created_at=now,
        updated_at=now,
        legal_name="Alpha SAS",
        domains=(OrganizationDomain("example.com", is_primary=True),),
    )


@pytest.fixture
def second_organization() -> Organization:
    now = datetime(2026, 9, 26, 18, 1, tzinfo=UTC)
    return Organization(
        id=OrganizationId(UUID("00000000-0000-4000-8000-000000008112")),
        created_at=now,
        updated_at=now,
        legal_name="Beta SAS",
    )


@pytest.fixture
def missing_organization_id() -> OrganizationId:
    return OrganizationId(UUID("00000000-0000-4000-8000-000000008999"))


class TestDjangoOrganizationRepository(OrganizationRepositoryContract):
    """Official Django adapter must satisfy the reusable Organization contract."""
