"""Core identifiers and naming conventions for CRM domain events."""

from __future__ import annotations

import re
from dataclasses import dataclass

from pycrmkit.core.ids import UUIDId
from pycrmkit.core.value_objects import ValueObject
from pycrmkit.exceptions import ValidationError

_EVENT_TYPE_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}(?:\.[a-z][a-z0-9_]{0,63})+$")


class EventId(UUIDId):
    """Strongly typed identifier for one immutable domain-event occurrence."""


@dataclass(frozen=True, slots=True)
class EventType(ValueObject):
    """Stable dotted public event name such as ``contact.created``."""

    value: str

    def __post_init__(self) -> None:
        normalized = self.value.strip().casefold()
        if not _EVENT_TYPE_PATTERN.fullmatch(normalized):
            raise ValidationError(
                "event type must be a dotted lowercase identifier",
                code="event.type.invalid",
                context={"event_type": self.value},
            )
        object.__setattr__(self, "value", normalized)

    @classmethod
    def parse(cls, value: EventType | str) -> EventType:
        """Normalize a raw string into an EventType."""

        return value if isinstance(value, cls) else cls(value)

    def __str__(self) -> str:
        return self.value
