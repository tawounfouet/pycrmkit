"""Reusable WebhookDeliveryRepository conformance assertions."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from pycrmkit.core.events import EventId, EventType
from pycrmkit.core.pagination import OffsetPageRequest
from pycrmkit.exceptions import DuplicateError, NotFoundError
from pycrmkit.webhooks import (
    WebhookDelivery,
    WebhookDeliveryAttempt,
    WebhookDeliveryAttemptOutcome,
    WebhookDeliveryId,
    WebhookDeliveryQuery,
    WebhookDeliveryRepository,
    WebhookDeliveryState,
    WebhookSubscriptionId,
)

NOW = datetime(2026, 9, 26, 9, 30, tzinfo=UTC)


def make_delivery(number: int = 1) -> WebhookDelivery:
    return WebhookDelivery(
        id=WebhookDeliveryId(UUID(int=number)),
        created_at=NOW,
        updated_at=NOW,
        subscription_id=WebhookSubscriptionId(UUID(int=100)),
        event_id=EventId(UUID(int=200)),
        event_type=EventType.parse("contact.created"),
        payload_json='{"type":"contact.created"}',
        idempotency_key="whd_contract",
    )


def assert_webhook_delivery_repository_contract(
    repository: WebhookDeliveryRepository,
) -> None:
    delivery = make_delivery()
    repository.save(delivery)

    assert repository.get(delivery.id) == delivery
    assert repository.find(delivery.id) == delivery
    assert repository.find(WebhookDeliveryId(UUID(int=999))) is None
    assert (
        repository.find_by_subscription_event(
            delivery.subscription_id,
            delivery.event_id,
        )
        == delivery
    )

    with pytest.raises(NotFoundError):
        repository.get(WebhookDeliveryId(UUID(int=999)))

    duplicate = make_delivery(2)
    with pytest.raises(DuplicateError):
        repository.save(duplicate)

    delivery.record_retry(
        at=NOW,
        next_attempt_at=NOW + timedelta(seconds=10),
        status_code=503,
        error_code="webhook.http.503",
    )
    repository.save(delivery)
    attempt = WebhookDeliveryAttempt(
        delivery_id=delivery.id,
        attempt_number=1,
        attempted_at=NOW,
        outcome=WebhookDeliveryAttemptOutcome.RETRY_SCHEDULED,
        status_code=503,
        error_code="webhook.http.503",
        next_attempt_at=NOW + timedelta(seconds=10),
    )
    repository.append_attempt(attempt)
    repository.append_attempt(attempt)

    attempts = repository.list_attempts(delivery.id, OffsetPageRequest())
    assert attempts.items == (attempt,)

    due = repository.list_due(
        NOW + timedelta(seconds=10),
        OffsetPageRequest(),
    )
    assert due.items == (delivery,)

    by_state = repository.search(
        WebhookDeliveryQuery(state=WebhookDeliveryState.RETRY_SCHEDULED),
        OffsetPageRequest(),
    )
    assert by_state.items == (delivery,)
