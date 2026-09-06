from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from pycrmkit.contacts import ContactId
from pycrmkit.exceptions import ConflictError, InvalidStateError, ValidationError
from pycrmkit.organizations import OrganizationId
from pycrmkit.relationships import (
    Relationship,
    RelationshipEndpoint,
    RelationshipId,
    RelationshipType,
)


def _relationship() -> Relationship:
    now = datetime(2026, 9, 6, 15, 0, tzinfo=UTC)
    return Relationship(
        id=RelationshipId(UUID("00000000-0000-4000-8000-000000000221")),
        created_at=now,
        updated_at=now,
        source=RelationshipEndpoint.contact(
            ContactId(UUID("00000000-0000-4000-8000-000000000222"))
        ),
        target=RelationshipEndpoint.organization(
            OrganizationId(UUID("00000000-0000-4000-8000-000000000223"))
        ),
        relationship_type=RelationshipType("employment"),
        valid_from=now,
        role=" Customer Success ",
        title=" Account Manager ",
        is_primary=True,
    )


def test_relationship_normalizes_role_title_and_validity() -> None:
    relationship = _relationship()
    assert relationship.role == "Customer Success"
    assert relationship.title == "Account Manager"
    assert relationship.is_active(relationship.valid_from)
    assert relationship.is_ended is False


def test_relationship_rejects_self_link() -> None:
    now = datetime(2026, 9, 6, 15, 0, tzinfo=UTC)
    endpoint = RelationshipEndpoint.contact(
        ContactId(UUID("00000000-0000-4000-8000-000000000222"))
    )
    with pytest.raises(ConflictError):
        Relationship(
            id=RelationshipId(UUID("00000000-0000-4000-8000-000000000221")),
            created_at=now,
            updated_at=now,
            source=endpoint,
            target=endpoint,
            relationship_type=RelationshipType("peer"),
            valid_from=now,
        )


def test_relationship_can_represent_historical_validity_before_record_creation() -> None:
    relationship = _relationship()
    historical_start = relationship.created_at - timedelta(days=365)
    historical = Relationship(
        id=relationship.id,
        created_at=relationship.created_at,
        updated_at=relationship.updated_at,
        source=relationship.source,
        target=relationship.target,
        relationship_type=relationship.relationship_type,
        valid_from=historical_start,
    )
    assert historical.valid_from == historical_start


def test_relationship_validity_uses_half_open_interval() -> None:
    relationship = _relationship()
    ended_at = relationship.valid_from + timedelta(hours=2)
    relationship.end(ended_at)

    assert relationship.is_active(ended_at - timedelta(microseconds=1))
    assert relationship.is_active(ended_at) is False
    assert relationship.is_ended is True


def test_relationship_end_is_idempotent_and_blocks_mutation() -> None:
    relationship = _relationship()
    ended_at = relationship.valid_from + timedelta(hours=1)
    relationship.end(ended_at)
    relationship.end(ended_at + timedelta(hours=1))

    assert relationship.valid_until == ended_at
    with pytest.raises(InvalidStateError):
        relationship.ensure_mutable()


def test_relationship_rejects_empty_or_reverse_validity() -> None:
    relationship = _relationship()
    with pytest.raises(ValidationError):
        relationship.end(relationship.valid_from)
