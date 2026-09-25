"""Registry for versioned public PyCRMKit event contracts."""

from __future__ import annotations

from dataclasses import dataclass

from pycrmkit.core.events import EventType
from pycrmkit.core.value_objects import ValueObject
from pycrmkit.events.envelope import DomainEvent
from pycrmkit.exceptions import DuplicateError, NotFoundError, ValidationError


@dataclass(frozen=True, slots=True)
class EventDefinition(ValueObject):
    """One registered public event contract identified by type and schema version."""

    event_type: EventType
    schema_version: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(self, "event_type", EventType.parse(self.event_type))
        if self.schema_version < 1:
            raise ValidationError(
                "event definition schema_version must be at least 1",
                code="event.registry.schema_version.invalid",
            )


class EventRegistry:
    """Mutable registry of supported public event type/version pairs."""

    def __init__(self) -> None:
        self._definitions: dict[tuple[str, int], EventDefinition] = {}

    def register(
        self,
        event_type: EventType | str,
        schema_version: int = 1,
    ) -> EventDefinition:
        """Register exactly one public event schema."""

        definition = EventDefinition(EventType.parse(event_type), schema_version)
        key = (str(definition.event_type), definition.schema_version)
        if key in self._definitions:
            raise DuplicateError(
                "event definition is already registered",
                code="event.registry.definition.duplicate",
                context={
                    "event_type": key[0],
                    "schema_version": key[1],
                },
            )
        self._definitions[key] = definition
        return definition

    def resolve(
        self,
        event_type: EventType | str,
        schema_version: int,
    ) -> EventDefinition:
        """Resolve one exact event contract or raise NotFoundError."""

        parsed = EventType.parse(event_type)
        key = (str(parsed), schema_version)
        definition = self._definitions.get(key)
        if definition is None:
            raise NotFoundError(
                "event definition is not registered",
                code="event.registry.definition.not_found",
                context={
                    "event_type": key[0],
                    "schema_version": key[1],
                },
            )
        return definition

    def latest(self, event_type: EventType | str) -> EventDefinition:
        """Return the highest registered schema version for one event type."""

        parsed = EventType.parse(event_type)
        definitions = [
            definition
            for definition in self._definitions.values()
            if definition.event_type == parsed
        ]
        if not definitions:
            raise NotFoundError(
                "event type is not registered",
                code="event.registry.event_type.not_found",
                context={"event_type": str(parsed)},
            )
        return max(definitions, key=lambda item: item.schema_version)

    def supports(
        self,
        event_type: EventType | str,
        schema_version: int,
    ) -> bool:
        """Return whether one exact type/version pair is registered."""

        parsed = EventType.parse(event_type)
        return (str(parsed), schema_version) in self._definitions

    def validate(self, event: DomainEvent) -> EventDefinition:
        """Require an event occurrence to match a registered contract."""

        return self.resolve(event.type, event.schema_version)

    def definitions(self) -> tuple[EventDefinition, ...]:
        """Return all definitions in deterministic type/version order."""

        return tuple(
            sorted(
                self._definitions.values(),
                key=lambda item: (str(item.event_type), item.schema_version),
            )
        )

    def __len__(self) -> int:
        return len(self._definitions)


BUILTIN_EVENT_TYPES: tuple[str, ...] = (
    "activity.created",
    "activity.updated",
    "contact.archived",
    "contact.created",
    "contact.updated",
    "custom_field.defined",
    "custom_field.revised",
    "custom_field.value_removed",
    "custom_field.value_set",
    "email.bounced",
    "email.clicked",
    "email.delivered",
    "email.failed",
    "email.opened",
    "email.queued",
    "email.sent",
    "lead.converted",
    "lead.created",
    "lead.disqualified",
    "lead.qualified",
    "opportunity.cancelled",
    "opportunity.created",
    "opportunity.lost",
    "opportunity.stage_changed",
    "opportunity.won",
    "organization.archived",
    "organization.created",
    "organization.updated",
    "pipeline.created",
    "relationship.created",
    "relationship.ended",
    "relationship.updated",
    "tag.assigned",
    "tag.created",
    "tag.removed",
    "task.cancelled",
    "task.completed",
    "task.created",
    "task.reopened",
    "task.started",
    "task.updated",
)


def default_event_registry() -> EventRegistry:
    """Build a fresh registry containing all stable event contracts through 0.4."""

    registry = EventRegistry()
    for event_type in BUILTIN_EVENT_TYPES:
        registry.register(event_type, 1)
    return registry


__all__ = [
    "BUILTIN_EVENT_TYPES",
    "EventDefinition",
    "EventRegistry",
    "default_event_registry",
]
