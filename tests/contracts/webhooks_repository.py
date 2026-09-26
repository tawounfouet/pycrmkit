"""Reusable WebhookSubscriptionRepository conformance assertions."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from pycrmkit.core.events import EventType
from pycrmkit.core.pagination import OffsetPageRequest
from pycrmkit.exceptions import NotFoundError
from pycrmkit.webhooks import (
    WebhookSubscription,
    WebhookSubscriptionId,
    WebhookSubscriptionQuery,
    WebhookSubscriptionRepository,
)

NOW = datetime(2026, 9, 26, 8, 0, tzinfo=UTC)


def make_subscription(
    number: int,
    *,
    url: str,
    events: tuple[str, ...],
    disabled: bool = False,
) -> WebhookSubscription:
    subscription = WebhookSubscription(
        id=WebhookSubscriptionId(UUID(int=number)),
        created_at=NOW + timedelta(seconds=number),
        updated_at=NOW + timedelta(seconds=number),
        url=url,
        event_types=tuple(EventType.parse(item) for item in events),
    )
    if disabled:
        subscription.disable(NOW + timedelta(minutes=1))
    return subscription


def assert_webhook_subscription_repository_contract(
    repository: WebhookSubscriptionRepository,
) -> None:
    contact = make_subscription(
        1,
        url="https://hooks.example.com/contact",
        events=("contact.created",),
    )
    sales = make_subscription(
        2,
        url="https://hooks.example.com/sales",
        events=("opportunity.won", "contact.created"),
    )
    disabled = make_subscription(
        3,
        url="https://hooks.example.com/disabled",
        events=("contact.created",),
        disabled=True,
    )
    for subscription in (contact, sales, disabled):
        repository.save(subscription)

    assert repository.get(contact.id) == contact
    assert repository.find(contact.id) == contact
    assert repository.find(WebhookSubscriptionId(UUID(int=999))) is None

    with pytest.raises(NotFoundError):
        repository.get(WebhookSubscriptionId(UUID(int=999)))

    all_page = repository.search(
        WebhookSubscriptionQuery(),
        OffsetPageRequest(),
    )
    assert all_page.total == 3
    assert [item.id for item in all_page.items] == [
        contact.id,
        sales.id,
        disabled.id,
    ]

    active_contact = repository.search(
        WebhookSubscriptionQuery(
            enabled=True,
            event_type=EventType.parse("contact.created"),
        ),
        OffsetPageRequest(),
    )
    assert active_contact.items == (contact, sales)

    disabled_page = repository.search(
        WebhookSubscriptionQuery(enabled=False),
        OffsetPageRequest(),
    )
    assert disabled_page.items == (disabled,)
