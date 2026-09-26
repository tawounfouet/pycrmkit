"""Transactional webhook registration facade."""

from __future__ import annotations

from collections.abc import Sequence

from pycrmkit.audit import AuditService
from pycrmkit.core.events import EventType
from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.events import EventRegistry
from pycrmkit.facade._runtime import CRMRuntime
from pycrmkit.webhooks import (
    WebhookSubscription,
    WebhookSubscriptionId,
    WebhookSubscriptionQuery,
    WebhookSubscriptionService,
)


class WebhooksAPI:
    """Register, disable and inspect webhook subscriptions."""

    def __init__(self, runtime: CRMRuntime, *, registry: EventRegistry) -> None:
        self._runtime = runtime
        self._registry = registry

    def register(
        self,
        *,
        url: str,
        events: Sequence[EventType | str],
    ) -> WebhookSubscription:
        with self._runtime.uow_factory() as uow:
            subscription = WebhookSubscriptionService(
                uow.webhooks,
                registry=self._registry,
                id_factory=self._runtime.id_factory,
                clock=self._runtime.clock,
            ).register(url=url, events=events)
            AuditService(
                uow.audit,
                id_factory=self._runtime.id_factory,
                clock=self._runtime.clock,
            ).record(
                action="webhook.subscription.registered",
                entity_type="webhook_subscription",
                entity_id=subscription.id,
                actor_id=self._runtime.context.actor_id,
                correlation_id=self._runtime.context.correlation_id,
                changes={"fields": ["url", "event_types"]},
            )
            uow.commit()
            return subscription

    def disable(
        self,
        subscription_id: WebhookSubscriptionId,
    ) -> WebhookSubscription:
        with self._runtime.uow_factory() as uow:
            subscription = WebhookSubscriptionService(
                uow.webhooks,
                registry=self._registry,
                id_factory=self._runtime.id_factory,
                clock=self._runtime.clock,
            ).disable(subscription_id)
            AuditService(
                uow.audit,
                id_factory=self._runtime.id_factory,
                clock=self._runtime.clock,
            ).record(
                action="webhook.subscription.disabled",
                entity_type="webhook_subscription",
                entity_id=subscription.id,
                actor_id=self._runtime.context.actor_id,
                correlation_id=self._runtime.context.correlation_id,
                changes={"fields": ["disabled_at"]},
            )
            uow.commit()
            return subscription

    def list(
        self,
        *,
        enabled: bool | None = None,
        event_type: EventType | str | None = None,
        page: OffsetPageRequest | None = None,
    ) -> Page[WebhookSubscription]:
        parsed_event = (
            EventType.parse(event_type)
            if event_type is not None
            else None
        )
        with self._runtime.uow_factory() as uow:
            return WebhookSubscriptionService(
                uow.webhooks,
                registry=self._registry,
            ).list(
                WebhookSubscriptionQuery(
                    enabled=enabled,
                    event_type=parsed_event,
                ),
                page,
            )
