"""Webhook registration service and filtering tests."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from pycrmkit.core.events import EventId
from pycrmkit.core.time import FixedClock
from pycrmkit.events import DomainEvent, EventRegistry
from pycrmkit.exceptions import NotFoundError
from pycrmkit.storage.memory import MemoryWebhookSubscriptionRepository
from pycrmkit.webhooks import WebhookSubscriptionService

NOW = datetime(2026, 9, 26, 8, 0, tzinfo=UTC)


def _registry() -> EventRegistry:
    registry = EventRegistry()
    registry.register("contact.created", 1)
    registry.register("opportunity.won", 1)
    return registry


def _event(event_type: str) -> DomainEvent:
    return DomainEvent(
        id=EventId(UUID(int=700)),
        type=event_type,  # type: ignore[arg-type]
        schema_version=1,
        aggregate_type="contact",
        aggregate_id="contact-700",
        occurred_at=NOW,
    )


def test_service_requires_registered_public_event_types() -> None:
    service = WebhookSubscriptionService(
        MemoryWebhookSubscriptionRepository(),
        registry=_registry(),
        clock=FixedClock(NOW),
    )

    with pytest.raises(NotFoundError):
        service.register(
            url="https://hooks.example.com/custom",
            events=("custom.created",),
        )


def test_matching_returns_only_enabled_subscriptions_for_event() -> None:
    repository = MemoryWebhookSubscriptionRepository()
    service = WebhookSubscriptionService(
        repository,
        registry=_registry(),
        clock=FixedClock(NOW),
    )
    contact = service.register(
        url="https://hooks.example.com/contact",
        events=("contact.created",),
    )
    sales = service.register(
        url="https://hooks.example.com/sales",
        events=("opportunity.won",),
    )
    disabled = service.register(
        url="https://hooks.example.com/disabled",
        events=("contact.created",),
    )
    service.disable(disabled.id)

    matches = service.matching(_event("contact.created"))

    assert matches.items == (contact,)
    assert sales not in matches.items
    assert disabled not in matches.items
