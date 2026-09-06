"""Core primitives shared by PyCRMKit domain modules."""

from pycrmkit.core.entities import Entity, TimestampedEntity
from pycrmkit.core.ids import EntityId, IDFactory, UUID4Factory, UUIDId
from pycrmkit.core.time import Clock, FixedClock, SystemClock, as_utc
from pycrmkit.core.value_objects import ValueObject

__all__ = [
    "Clock",
    "Entity",
    "EntityId",
    "FixedClock",
    "IDFactory",
    "SystemClock",
    "TimestampedEntity",
    "UUID4Factory",
    "UUIDId",
    "ValueObject",
    "as_utc",
]
