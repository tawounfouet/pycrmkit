"""Production-reference persistence qualification against live PostgreSQL."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from decimal import Decimal
from threading import Barrier
from uuid import UUID

import pytest
from sqlalchemy import Engine, inspect
from sqlalchemy.orm import Session, sessionmaker

from pycrmkit.contacts import Contact, ContactId
from pycrmkit.custom_fields import (
    CustomFieldDefinition,
    CustomFieldDefinitionId,
    CustomFieldType,
    CustomFieldValue,
    CustomFieldValueId,
)
from pycrmkit.core.references import EntityReference
from pycrmkit.exceptions import DuplicateError, RepositoryError
from pycrmkit.leads import Lead, LeadId
from pycrmkit.opportunities import Opportunity, OpportunityId
from pycrmkit.storage.sqlalchemy import Base, SQLAlchemyUnitOfWork
from pycrmkit.tags import Tag, TagId, TagName

pytestmark = pytest.mark.postgresql

NOW = datetime(2026, 9, 26, 14, 0, tzinfo=UTC)


def test_postgresql_metadata_creates_expected_constraints_and_indexes(
    postgres_engine: Engine,
) -> None:
    inspector = inspect(postgres_engine)

    assert set(inspector.get_table_names()) == set(Base.metadata.tables)

    tag_uniques = {
        constraint["name"]
        for constraint in inspector.get_unique_constraints("pycrmkit_tags")
    }
    assignment_uniques = {
        constraint["name"]
        for constraint in inspector.get_unique_constraints(
            "pycrmkit_tag_assignments"
        )
    }
    webhook_indexes = {
        index["name"]
        for index in inspector.get_indexes("pycrmkit_webhook_deliveries")
    }

    assert "uq_pycrmkit_tags_normalized_name" in tag_uniques
    assert "uq_pycrmkit_tag_assignments_target" in assignment_uniques
    assert "ix_pycrmkit_webhook_delivery_subscription_event" in webhook_indexes


def test_postgresql_foreign_key_violation_is_backend_neutral(
    postgres_session_factory: sessionmaker[Session],
) -> None:
    missing_contact = ContactId(
        UUID("00000000-0000-4000-8000-000000009901")
    )
    lead = Lead(
        id=LeadId(UUID("00000000-0000-4000-8000-000000009902")),
        created_at=NOW,
        updated_at=NOW,
        contact_id=missing_contact,
    )

    with pytest.raises(RepositoryError) as error:
        with SQLAlchemyUnitOfWork(postgres_session_factory) as uow:
            uow.leads.save(lead)
            uow.commit()

    assert error.value.code == "repository.foreign_key_violation"
    assert error.value.context["sqlstate"] == "23503"
    assert "statement" not in error.value.context
    assert "params" not in error.value.context


def test_postgresql_round_trips_unicode_decimal_timezone_json_and_custom_fields(
    postgres_session_factory: sessionmaker[Session],
) -> None:
    contact = Contact(
        id=ContactId(UUID("00000000-0000-4000-8000-000000009911")),
        created_at=NOW,
        updated_at=NOW,
        display_name="Zoë 東京",
        metadata={"city": "Paris", "note": "élève 東京"},
    )
    opportunity = Opportunity(
        id=OpportunityId(UUID("00000000-0000-4000-8000-000000009912")),
        created_at=NOW,
        updated_at=NOW,
        name="International expansion",
        contact_id=contact.id,
        estimated_value=Decimal("123456.7890"),
        currency="EUR",
        probability=Decimal("0.375000"),
    )
    definition = CustomFieldDefinition(
        id=CustomFieldDefinitionId(
            UUID("00000000-0000-4000-8000-000000009913")
        ),
        created_at=NOW,
        updated_at=NOW,
        key="account_context",
        label="Account Context",
        field_type=CustomFieldType.JSON,
        schema_version=1,
        applies_to=("contact",),
    )
    value = CustomFieldValue(
        id=CustomFieldValueId(
            UUID("00000000-0000-4000-8000-000000009914")
        ),
        created_at=NOW,
        updated_at=NOW,
        definition_id=definition.id,
        entity=EntityReference("contact", contact.id),
        schema_version=1,
        value={"segment": "Élite", "region": "東京"},
    )

    with SQLAlchemyUnitOfWork(postgres_session_factory) as uow:
        uow.contacts.save(contact)
        uow.opportunities.save(opportunity)
        uow.custom_fields.save_definition(definition)
        uow.custom_fields.save_value(value)
        uow.commit()

    with SQLAlchemyUnitOfWork(postgres_session_factory) as uow:
        loaded_contact = uow.contacts.get(contact.id)
        loaded_opportunity = uow.opportunities.get(opportunity.id)
        loaded_definition = uow.custom_fields.get_definition(definition.id)
        loaded_value = uow.custom_fields.get_value(definition.id, value.entity)

    assert loaded_contact == contact
    assert loaded_contact.created_at == NOW
    assert loaded_opportunity.estimated_value == Decimal("123456.7890")
    assert loaded_opportunity.probability == Decimal("0.375000")
    assert loaded_definition == definition
    assert loaded_value == value


def test_concurrent_normalized_tag_collision_maps_to_duplicate_error(
    postgres_session_factory: sessionmaker[Session],
) -> None:
    barrier = Barrier(2)
    tags = (
        Tag(
            id=TagId(UUID("00000000-0000-4000-8000-000000009921")),
            created_at=NOW,
            updated_at=NOW,
            name=TagName("VIP"),
        ),
        Tag(
            id=TagId(UUID("00000000-0000-4000-8000-000000009922")),
            created_at=NOW,
            updated_at=NOW,
            name=TagName("vip"),
        ),
    )

    def write(tag: Tag) -> str:
        try:
            with SQLAlchemyUnitOfWork(postgres_session_factory) as uow:
                uow.tags.save(tag)
                barrier.wait(timeout=10)
                uow.commit()
            return "committed"
        except DuplicateError as error:
            assert error.code == "repository.duplicate"
            assert error.context["sqlstate"] == "23505"
            return "duplicate"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = tuple(pool.map(write, tags))

    assert sorted(outcomes) == ["committed", "duplicate"]

    with SQLAlchemyUnitOfWork(postgres_session_factory) as uow:
        persisted = uow.tags.find_by_normalized("vip")
        assert persisted is not None
        assert persisted.name.normalized == "vip"
