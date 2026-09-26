"""Transactional webhook registration and explicit delivery facade."""

from __future__ import annotations

from collections.abc import Sequence

from pycrmkit.audit import AuditService
from pycrmkit.core.events import EventId, EventType
from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.core.unit_of_work import UnitOfWork
from pycrmkit.events import DomainEvent, EventRegistry, EventSerializer
from pycrmkit.facade._runtime import CRMRuntime
from pycrmkit.webhooks import (
    WebhookDelivery,
    WebhookDeliveryAttempt,
    WebhookDeliveryEngine,
    WebhookDeliveryId,
    WebhookDeliveryQuery,
    WebhookDeliveryState,
    WebhookRetryPolicy,
    WebhookSubscription,
    WebhookSubscriptionId,
    WebhookSubscriptionQuery,
    WebhookSubscriptionService,
    WebhookTransport,
)


class WebhooksAPI:
    """Register subscriptions and explicitly execute reliable delivery."""

    def __init__(
        self,
        runtime: CRMRuntime,
        *,
        registry: EventRegistry,
        transport: WebhookTransport,
        retry_policy: WebhookRetryPolicy,
        timeout_seconds: float,
    ) -> None:
        self._runtime = runtime
        self._registry = registry
        self._transport = transport
        self._retry_policy = retry_policy
        self._timeout_seconds = timeout_seconds

    def register(
        self,
        *,
        url: str,
        events: Sequence[EventType | str],
        signing_secret: str | None = None,
    ) -> WebhookSubscription:
        with self._runtime.uow_factory() as uow:
            subscription = WebhookSubscriptionService(
                uow.webhooks,
                registry=self._registry,
                id_factory=self._runtime.id_factory,
                clock=self._runtime.clock,
            ).register(
                url=url,
                events=events,
                signing_secret=signing_secret,
            )
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
            was_enabled = uow.webhooks.get(subscription_id).enabled
            subscription = WebhookSubscriptionService(
                uow.webhooks,
                registry=self._registry,
                id_factory=self._runtime.id_factory,
                clock=self._runtime.clock,
            ).disable(subscription_id)
            if was_enabled:
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
        parsed_event = EventType.parse(event_type) if event_type is not None else None
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

    def deliver(self, event: DomainEvent) -> tuple[WebhookDelivery, ...]:
        """Explicitly deliver one registered event to matching subscriptions."""

        with self._runtime.uow_factory() as uow:
            deliveries = self._engine(uow).dispatch(event)
            uow.commit()
            return deliveries

    def retry_due(self) -> tuple[WebhookDelivery, ...]:
        """Retry all scheduled deliveries due at the runtime clock."""

        with self._runtime.uow_factory() as uow:
            deliveries = self._engine(uow).retry_due()
            uow.commit()
            return deliveries

    def deliveries(
        self,
        *,
        subscription_id: WebhookSubscriptionId | None = None,
        event_id: EventId | None = None,
        state: WebhookDeliveryState | str | None = None,
        page: OffsetPageRequest | None = None,
    ) -> Page[WebhookDelivery]:
        parsed_state = WebhookDeliveryState(state) if state is not None else None
        with self._runtime.uow_factory() as uow:
            return uow.webhook_deliveries.search(
                WebhookDeliveryQuery(
                    subscription_id=subscription_id,
                    event_id=event_id,
                    state=parsed_state,
                ),
                page or OffsetPageRequest(),
            )

    def attempts(
        self,
        delivery_id: WebhookDeliveryId,
        *,
        page: OffsetPageRequest | None = None,
    ) -> Page[WebhookDeliveryAttempt]:
        with self._runtime.uow_factory() as uow:
            return uow.webhook_deliveries.list_attempts(
                delivery_id,
                page or OffsetPageRequest(),
            )

    def _engine(self, uow: UnitOfWork) -> WebhookDeliveryEngine:
        return WebhookDeliveryEngine(
            subscription_repository=uow.webhooks,
            delivery_repository=uow.webhook_deliveries,
            serializer=EventSerializer(self._registry),
            transport=self._transport,
            retry_policy=self._retry_policy,
            id_factory=self._runtime.id_factory,
            clock=self._runtime.clock,
            timeout_seconds=self._timeout_seconds,
        )
