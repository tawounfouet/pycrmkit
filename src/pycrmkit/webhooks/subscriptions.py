"""Webhook subscription queries and application service."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from pycrmkit.core.events import EventType
from pycrmkit.core.ids import IDFactory, UUID4Factory
from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.core.time import Clock, SystemClock
from pycrmkit.events import DomainEvent, EventRegistry
from pycrmkit.webhooks.entities import WebhookSubscription, WebhookSubscriptionId
from pycrmkit.webhooks.signing import generate_webhook_secret

if TYPE_CHECKING:
    from pycrmkit.webhooks.repository import WebhookSubscriptionRepository


@dataclass(frozen=True, slots=True)
class WebhookSubscriptionQuery:
    """Backend-independent filters for webhook registrations."""

    enabled: bool | None = None
    event_type: EventType | None = None

    def __post_init__(self) -> None:
        if self.event_type is not None:
            object.__setattr__(
                self,
                "event_type",
                EventType.parse(self.event_type),
            )


@dataclass(slots=True)
class WebhookSubscriptionService:
    """Manage webhook registrations without delivering network requests."""

    repository: WebhookSubscriptionRepository
    registry: EventRegistry
    id_factory: IDFactory = field(default_factory=UUID4Factory)
    clock: Clock = field(default_factory=SystemClock)

    def register(
        self,
        *,
        url: str,
        events: Sequence[EventType | str],
        signing_secret: str | None = None,
    ) -> WebhookSubscription:
        """Register one endpoint for one or more registered event types."""

        event_types = tuple(EventType.parse(event) for event in events)
        for event_type in event_types:
            self.registry.latest(event_type)

        now = self.clock.now()
        subscription = WebhookSubscription(
            id=self.id_factory.new(WebhookSubscriptionId),
            created_at=now,
            updated_at=now,
            url=url,
            event_types=event_types,
            signing_secret=(
                signing_secret
                if signing_secret is not None
                else generate_webhook_secret()
            ),
        )
        self.repository.save(subscription)
        return subscription

    def disable(
        self,
        subscription_id: WebhookSubscriptionId,
    ) -> WebhookSubscription:
        """Disable a registration idempotently."""

        subscription = self.repository.get(subscription_id)
        if subscription.disable(self.clock.now()):
            self.repository.save(subscription)
        return subscription

    def list(
        self,
        query: WebhookSubscriptionQuery | None = None,
        page: OffsetPageRequest | None = None,
    ) -> Page[WebhookSubscription]:
        """List registrations using deterministic pagination."""

        return self.repository.search(
            query or WebhookSubscriptionQuery(),
            page or OffsetPageRequest(),
        )

    def matching(
        self,
        event: DomainEvent,
        page: OffsetPageRequest | None = None,
    ) -> Page[WebhookSubscription]:
        """Return active subscriptions matching one event type."""

        self.registry.validate(event)
        return self.repository.search(
            WebhookSubscriptionQuery(enabled=True, event_type=event.type),
            page or OffsetPageRequest(),
        )
