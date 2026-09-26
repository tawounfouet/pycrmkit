"""Run ContactRepository contracts against the Django ORM adapter."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from pycrmkit.contacts import Contact, ContactEmail, ContactId, ContactRepository
from pycrmkit.integrations.django.repositories import DjangoContactRepository

from ...contracts.contacts_repository import ContactRepositoryContract


@pytest.fixture
def repository() -> ContactRepository:
    repository = DjangoContactRepository()
    assert isinstance(repository, ContactRepository)
    return repository


@pytest.fixture
def contact() -> Contact:
    now = datetime(2026, 9, 26, 17, 0, tzinfo=UTC)
    return Contact(
        id=ContactId(UUID("00000000-0000-4000-8000-000000008011")),
        created_at=now,
        updated_at=now,
        first_name="Alpha",
        emails=(ContactEmail("contact@example.com", is_primary=True),),
    )


@pytest.fixture
def second_contact() -> Contact:
    now = datetime(2026, 9, 26, 17, 1, tzinfo=UTC)
    return Contact(
        id=ContactId(UUID("00000000-0000-4000-8000-000000008012")),
        created_at=now,
        updated_at=now,
        first_name="Beta",
    )


@pytest.fixture
def missing_contact_id() -> ContactId:
    return ContactId(UUID("00000000-0000-4000-8000-000000008999"))


class TestDjangoContactRepository(ContactRepositoryContract):
    """Official Django adapter must satisfy the reusable Contact contract."""
