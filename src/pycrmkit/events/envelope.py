"""Versioned immutable envelope for PyCRMKit domain events."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Self
from uuid import UUID

from pycrmkit.core.events import EventId, EventType
from pycrmkit.core.ids import IDFactory
from pycrmkit.core.json import freeze_json_mapping, thaw_json_mapping
from pycrmkit.core.time import Clock, as_utc
from pycrmkit.exceptions import ValidationError


def _optional_text(value: str | None, *, field_name: str) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        raise ValidationError(
            f"{field_name} cannot be blank",
            code=f"event.{field_name}.invalid",
        )
    return normalized


@dataclass(frozen=True, slots=True)
class DomainEvent:
    """Immutable, schema-versioned CRM domain-event envelope."""

    id: EventId
    type: EventType
    schema_version: int
    aggregate_type: str
    aggregate_id: str
    occurred_at: datetime
    actor_id: str | None = None
    correlation_id: str | None = None
    causation_id: EventId | None = None
    payload: Mapping[str, object] = field(default_factory=dict)
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.schema_version < 1:
            raise ValidationError(
                "event schema_version must be at least 1",
                code="event.schema_version.invalid",
            )
        aggregate_type = self.aggregate_type.strip().casefold()
        if not aggregate_type:
            raise ValidationError(
                "aggregate_type cannot be blank",
                code="event.aggregate_type.invalid",
            )
        aggregate_id = self.aggregate_id.strip()
        if not aggregate_id:
            raise ValidationError(
                "aggregate_id cannot be blank",
                code="event.aggregate_id.invalid",
            )
        object.__setattr__(self, "type", EventType.parse(self.type))
        object.__setattr__(self, "aggregate_type", aggregate_type)
        object.__setattr__(self, "aggregate_id", aggregate_id)
        object.__setattr__(self, "occurred_at", as_utc(self.occurred_at))
        object.__setattr__(self, "actor_id", _optional_text(self.actor_id, field_name="actor_id"))
        object.__setattr__(
            self,
            "correlation_id",
            _optional_text(self.correlation_id, field_name="correlation_id"),
        )
        object.__setattr__(self, "payload", freeze_json_mapping(self.payload))
        object.__setattr__(self, "metadata", freeze_json_mapping(self.metadata))

    @classmethod
    def create(
        cls,
        *,
        id_factory: IDFactory,
        clock: Clock,
        type: EventType | str,
        aggregate_type: str,
        aggregate_id: object,
        schema_version: int = 1,
        actor_id: str | None = None,
        correlation_id: str | None = None,
        causation_id: EventId | None = None,
        payload: Mapping[str, object] | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> DomainEvent:
        """Create a deterministic event using injected ID/time dependencies."""

        return cls(
            id=id_factory.new(EventId),
            type=EventType.parse(type),
            schema_version=schema_version,
            aggregate_type=aggregate_type,
            aggregate_id=str(aggregate_id),
            occurred_at=clock.now(),
            actor_id=actor_id,
            correlation_id=correlation_id,
            causation_id=causation_id,
            payload=payload or {},
            metadata=metadata or {},
        )

    def to_dict(self) -> dict[str, object]:
        """Serialize the stable public envelope to JSON-compatible primitives."""

        return {
            "id": str(self.id),
            "type": str(self.type),
            "schema_version": self.schema_version,
            "aggregate_type": self.aggregate_type,
            "aggregate_id": self.aggregate_id,
            "occurred_at": self.occurred_at.isoformat(),
            "actor_id": self.actor_id,
            "correlation_id": self.correlation_id,
            "causation_id": str(self.causation_id) if self.causation_id is not None else None,
            "payload": thaw_json_mapping(self.payload),
            "metadata": thaw_json_mapping(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> Self:
        """Deserialize one public event envelope produced by :meth:`to_dict`."""

        try:
            raw_causation = data.get("causation_id")
            raw_payload = data.get("payload", {})
            raw_metadata = data.get("metadata", {})
            if not isinstance(raw_payload, Mapping) or not isinstance(raw_metadata, Mapping):
                raise TypeError("payload and metadata must be mappings")
            return cls(
                id=EventId(UUID(str(data["id"]))),
                type=EventType(str(data["type"])),
                schema_version=int(str(data["schema_version"])),
                aggregate_type=str(data["aggregate_type"]),
                aggregate_id=str(data["aggregate_id"]),
                occurred_at=datetime.fromisoformat(str(data["occurred_at"])),
                actor_id=_coerce_optional_string(data.get("actor_id")),
                correlation_id=_coerce_optional_string(data.get("correlation_id")),
                causation_id=(
                    EventId(UUID(str(raw_causation))) if raw_causation is not None else None
                ),
                payload={str(key): value for key, value in raw_payload.items()},
                metadata={str(key): value for key, value in raw_metadata.items()},
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValidationError(
                "invalid domain event envelope",
                code="event.envelope.invalid",
            ) from exc


def _coerce_optional_string(value: object) -> str | None:
    return None if value is None else str(value)
