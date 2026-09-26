"""Idempotent webhook delivery engine and append-only attempt log."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from pycrmkit.core.entities import TimestampedEntity
from pycrmkit.core.events import EventId, EventType
from pycrmkit.core.ids import IDFactory, UUID4Factory, UUIDId
from pycrmkit.core.pagination import OffsetPageRequest
from pycrmkit.core.time import Clock, SystemClock, as_utc
from pycrmkit.events import DomainEvent, EventSerializer
from pycrmkit.exceptions import DuplicateError, ValidationError
from pycrmkit.webhooks.entities import WebhookSubscription, WebhookSubscriptionId
from pycrmkit.webhooks.retry import WebhookRetryPolicy
from pycrmkit.webhooks.signing import sign_webhook_payload
from pycrmkit.webhooks.subscriptions import WebhookSubscriptionQuery
from pycrmkit.webhooks.transport import (
    WebhookRequest,
    WebhookTransport,
    WebhookTransportError,
)

if TYPE_CHECKING:
    from pycrmkit.webhooks.repository import (
        WebhookDeliveryRepository,
        WebhookSubscriptionRepository,
    )


class WebhookDeliveryId(UUIDId):
    """Strongly typed identifier for one subscription/event delivery."""


class WebhookDeliveryState(StrEnum):
    PENDING = "pending"
    RETRY_SCHEDULED = "retry_scheduled"
    SUCCEEDED = "succeeded"
    DEAD_LETTER = "dead_letter"


class WebhookDeliveryAttemptOutcome(StrEnum):
    SUCCEEDED = "succeeded"
    RETRY_SCHEDULED = "retry_scheduled"
    DEAD_LETTER = "dead_letter"


@dataclass(eq=False, slots=True)
class WebhookDelivery(TimestampedEntity[WebhookDeliveryId]):
    """Persistent idempotent delivery state for one subscription/event pair."""

    subscription_id: WebhookSubscriptionId
    event_id: EventId
    event_type: EventType
    payload_json: str = field(repr=False)
    idempotency_key: str
    state: WebhookDeliveryState = WebhookDeliveryState.PENDING
    attempt_count: int = 0
    next_attempt_at: datetime | None = None
    last_attempt_at: datetime | None = None
    completed_at: datetime | None = None
    last_status_code: int | None = None
    last_error_code: str | None = None

    def __post_init__(self) -> None:
        TimestampedEntity.__post_init__(self)
        self.event_type = EventType.parse(self.event_type)
        self.state = WebhookDeliveryState(self.state)
        if not self.payload_json:
            raise ValidationError(
                "webhook delivery payload is required",
                code="webhook.delivery.payload.required",
            )
        if not self.idempotency_key:
            raise ValidationError(
                "webhook delivery idempotency key is required",
                code="webhook.delivery.idempotency_key.required",
            )
        if self.attempt_count < 0:
            raise ValidationError(
                "webhook delivery attempt_count cannot be negative",
                code="webhook.delivery.attempt_count.invalid",
            )
        for name in ("next_attempt_at", "last_attempt_at", "completed_at"):
            value = getattr(self, name)
            if value is not None:
                setattr(self, name, as_utc(value))

    @property
    def terminal(self) -> bool:
        return self.state in {
            WebhookDeliveryState.SUCCEEDED,
            WebhookDeliveryState.DEAD_LETTER,
        }

    def can_attempt(self, at: datetime) -> bool:
        when = as_utc(at)
        if self.terminal:
            return False
        return self.next_attempt_at is None or self.next_attempt_at <= when

    def record_success(self, *, at: datetime, status_code: int) -> None:
        self._record_common(at=at, status_code=status_code, error_code=None)
        self.state = WebhookDeliveryState.SUCCEEDED
        self.next_attempt_at = None
        self.completed_at = as_utc(at)

    def record_retry(
        self,
        *,
        at: datetime,
        next_attempt_at: datetime,
        status_code: int | None,
        error_code: str,
    ) -> None:
        self._record_common(
            at=at,
            status_code=status_code,
            error_code=error_code,
        )
        self.state = WebhookDeliveryState.RETRY_SCHEDULED
        self.next_attempt_at = as_utc(next_attempt_at)
        self.completed_at = None

    def record_dead_letter(
        self,
        *,
        at: datetime,
        status_code: int | None,
        error_code: str,
    ) -> None:
        self._record_common(
            at=at,
            status_code=status_code,
            error_code=error_code,
        )
        self.state = WebhookDeliveryState.DEAD_LETTER
        self.next_attempt_at = None
        self.completed_at = as_utc(at)

    def _record_common(
        self,
        *,
        at: datetime,
        status_code: int | None,
        error_code: str | None,
    ) -> None:
        when = as_utc(at)
        self.attempt_count += 1
        self.last_attempt_at = when
        self.updated_at = max(self.updated_at, when)
        self.last_status_code = status_code
        self.last_error_code = error_code


@dataclass(frozen=True, slots=True)
class WebhookDeliveryAttempt:
    """One immutable delivery-processing attempt."""

    delivery_id: WebhookDeliveryId
    attempt_number: int
    attempted_at: datetime
    outcome: WebhookDeliveryAttemptOutcome
    status_code: int | None = None
    error_code: str | None = None
    next_attempt_at: datetime | None = None

    def __post_init__(self) -> None:
        if type(self.attempt_number) is not int or self.attempt_number < 1:
            raise ValidationError(
                "webhook attempt number must be positive",
                code="webhook.delivery.attempt_number.invalid",
            )
        object.__setattr__(self, "attempted_at", as_utc(self.attempted_at))
        object.__setattr__(self, "outcome", WebhookDeliveryAttemptOutcome(self.outcome))
        if self.next_attempt_at is not None:
            object.__setattr__(
                self,
                "next_attempt_at",
                as_utc(self.next_attempt_at),
            )


@dataclass(frozen=True, slots=True)
class WebhookDeliveryQuery:
    subscription_id: WebhookSubscriptionId | None = None
    event_id: EventId | None = None
    state: WebhookDeliveryState | None = None

    def __post_init__(self) -> None:
        if self.state is not None:
            object.__setattr__(self, "state", WebhookDeliveryState(self.state))


def webhook_idempotency_key(
    subscription_id: WebhookSubscriptionId,
    event_id: EventId,
) -> str:
    """Build a stable opaque key for one subscription/event pair."""

    raw = f"{subscription_id}:{event_id}".encode("ascii")
    return "whd_" + hashlib.sha256(raw).hexdigest()


@dataclass(slots=True)
class WebhookDeliveryEngine:
    """Match, sign, deliver, retry and persist webhook delivery state."""

    subscription_repository: WebhookSubscriptionRepository
    delivery_repository: WebhookDeliveryRepository
    serializer: EventSerializer
    transport: WebhookTransport
    retry_policy: WebhookRetryPolicy = field(default_factory=WebhookRetryPolicy)
    id_factory: IDFactory = field(default_factory=UUID4Factory)
    clock: Clock = field(default_factory=SystemClock)
    timeout_seconds: float = 10.0

    def dispatch(self, event: DomainEvent) -> tuple[WebhookDelivery, ...]:
        """Deliver one event to all active matching subscriptions."""

        self.serializer.registry.validate(event)
        subscriptions: list[WebhookSubscription] = []
        offset = 0
        while True:
            page = self.subscription_repository.search(
                self._active_query(event.type),
                OffsetPageRequest(limit=200, offset=offset),
            )
            subscriptions.extend(page.items)
            if not page.has_next:
                break
            offset += len(page.items)

        return tuple(self._deliver(subscription, event) for subscription in subscriptions)

    def retry_due(self) -> tuple[WebhookDelivery, ...]:
        """Retry all deliveries due at the current clock instant."""

        now = self.clock.now()
        retried: list[WebhookDelivery] = []
        while True:
            page = self.delivery_repository.list_due(
                now,
                OffsetPageRequest(limit=200, offset=0),
            )
            if not page.items:
                break
            for delivery in page.items:
                subscription = self.subscription_repository.get(
                    delivery.subscription_id
                )
                retried.append(self._attempt_existing(subscription, delivery))
        return tuple(retried)

    def _deliver(
        self,
        subscription: WebhookSubscription,
        event: DomainEvent,
    ) -> WebhookDelivery:
        payload_json = self.serializer.dumps(event)
        existing = self.delivery_repository.find_by_subscription_event(
            subscription.id,
            event.id,
        )
        if existing is not None:
            if existing.payload_json != payload_json:
                raise DuplicateError(
                    "event id has conflicting webhook payload",
                    code="webhook.delivery.event_conflict",
                )
            if not existing.can_attempt(self.clock.now()):
                return existing
            return self._attempt_existing(subscription, existing)

        now = self.clock.now()
        delivery = WebhookDelivery(
            id=self.id_factory.new(WebhookDeliveryId),
            created_at=now,
            updated_at=now,
            subscription_id=subscription.id,
            event_id=event.id,
            event_type=event.type,
            payload_json=payload_json,
            idempotency_key=webhook_idempotency_key(subscription.id, event.id),
        )
        self.delivery_repository.save(delivery)
        return self._attempt_existing(subscription, delivery)

    def _attempt_existing(
        self,
        subscription: WebhookSubscription,
        delivery: WebhookDelivery,
    ) -> WebhookDelivery:
        now = self.clock.now()
        if delivery.terminal or not delivery.can_attempt(now):
            return delivery

        if not subscription.enabled:
            return self._record_dead_letter_without_transport(
                delivery,
                error_code="webhook.subscription_disabled",
            )

        attempt_number = delivery.attempt_count + 1
        payload = delivery.payload_json.encode("utf-8")
        timestamp = int(now.timestamp())
        signature = sign_webhook_payload(
            subscription.signing_secret,
            timestamp,
            payload,
        )
        request = WebhookRequest(
            url=subscription.url,
            body=payload,
            timeout_seconds=self.timeout_seconds,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "PyCRMKit-Webhooks/0.5",
                "X-PyCRMKit-Delivery-ID": str(delivery.id),
                "X-PyCRMKit-Event-ID": str(delivery.event_id),
                "X-PyCRMKit-Event-Type": str(delivery.event_type),
                "X-PyCRMKit-Idempotency-Key": delivery.idempotency_key,
                "X-PyCRMKit-Timestamp": str(timestamp),
                "X-PyCRMKit-Signature": signature,
            },
        )

        try:
            response = self.transport.send(request)
        except WebhookTransportError as exc:
            return self._record_failure(
                delivery,
                attempt_number=attempt_number,
                status_code=None,
                error_code=exc.code,
                retryable=True,
            )

        if 200 <= response.status_code <= 299:
            delivery.record_success(at=now, status_code=response.status_code)
            attempt = WebhookDeliveryAttempt(
                delivery_id=delivery.id,
                attempt_number=attempt_number,
                attempted_at=now,
                outcome=WebhookDeliveryAttemptOutcome.SUCCEEDED,
                status_code=response.status_code,
            )
            self.delivery_repository.save(delivery)
            self.delivery_repository.append_attempt(attempt)
            return delivery

        return self._record_failure(
            delivery,
            attempt_number=attempt_number,
            status_code=response.status_code,
            error_code=f"webhook.http.{response.status_code}",
            retryable=self.retry_policy.should_retry_status(response.status_code),
        )

    def _record_failure(
        self,
        delivery: WebhookDelivery,
        *,
        attempt_number: int,
        status_code: int | None,
        error_code: str,
        retryable: bool,
    ) -> WebhookDelivery:
        now = self.clock.now()
        if retryable and attempt_number < self.retry_policy.max_attempts:
            next_at = self.retry_policy.next_attempt_at(now, attempt_number)
            delivery.record_retry(
                at=now,
                next_attempt_at=next_at,
                status_code=status_code,
                error_code=error_code,
            )
            outcome = WebhookDeliveryAttemptOutcome.RETRY_SCHEDULED
        else:
            next_at = None
            delivery.record_dead_letter(
                at=now,
                status_code=status_code,
                error_code=error_code,
            )
            outcome = WebhookDeliveryAttemptOutcome.DEAD_LETTER

        attempt = WebhookDeliveryAttempt(
            delivery_id=delivery.id,
            attempt_number=attempt_number,
            attempted_at=now,
            outcome=outcome,
            status_code=status_code,
            error_code=error_code,
            next_attempt_at=next_at,
        )
        self.delivery_repository.save(delivery)
        self.delivery_repository.append_attempt(attempt)
        return delivery

    def _record_dead_letter_without_transport(
        self,
        delivery: WebhookDelivery,
        *,
        error_code: str,
    ) -> WebhookDelivery:
        return self._record_failure(
            delivery,
            attempt_number=delivery.attempt_count + 1,
            status_code=None,
            error_code=error_code,
            retryable=False,
        )

    @staticmethod
    def _active_query(event_type: EventType) -> WebhookSubscriptionQuery:
        return WebhookSubscriptionQuery(enabled=True, event_type=event_type)


__all__ = [
    "WebhookDelivery",
    "WebhookDeliveryAttempt",
    "WebhookDeliveryAttemptOutcome",
    "WebhookDeliveryEngine",
    "WebhookDeliveryId",
    "WebhookDeliveryQuery",
    "WebhookDeliveryState",
    "webhook_idempotency_key",
]
