"""Explicit facade E2E for signed retryable webhook delivery."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from pycrmkit import CRM
from pycrmkit.core.events import EventId
from pycrmkit.core.time import FixedClock
from pycrmkit.events import DomainEvent
from pycrmkit.webhooks import (
    WebhookDeliveryState,
    WebhookRequest,
    WebhookResponse,
    WebhookRetryPolicy,
    verify_webhook_signature,
)

NOW = datetime(2026, 9, 26, 10, 0, tzinfo=UTC)
SECRET = "0123456789abcdef0123456789abcdef"


class SequenceTransport:
    def __init__(self) -> None:
        self.requests: list[WebhookRequest] = []
        self.responses = [WebhookResponse(503), WebhookResponse(204)]

    def send(self, request: WebhookRequest) -> WebhookResponse:
        self.requests.append(request)
        return self.responses.pop(0)


def _event() -> DomainEvent:
    return DomainEvent(
        id=EventId(UUID("00000000-0000-0000-0000-000000002001")),
        type="contact.created",  # type: ignore[arg-type]
        schema_version=1,
        aggregate_type="contact",
        aggregate_id="contact-2001",
        occurred_at=NOW,
        actor_id="user-2",
        correlation_id="corr-2",
        payload={"source": "webhook-e2e"},
    )


def test_facade_delivery_retry_history_signature_and_idempotency() -> None:
    transport = SequenceTransport()
    clock = FixedClock(NOW)
    crm = CRM.memory(
        clock=clock,
        webhook_transport=transport,
        webhook_retry_policy=WebhookRetryPolicy(max_attempts=2),
    )
    subscription = crm.webhooks.register(
        url="https://hooks.example.com/crm",
        events=("contact.created",),
        signing_secret=SECRET,
    )
    crm.webhooks.register(
        url="https://hooks.example.com/sales",
        events=("opportunity.won",),
        signing_secret=SECRET,
    )

    first = crm.webhooks.deliver(_event())
    assert len(first) == 1
    assert first[0].subscription_id == subscription.id
    assert first[0].state is WebhookDeliveryState.RETRY_SCHEDULED
    assert crm.webhooks.attempts(first[0].id).total == 1

    request = transport.requests[0]
    assert verify_webhook_signature(
        SECRET,
        int(request.headers["X-PyCRMKit-Timestamp"]),
        request.body,
        request.headers["X-PyCRMKit-Signature"],
    )

    assert crm.webhooks.retry_due() == ()
    clock.advance(timedelta(seconds=10))
    retried = crm.webhooks.retry_due()

    assert retried[0].state is WebhookDeliveryState.SUCCEEDED
    assert crm.webhooks.attempts(retried[0].id).total == 2
    assert crm.webhooks.deliveries(
        state=WebhookDeliveryState.SUCCEEDED
    ).items == (retried[0],)

    replay = crm.webhooks.deliver(_event())
    assert replay[0].id == retried[0].id
    assert len(transport.requests) == 2
