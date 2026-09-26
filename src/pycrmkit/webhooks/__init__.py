"""Webhook registration domain."""

from pycrmkit.webhooks.entities import (
    WebhookSubscription,
    WebhookSubscriptionId,
    normalize_webhook_url,
)
from pycrmkit.webhooks.repository import WebhookSubscriptionRepository
from pycrmkit.webhooks.subscriptions import (
    WebhookSubscriptionQuery,
    WebhookSubscriptionService,
)

__all__ = [
    "WebhookSubscription",
    "WebhookSubscriptionId",
    "WebhookSubscriptionQuery",
    "WebhookSubscriptionRepository",
    "WebhookSubscriptionService",
    "normalize_webhook_url",
]
