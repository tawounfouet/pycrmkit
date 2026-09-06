"""Entity conventions for the PyCRMKit domain model."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Generic, TypeVar

from pycrmkit.core.ids import UUIDId
from pycrmkit.core.time import as_utc

EntityIdT = TypeVar("EntityIdT", bound=UUIDId)


@dataclass(eq=False, slots=True)
class Entity(Generic[EntityIdT]):
    """Base entity whose equality and hash are defined by type and domain identity."""

    id: EntityIdT

    def __eq__(self, other: object) -> bool:
        if self is other:
            return True
        if not isinstance(other, Entity):
            return NotImplemented
        return type(self) is type(other) and self.id == other.id

    def __hash__(self) -> int:
        return hash((type(self), self.id))


@dataclass(eq=False, slots=True)
class TimestampedEntity(Entity[EntityIdT]):
    """Entity convention with creation/update timestamps normalized to UTC."""

    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        self.created_at = as_utc(self.created_at)
        self.updated_at = as_utc(self.updated_at)
        if self.updated_at < self.created_at:
            raise ValueError("updated_at cannot be earlier than created_at")
