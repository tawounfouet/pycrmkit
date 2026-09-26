"""Persistence contract for webhook subscriptions."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pycrmkit.core.pagination import OffsetPageRequest, Page
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
