"""Webhook delivery, retry, idempotency and dead-letter tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from pycrmkit.core.events import EventId
from pycrmkit.core.pagination import OffsetPageRequest
from pycrmkit.core.time import FixedClock
from pycrmkit.events import DomainEvent, EventRegistry, EventSerializer
from pycrmkit.storage.memory import (
    MemoryWebhookDeliveryRepository,
    MemoryWebhookSubscriptionRepository,
)
from pycrmkit.webhooks import (
    WebhookDeliveryEngine,
    WebhookDeliveryState,
    WebhookRequest,
    WebhookResponse,
    WebhookRetryPolicy,
    WebhookSubscriptionService,
    WebhookTransportError,
    verify_webhook_signature,
)

NOW = datetime(2026, 9, 26, 9, 0, tzinfo=UTC)
SECRET = "0123456789abcdef0123456789abcdef"


class SequenceTransport:
    def __init__(self, outcomes: list[WebhookResponse | Exception]) -> None:
        self.outcomes = outcomes
        self.requests: list[WebhookRequest] = []

    def send(self, request: WebhookRequest) -> WebhookResponse:
        self.requests.append(request)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _event() -> DomainEvent:
    return DomainEvent(
        id=EventId(UUID("00000000-0000-0000-0000-000000001001")),
        type="contact.created",  # type: ignore[arg-type]
        schema_version=1,
        aggregate_type="contact",
        aggregate_id="contact-1001",
        occurred_at=NOW,
        actor_id="user-1",
        correlation_id="corr-1",
        payload={"source": "test"},
    )


def _engine(outcomes: list[WebhookResponse | Exception]):
    clock = FixedClock(NOW)
    registry = EventRegistry()
    registry.register("contact.created", 1)
    registry.register("opportunity.won", 1)
    subscriptions = MemoryWebhookSubscriptionRepository()
    deliveries = MemoryWebhookDeliveryRepository()
    contact = WebhookSubscriptionService(
        subscriptions,
        registry=registry,
        clock=clock,
    ).register(
        url="https://hooks.example.com/contact",
        events=("contact.created",),
        signing_secret=SECRET,
    )
    WebhookSubscriptionService(
        subscriptions,
        registry=registry,
        clock=clock,
    ).register(
        url="https://hooks.example.com/sales",
        events=("opportunity.won",),
        signing_secret=SECRET,
    )
    transport = SequenceTransport(outcomes)
    engine = WebhookDeliveryEngine(
        subscription_repository=subscriptions,
        delivery_repository=deliveries,
        serializer=EventSerializer(registry),
        transport=transport,
        retry_policy=WebhookRetryPolicy(max_attempts=2),
        clock=clock,
    )
    return engine, clock, transport, deliveries, contact


def test_delivery_retries_5xx_then_succeeds_with_same_idempotency_key() -> None:
    engine, clock, transport, deliveries, _ = _engine(
        [WebhookResponse(503), WebhookResponse(204)]
    )

    first = engine.dispatch(_event())
    assert len(first) == 1
    assert first[0].state is WebhookDeliveryState.RETRY_SCHEDULED
    assert first[0].next_attempt_at == NOW + timedelta(seconds=10)
    assert len(transport.requests) == 1

    assert engine.retry_due() == ()
    clock.advance(timedelta(seconds=10))
    retried = engine.retry_due()

    assert retried[0].state is WebhookDeliveryState.SUCCEEDED
    assert retried[0].attempt_count == 2
    assert len(transport.requests) == 2
    assert (
        transport.requests[0].headers["X-PyCRMKit-Idempotency-Key"]
        == transport.requests[1].headers["X-PyCRMKit-Idempotency-Key"]
    )

    attempts = deliveries.list_attempts(
        retried[0].id,
        OffsetPageRequest(),
    )
    assert [item.outcome.value for item in attempts.items] == [
        "retry_scheduled",
        "succeeded",
    ]


def test_duplicate_dispatch_after_success_does_not_send_again() -> None:
    engine, _, transport, _, _ = _engine([WebhookResponse(200)])

    original = engine.dispatch(_event())[0]
    replay = engine.dispatch(_event())[0]

    assert replay.id == original.id
    assert replay.state is WebhookDeliveryState.SUCCEEDED
    assert len(transport.requests) == 1


def test_non_retryable_4xx_goes_directly_to_dead_letter() -> None:
    engine, _, transport, _, _ = _engine([WebhookResponse(400)])

    delivery = engine.dispatch(_event())[0]

    assert delivery.state is WebhookDeliveryState.DEAD_LETTER
    assert delivery.attempt_count == 1
    assert delivery.last_error_code == "webhook.http.400"
    assert len(transport.requests) == 1


def test_timeout_retries_then_dead_letters_at_max_attempts() -> None:
    error = WebhookTransportError(
        "timeout",
        code="webhook.transport.timeout",
    )
    engine, clock, _, _, _ = _engine([error, error])

    first = engine.dispatch(_event())[0]
    assert first.state is WebhookDeliveryState.RETRY_SCHEDULED

    clock.advance(timedelta(seconds=10))
    final = engine.retry_due()[0]

    assert final.state is WebhookDeliveryState.DEAD_LETTER
    assert final.attempt_count == 2
    assert final.last_error_code == "webhook.transport.timeout"


def test_signed_request_can_be_verified_by_receiver() -> None:
    engine, _, transport, _, subscription = _engine([WebhookResponse(202)])

    engine.dispatch(_event())
    request = transport.requests[0]

    assert verify_webhook_signature(
        subscription.signing_secret,
        int(request.headers["X-PyCRMKit-Timestamp"]),
        request.body,
        request.headers["X-PyCRMKit-Signature"],
    )
