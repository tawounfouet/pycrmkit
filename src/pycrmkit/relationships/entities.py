"""Relationship aggregate root."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from pycrmkit.core.entities import TimestampedEntity
from pycrmkit.core.ids import UUIDId
from pycrmkit.core.time import as_utc
from pycrmkit.exceptions import InvalidStateError, ValidationError
from pycrmkit.relationships.policies import (
    normalize_optional_text,
    normalize_validity,
    validate_endpoints,
)
from pycrmkit.relationships.value_objects import RelationshipEndpoint, RelationshipType


class RelationshipId(UUIDId):
    """Strongly typed identifier for a Relationship."""


@dataclass(eq=False, slots=True)
class Relationship(TimestampedEntity[RelationshipId]):
    """Directional typed relationship between two CRM entities."""

    source: RelationshipEndpoint
    target: RelationshipEndpoint
    relationship_type: RelationshipType
    valid_from: datetime
    role: str | None = None
    title: str | None = None
    is_primary: bool = False
    valid_until: datetime | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        TimestampedEntity.__post_init__(self)
        validate_endpoints(self.source, self.target)
        self.role = normalize_optional_text(self.role)
        self.title = normalize_optional_text(self.title)
        self.valid_from, self.valid_until = normalize_validity(self.valid_from, self.valid_until)
        self.metadata = dict(self.metadata)

    @property
    def is_ended(self) -> bool:
        """Return whether the relationship has an explicit end timestamp."""
        return self.valid_until is not None

    def is_active(self, at: datetime) -> bool:
        """Evaluate activity using [valid_from, valid_until) interval semantics."""
        instant = as_utc(at)
        return self.valid_from <= instant and (
            self.valid_until is None or instant < self.valid_until
        )

    def end(self, at: datetime) -> None:
        """End the relationship idempotently at an explicit timestamp."""
        timestamp = as_utc(at)
        if self.valid_until is not None:
            return
        if timestamp <= self.valid_from:
            raise ValidationError(
                "relationship end must be later than valid_from",
                code="relationship.end.invalid_timestamp",
            )
        self.valid_until = timestamp
        self.updated_at = timestamp

    def ensure_mutable(self) -> None:
        """Reject profile mutation after the relationship has ended."""
        if self.valid_until is not None:
            raise InvalidStateError(
                "ended relationships cannot be updated",
                code="relationship.ended",
                context={"relationship_id": str(self.id)},
            )
