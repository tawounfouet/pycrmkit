"""Run Organization repository contracts against the official SQLAlchemy adapter."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest
from sqlalchemy.orm import Session
from pycrmkit.organizations import (
    Organization,
    OrganizationDomain,
    OrganizationId,
    OrganizationRepository,
)
from pycrmkit.storage.sqlalchemy.repositories import SQLAlchemyOrganizationRepository

from ...contracts.organizations_repository import OrganizationRepositoryContract


@pytest.fixture
def repository(session: Session) -> OrganizationRepository:
    repository = SQLAlchemyOrganizationRepository(session)
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


class TestSQLAlchemyOrganizationRepository(OrganizationRepositoryContract):
    """Official SQLAlchemy adapter must satisfy the Organization contract."""

