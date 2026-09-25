"""Stable JSON serialization governed by an EventRegistry."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass

from pycrmkit.events.envelope import DomainEvent
from pycrmkit.events.registry import EventRegistry
from pycrmkit.exceptions import ValidationError


@dataclass(frozen=True, slots=True)
class EventSerializer:
    """Serialize only event contracts explicitly supported by a registry."""

    registry: EventRegistry

    def to_dict(self, event: DomainEvent) -> dict[str, object]:
        """Return the stable JSON-compatible envelope after registry validation."""

        self.registry.validate(event)
        return event.to_dict()

    def from_dict(self, data: Mapping[str, object]) -> DomainEvent:
        """Restore and validate one registered event envelope."""

        event = DomainEvent.from_dict(data)
        self.registry.validate(event)
        return event

    def dumps(self, event: DomainEvent) -> str:
        """Serialize to deterministic compact JSON suitable for transport/signing."""

        return json.dumps(
            self.to_dict(event),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )

    def loads(self, data: str | bytes | bytearray) -> DomainEvent:
        """Deserialize deterministic JSON and require a registered contract."""

        try:
            raw = json.loads(data)
        except (json.JSONDecodeError, TypeError, UnicodeDecodeError) as exc:
            raise ValidationError(
                "invalid event JSON",
                code="event.serialization.invalid_json",
            ) from exc
        if not isinstance(raw, Mapping):
            raise ValidationError(
                "event JSON must contain an object envelope",
                code="event.serialization.invalid_envelope",
            )
        return self.from_dict({str(key): value for key, value in raw.items()})


__all__ = ["EventSerializer"]
