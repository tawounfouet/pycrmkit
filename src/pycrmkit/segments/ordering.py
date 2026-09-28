"""Portable ordering primitives for Segment and SavedQuery execution."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from pycrmkit.core.value_objects import ValueObject
from pycrmkit.segments.expressions import normalize_query_field_key


class SortDirection(StrEnum):
    """Portable sort direction."""

    ASC = "asc"
    DESC = "desc"


class NullOrder(StrEnum):
    """Explicit null placement for portable ordering."""

    FIRST = "first"
    LAST = "last"


@dataclass(frozen=True, slots=True)
class SortExpression(ValueObject):
    """One deterministic field ordering rule."""

    field: str
    direction: SortDirection = SortDirection.ASC
    null_order: NullOrder = NullOrder.LAST

    def __post_init__(self) -> None:
        object.__setattr__(self, "field", normalize_query_field_key(self.field))
        object.__setattr__(self, "direction", SortDirection(self.direction))
        object.__setattr__(self, "null_order", NullOrder(self.null_order))


__all__ = ["NullOrder", "SortDirection", "SortExpression"]
