"""Installed/public-surface smoke for the 0.5 Event Registry."""

from datetime import UTC, datetime
from uuid import UUID

from pycrmkit.core.events import EventId
from pycrmkit.events import (
    DomainEvent,
    EventSerializer,
    default_event_registry,
)


def test_builtin_registry_serializes_stable_event_contract() -> None:
    serializer = EventSerializer(default_event_registry())
    event = DomainEvent(
        id=EventId(UUID("00000000-0000-0000-0000-000000000901")),
        type="contact.created",  # type: ignore[arg-type]
        schema_version=1,
        aggregate_type="contact",
        aggregate_id="00000000-0000-0000-0000-000000000902",
        occurred_at=datetime(2026, 9, 25, 20, 0, tzinfo=UTC),
    )

    restored = serializer.loads(serializer.dumps(event))

    assert restored.to_dict() == event.to_dict()
