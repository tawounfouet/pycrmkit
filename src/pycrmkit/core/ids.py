"""Typed UUID identifiers and identifier factories."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Self, TypeVar, runtime_checkable
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True, order=True)
class UUIDId:
    """Immutable UUID-backed identifier suitable for domain-specific subclasses."""

    value: UUID

    def __post_init__(self) -> None:
        if not isinstance(self.value, UUID):
            raise TypeError("UUIDId.value must be a uuid.UUID")

    @classmethod
    def parse(cls, value: UUIDId | UUID | str) -> Self:
        """Parse an identifier from another UUID-backed ID, UUID, or canonical string."""

        if isinstance(value, cls):
            return value
        raw = value.value if isinstance(value, UUIDId) else value
        parsed = raw if isinstance(raw, UUID) else UUID(str(raw))
        return cls(parsed)

    def __str__(self) -> str:
        return str(self.value)


class EntityId(UUIDId):
    """Default identifier type for generic PyCRMKit entities."""


IdT = TypeVar("IdT", bound=UUIDId)


@runtime_checkable
class IDFactory(Protocol):
    """Factory contract used by services to create typed identifiers."""

    def new(self, id_type: type[IdT]) -> IdT:
        """Create a new identifier of ``id_type``."""


class UUID4Factory:
    """Default identifier factory backed by RFC 4122 UUID version 4 values."""

    def new(self, id_type: type[IdT]) -> IdT:
        return id_type(uuid4())
