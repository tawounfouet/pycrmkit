"""Release-candidate E2E for automatic EventBus-to-webhook delivery."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from pycrmkit import CRM
from pycrmkit.core.time import FixedClock
from pycrmkit.events import DomainEvent
from pycrmkit.webhooks import (
    WebhookDeliveryState,
    WebhookRequest,
    WebhookResponse,
    WebhookRetryPolicy,
    verify_webhook_signature,
)

NOW = datetime(2026, 9, 26, 10, 30, tzinfo=UTC)
SECRET = "0123456789abcdef0123456789abcdef"


class SequenceTransport:
    def __init__(self, responses: list[WebhookResponse]) -> None:
        self.responses = responses
        self.requests: list[WebhookRequest] = []

    def send(self, request: WebhookRequest) -> WebhookResponse:
        self.requests.append(request)
        return self.responses.pop(0)


def test_contact_created_event_auto_delivers_retries_and_exposes_history() -> None:
    transport = SequenceTransport([WebhookResponse(503), WebhookResponse(204)])
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

    observed: list[DomainEvent] = []
    crm.events.subscribe("contact.created", observed.append)

    contact = crm.with_context(
        actor_id="rc-user",
        correlation_id="rc-correlation",
    ).contacts.create(display_name="Webhook RC")

    assert crm.contacts.get(contact.id) == contact
    assert len(observed) == 1
    event = observed[0]
    assert event.actor_id == "rc-user"
    assert event.correlation_id == "rc-correlation"

    history = crm.webhooks.deliveries(event_id=event.id)
    assert history.total == 1
    first = history.items[0]
    assert first.subscription_id == subscription.id
    assert first.state is WebhookDeliveryState.RETRY_SCHEDULED
    assert first.attempt_count == 1
    assert first.last_status_code == 503
    assert crm.webhooks.attempts(first.id).total == 1
    assert len(transport.requests) == 1

    request = transport.requests[0]
    assert request.headers["X-PyCRMKit-Event-ID"] == str(event.id)
    assert request.headers["X-PyCRMKit-Event-Type"] == "contact.created"
    assert verify_webhook_signature(
        SECRET,
        int(request.headers["X-PyCRMKit-Timestamp"]),
        request.body,
        request.headers["X-PyCRMKit-Signature"],
    )

    assert crm.webhooks.retry_due() == ()
    clock.advance(timedelta(seconds=10))
    retried = crm.webhooks.retry_due()

    assert len(retried) == 1
    final = retried[0]
    assert final.id == first.id
    assert final.state is WebhookDeliveryState.SUCCEEDED
    assert final.attempt_count == 2
    attempts = crm.webhooks.attempts(final.id)
    assert [attempt.status_code for attempt in attempts.items] == [503, 204]
    assert len(transport.requests) == 2

    replay = crm.webhooks.deliver(event)
    assert replay[0].id == final.id
    assert len(transport.requests) == 2


def test_auto_delivery_can_be_disabled_without_disabling_explicit_delivery() -> None:
    transport = SequenceTransport([WebhookResponse(204)])
    clock = FixedClock(NOW)
    crm = CRM.memory(
        clock=clock,
        webhook_transport=transport,
        webhook_auto_delivery=False,
    )
    crm.webhooks.register(
        url="https://hooks.example.com/manual",
        events=("contact.created",),
        signing_secret=SECRET,
    )
    observed: list[DomainEvent] = []
    crm.events.subscribe("contact.created", observed.append)

    crm.contacts.create(display_name="Manual webhook")

    assert len(observed) == 1
    assert crm.webhooks.deliveries().total == 0
    assert transport.requests == []

    delivered = crm.webhooks.deliver(observed[0])

    assert delivered[0].state is WebhookDeliveryState.SUCCEEDED
    assert len(transport.requests) == 1
