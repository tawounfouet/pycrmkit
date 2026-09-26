"""Run Contact repository contracts against the official SQLAlchemy adapter."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest
from sqlalchemy.orm import Session
from pycrmkit.contacts import Contact, ContactEmail, ContactId, ContactRepository
from pycrmkit.storage.sqlalchemy.repositories import SQLAlchemyContactRepository

from ...contracts.contacts_repository import ContactRepositoryContract


@pytest.fixture
def repository(session: Session) -> ContactRepository:
    repository = SQLAlchemyContactRepository(session)
    assert isinstance(repository, ContactRepository)
    return repository


@pytest.fixture
def contact() -> Contact:
    now = datetime(2026, 9, 6, 10, 0, tzinfo=UTC)
    return Contact(
        id=ContactId(UUID("00000000-0000-4000-8000-000000000011")),
        created_at=now,
        updated_at=now,
        first_name="Alpha",
        emails=(ContactEmail("contact@example.com", is_primary=True),),
    )


@pytest.fixture
def second_contact() -> Contact:
    now = datetime(2026, 9, 6, 10, 1, tzinfo=UTC)
    return Contact(
        id=ContactId(UUID("00000000-0000-4000-8000-000000000012")),
        created_at=now,
        updated_at=now,
        first_name="Beta",
    )


@pytest.fixture
def missing_contact_id() -> ContactId:
    return ContactId(UUID("00000000-0000-4000-8000-000000009999"))


class TestSQLAlchemyContactRepository(ContactRepositoryContract):
    """Official SQLAlchemy adapter must satisfy the reusable Contact contract."""

