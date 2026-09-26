"""In-memory webhook subscription repository."""

from __future__ import annotations

from copy import deepcopy

from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.exceptions import NotFoundError
from pycrmkit.storage.memory._state import _MemoryState
from pycrmkit.webhooks import (
    WebhookSubscription,
    WebhookSubscriptionId,
    WebhookSubscriptionQuery,
)


class MemoryWebhookSubscriptionRepository:
    """Copy-isolated Memory implementation for webhook registrations."""

    def __init__(self, state: _MemoryState | None = None) -> None:
        self._state = state or _MemoryState()

    def get(self, subscription_id: WebhookSubscriptionId) -> WebhookSubscription:
        subscription = self.find(subscription_id)
        if subscription is None:
            raise NotFoundError(
                "webhook subscription not found",
                code="webhook.subscription.not_found",
                context={"subscription_id": str(subscription_id)},
            )
        return subscription

    def find(
        self,
        subscription_id: WebhookSubscriptionId,
    ) -> WebhookSubscription | None:
        subscription = self._state.webhook_subscriptions.get(subscription_id)
        return deepcopy(subscription) if subscription is not None else None

    def save(self, subscription: WebhookSubscription) -> None:
        self._state.webhook_subscriptions[subscription.id] = deepcopy(subscription)

    def search(
        self,
        query: WebhookSubscriptionQuery,
        page: OffsetPageRequest,
    ) -> Page[WebhookSubscription]:
        values = list(self._state.webhook_subscriptions.values())
        if query.enabled is not None:
            values = [item for item in values if item.enabled is query.enabled]
        if query.event_type is not None:
            values = [
                item
                for item in values
                if query.event_type in item.event_types
            ]
        values.sort(key=lambda item: (item.created_at, str(item.id)))
        total = len(values)
        selected = values[page.offset : page.offset + page.limit]
        return Page(
            items=tuple(deepcopy(selected)),
            limit=page.limit,
            offset=page.offset,
            total=total,
        )
