"""In-memory webhook delivery state and append-only attempt log."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime

from pycrmkit.core.events import EventId
from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.exceptions import DuplicateError, NotFoundError
from pycrmkit.storage.memory._state import _MemoryState
from pycrmkit.webhooks.delivery import (
    WebhookDelivery,
    WebhookDeliveryAttempt,
    WebhookDeliveryId,
    WebhookDeliveryQuery,
    WebhookDeliveryState,
)
from pycrmkit.webhooks.entities import WebhookSubscriptionId


class MemoryWebhookDeliveryRepository:
    """Copy-isolated Memory delivery repository."""

    def __init__(self, state: _MemoryState | None = None) -> None:
        self._state = state or _MemoryState()

    def get(self, delivery_id: WebhookDeliveryId) -> WebhookDelivery:
        delivery = self.find(delivery_id)
        if delivery is None:
            raise NotFoundError(
                "webhook delivery not found",
                code="webhook.delivery.not_found",
                context={"delivery_id": str(delivery_id)},
            )
        return delivery

    def find(self, delivery_id: WebhookDeliveryId) -> WebhookDelivery | None:
        delivery = self._state.webhook_deliveries.get(delivery_id)
        return deepcopy(delivery) if delivery is not None else None

    def find_by_subscription_event(
        self,
        subscription_id: WebhookSubscriptionId,
        event_id: EventId,
    ) -> WebhookDelivery | None:
        for delivery in self._state.webhook_deliveries.values():
            if (
                delivery.subscription_id == subscription_id
                and delivery.event_id == event_id
            ):
                return deepcopy(delivery)
        return None

    def save(self, delivery: WebhookDelivery) -> None:
        existing = self.find_by_subscription_event(
            delivery.subscription_id,
            delivery.event_id,
        )
        if existing is not None and existing.id != delivery.id:
            raise DuplicateError(
                "webhook delivery already exists for subscription/event",
                code="webhook.delivery.duplicate",
                context={
                    "subscription_id": str(delivery.subscription_id),
                    "event_id": str(delivery.event_id),
                },
            )
        self._state.webhook_deliveries[delivery.id] = deepcopy(delivery)

    def search(
        self,
        query: WebhookDeliveryQuery,
        page: OffsetPageRequest,
    ) -> Page[WebhookDelivery]:
        values = list(self._state.webhook_deliveries.values())
        if query.subscription_id is not None:
            values = [
                item
                for item in values
                if item.subscription_id == query.subscription_id
            ]
        if query.event_id is not None:
            values = [item for item in values if item.event_id == query.event_id]
        if query.state is not None:
            values = [item for item in values if item.state is query.state]
        values.sort(key=lambda item: (item.created_at, str(item.id)))
        total = len(values)
        selected = values[page.offset : page.offset + page.limit]
        return Page(
            items=tuple(deepcopy(selected)),
            limit=page.limit,
            offset=page.offset,
            total=total,
        )

    def list_due(
        self,
        at: datetime,
        page: OffsetPageRequest,
    ) -> Page[WebhookDelivery]:
        values = [
            item
            for item in self._state.webhook_deliveries.values()
            if item.state is WebhookDeliveryState.RETRY_SCHEDULED
            and item.next_attempt_at is not None
            and item.next_attempt_at <= at
        ]
        values.sort(key=lambda item: (item.next_attempt_at, str(item.id)))
        total = len(values)
        selected = values[page.offset : page.offset + page.limit]
        return Page(
            items=tuple(deepcopy(selected)),
            limit=page.limit,
            offset=page.offset,
            total=total,
        )

    def append_attempt(self, attempt: WebhookDeliveryAttempt) -> None:
        key = (attempt.delivery_id, attempt.attempt_number)
        existing = self._state.webhook_delivery_attempts.get(key)
        if existing is not None:
            if existing != attempt:
                raise DuplicateError(
                    "webhook delivery attempt number conflicts",
                    code="webhook.delivery.attempt.duplicate",
                )
            return
        self._state.webhook_delivery_attempts[key] = deepcopy(attempt)

    def list_attempts(
        self,
        delivery_id: WebhookDeliveryId,
        page: OffsetPageRequest,
    ) -> Page[WebhookDeliveryAttempt]:
        self.get(delivery_id)
        values = [
            item
            for (stored_id, _), item in self._state.webhook_delivery_attempts.items()
            if stored_id == delivery_id
        ]
        values.sort(key=lambda item: item.attempt_number)
        total = len(values)
        selected = values[page.offset : page.offset + page.limit]
        return Page(
            items=tuple(deepcopy(selected)),
            limit=page.limit,
            offset=page.offset,
            total=total,
        )
