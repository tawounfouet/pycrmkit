"""Synchronous in-process event-bus behavior."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from pycrmkit.core.events import EventId, EventType
from pycrmkit.events import DomainEvent, EventPublisher, InProcessEventBus


def _event(event_type: str = "contact.created") -> DomainEvent:
    return DomainEvent(
        id=EventId(UUID(int=42)),
        type=EventType(event_type),
        schema_version=1,
        aggregate_type="contact",
        aggregate_id="contact-1",
        occurred_at=datetime(2026, 9, 6, 18, 0, tzinfo=UTC),
    )


def test_bus_is_an_event_publisher_and_preserves_subscription_order() -> None:
    bus = InProcessEventBus()
    assert isinstance(bus, EventPublisher)
    calls: list[str] = []

    def first(event: DomainEvent) -> None:
        calls.append(f"first:{event.type}")

    def second(event: DomainEvent) -> None:
        calls.append(f"second:{event.type}")

    bus.subscribe("contact.created", first)
    bus.subscribe("contact.created", second)
    bus.publish(_event())
    assert calls == ["first:contact.created", "second:contact.created"]


def test_duplicate_subscription_is_idempotent_and_unsubscribe_is_explicit() -> None:
    bus = InProcessEventBus()
    calls: list[int] = []

    def handler(event: DomainEvent) -> None:
        del event
        calls.append(1)

    bus.subscribe("contact.created", handler)
    bus.subscribe("contact.created", handler)
    bus.publish(_event())
    assert calls == [1]
    assert bus.unsubscribe("contact.created", handler) is True
    assert bus.unsubscribe("contact.created", handler) is False


def test_on_decorator_registers_exact_event_type_only() -> None:
    bus = InProcessEventBus()
    calls: list[str] = []

    @bus.on("contact.created")
    def handler(event: DomainEvent) -> None:
        calls.append(str(event.type))

    bus.publish(_event("contact.created"))
    bus.publish(_event("contact.updated"))
    assert calls == ["contact.created"]
    assert handler is not None


def test_handler_failure_propagates_synchronously() -> None:
    bus = InProcessEventBus()

    def fail(event: DomainEvent) -> None:
        del event
        raise RuntimeError("handler failed")

    bus.subscribe("contact.created", fail)
    with pytest.raises(RuntimeError, match="handler failed"):
        bus.publish(_event())
