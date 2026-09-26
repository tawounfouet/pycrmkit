"""Automatic EventBus-to-webhook bridge tests."""

from datetime import UTC, datetime
from uuid import UUID

from pycrmkit.core.events import EventId
from pycrmkit.events import DomainEvent, EventRegistry, InProcessEventBus
from pycrmkit.webhooks.integration import WebhookEventBridge

NOW = datetime(2026, 9, 26, 10, 0, tzinfo=UTC)


def _event() -> DomainEvent:
    return DomainEvent(
        id=EventId(UUID(int=3001)),
        type="contact.created",  # type: ignore[arg-type]
        schema_version=1,
        aggregate_type="contact",
        aggregate_id="contact-3001",
        occurred_at=NOW,
    )


def test_bridge_installs_once_and_routes_registered_events() -> None:
    bus = InProcessEventBus()
    registry = EventRegistry()
    registry.register("contact.created", 1)
    registry.register("contact.created", 2)
    registry.register("opportunity.won", 1)
    delivered: list[DomainEvent] = []
    bridge = WebhookEventBridge(
        event_bus=bus,
        registry=registry,
        deliver=delivered.append,
    )

    bridge.install()
    bridge.install()
    bus.publish(_event())

    assert delivered == [_event()]


def test_bridge_uninstall_preserves_other_event_handlers() -> None:
    bus = InProcessEventBus()
    registry = EventRegistry()
    registry.register("contact.created", 1)
    delivered: list[DomainEvent] = []
    observed: list[DomainEvent] = []
    bus.subscribe("contact.created", observed.append)
    bridge = WebhookEventBridge(
        event_bus=bus,
        registry=registry,
        deliver=delivered.append,
    )
    bridge.install()
    bridge.uninstall()

    event = _event()
    bus.publish(event)

    assert delivered == []
    assert observed == [event]
