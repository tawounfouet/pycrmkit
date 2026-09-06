"""Relationship-domain normalization and invariant policies."""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime

from pycrmkit.core.time import as_utc
from pycrmkit.exceptions import ConflictError, ValidationError
from pycrmkit.relationships.value_objects import RelationshipEndpoint

_WHITESPACE = re.compile(r"\s+")


def normalize_optional_text(value: str | None) -> str | None:
    """Normalize optional human text without changing meaningful letter case."""
    if value is None:
        return None
    normalized = _WHITESPACE.sub(" ", unicodedata.normalize("NFKC", value).strip())
    return normalized or None


def validate_endpoints(source: RelationshipEndpoint, target: RelationshipEndpoint) -> None:
    """Reject self-links while preserving explicit source → target direction."""
    if source == target:
        raise ConflictError(
            "a relationship cannot link an entity to itself",
            code="relationship.self_link",
            context={"entity_kind": source.kind.value, "entity_id": str(source.id)},
        )


def normalize_validity(
    valid_from: datetime,
    valid_until: datetime | None,
) -> tuple[datetime, datetime | None]:
    """Normalize relationship validity timestamps and enforce a non-empty interval."""
    start = as_utc(valid_from)
    end = as_utc(valid_until) if valid_until is not None else None
    if end is not None and end <= start:
        raise ValidationError(
            "valid_until must be later than valid_from",
            code="relationship.validity.invalid_interval",
        )
    return start, end
