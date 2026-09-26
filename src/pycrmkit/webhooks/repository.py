"""Persistence contracts for webhook subscriptions and deliveries."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from pycrmkit.core.events import EventId
from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.webhooks.delivery import (
    WebhookDelivery,
    WebhookDeliveryAttempt,
    WebhookDeliveryId,
    WebhookDeliveryQuery,
)
from pycrmkit.webhooks.entities import WebhookSubscription, WebhookSubscriptionId
from pycrmkit.webhooks.subscriptions import WebhookSubscriptionQuery


@runtime_checkable
class WebhookSubscriptionRepository(Protocol):
    """Backend-neutral webhook subscription persistence boundary."""

    def get(self, subscription_id: WebhookSubscriptionId) -> WebhookSubscription:
        """Return one subscription or raise NotFoundError."""

    def find(
        self,
        subscription_id: WebhookSubscriptionId,
    ) -> WebhookSubscription | None:
        """Return one subscription or None."""

    def save(self, subscription: WebhookSubscription) -> None:
        """Persist subscription state."""

    def search(
        self,
        query: WebhookSubscriptionQuery,
        page: OffsetPageRequest,
    ) -> Page[WebhookSubscription]:
        """Return subscriptions with deterministic ordering."""


@runtime_checkable
class WebhookDeliveryRepository(Protocol):
    """Backend-neutral persistence for idempotent delivery state and attempts."""

    def get(self, delivery_id: WebhookDeliveryId) -> WebhookDelivery:
        ...

    def find(self, delivery_id: WebhookDeliveryId) -> WebhookDelivery | None:
        ...

    def find_by_subscription_event(
        self,
        subscription_id: WebhookSubscriptionId,
        event_id: EventId,
    ) -> WebhookDelivery | None:
        ...

    def save(self, delivery: WebhookDelivery) -> None:
        ...

    def search(
        self,
        query: WebhookDeliveryQuery,
        page: OffsetPageRequest,
    ) -> Page[WebhookDelivery]:
        ...

    def list_due(
        self,
        at: datetime,
        page: OffsetPageRequest,
    ) -> Page[WebhookDelivery]:
        ...

    def append_attempt(self, attempt: WebhookDeliveryAttempt) -> None:
        ...

    def list_attempts(
        self,
        delivery_id: WebhookDeliveryId,
        page: OffsetPageRequest,
    ) -> Page[WebhookDeliveryAttempt]:
        ...
