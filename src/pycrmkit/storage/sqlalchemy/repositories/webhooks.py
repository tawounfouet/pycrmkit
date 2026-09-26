"""SQLAlchemy webhook subscription and delivery repositories."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, exists, select
from sqlalchemy.orm import Session

from pycrmkit.core.events import EventId
from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.exceptions import DuplicateError, NotFoundError
from pycrmkit.storage.sqlalchemy.mappers import (
    webhook_attempt_from_model,
    webhook_attempt_to_model,
    webhook_delivery_from_model,
    webhook_delivery_to_model,
    webhook_subscription_from_model,
    webhook_subscription_to_model,
)
from pycrmkit.storage.sqlalchemy.models.webhook import (
    WebhookDeliveryAttemptModel,
    WebhookDeliveryModel,
    WebhookSubscriptionEventModel,
    WebhookSubscriptionModel,
)
from pycrmkit.storage.sqlalchemy.repositories._helpers import page_models
from pycrmkit.webhooks import (
    WebhookDelivery,
    WebhookDeliveryAttempt,
    WebhookDeliveryId,
    WebhookDeliveryQuery,
    WebhookDeliveryState,
    WebhookSubscription,
    WebhookSubscriptionId,
    WebhookSubscriptionQuery,
)


class SQLAlchemyWebhookSubscriptionRepository:
    """SQLAlchemy adapter for webhook endpoint registrations."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(
        self,
        subscription_id: WebhookSubscriptionId,
    ) -> WebhookSubscription:
        subscription = self.find(subscription_id)
        if subscription is None:
            raise NotFoundError(
                "webhook subscription not found",
                code="webhook.subscription.not_found",
                context={
                    "subscription_id": str(subscription_id)
                },
            )
        return subscription

    def find(
        self,
        subscription_id: WebhookSubscriptionId,
    ) -> WebhookSubscription | None:
        model = self.session.get(
            WebhookSubscriptionModel,
            str(subscription_id),
        )
        return None if model is None else self._hydrate(model)

    def save(
        self,
        subscription: WebhookSubscription,
    ) -> None:
        model = self.session.get(
            WebhookSubscriptionModel,
            str(subscription.id),
        )
        target = webhook_subscription_to_model(
            subscription,
            model,
        )
        if model is None:
            self.session.add(target)
        key = str(subscription.id)
        self.session.execute(
            delete(WebhookSubscriptionEventModel).where(
                WebhookSubscriptionEventModel.subscription_id
                == key
            )
        )
        self.session.add_all(
            [
                WebhookSubscriptionEventModel(
                    subscription_id=key,
                    event_type=str(event_type),
                )
                for event_type in subscription.event_types
            ]
        )

    def search(
        self,
        query: WebhookSubscriptionQuery,
        page: OffsetPageRequest,
    ) -> Page[WebhookSubscription]:
        statement = select(WebhookSubscriptionModel)
        if query.enabled is True:
            statement = statement.where(
                WebhookSubscriptionModel.disabled_at.is_(None)
            )
        elif query.enabled is False:
            statement = statement.where(
                WebhookSubscriptionModel.disabled_at.is_not(None)
            )
        if query.event_type is not None:
            statement = statement.where(
                exists(
                    select(
                        WebhookSubscriptionEventModel.event_type
                    ).where(
                        WebhookSubscriptionEventModel.subscription_id
                        == WebhookSubscriptionModel.id,
                        WebhookSubscriptionEventModel.event_type
                        == str(query.event_type),
                    )
                )
            )
        statement = statement.order_by(
            WebhookSubscriptionModel.created_at.asc(),
            WebhookSubscriptionModel.id.asc(),
        )
        return page_models(
            self.session,
            statement,
            page,
            self._hydrate,
        )

    def _hydrate(
        self,
        model: WebhookSubscriptionModel,
    ) -> WebhookSubscription:
        events = list(
            self.session.scalars(
                select(WebhookSubscriptionEventModel)
                .where(
                    WebhookSubscriptionEventModel.subscription_id
                    == model.id
                )
                .order_by(
                    WebhookSubscriptionEventModel.event_type.asc()
                )
            )
        )
        return webhook_subscription_from_model(
            model,
            events,
        )


class SQLAlchemyWebhookDeliveryRepository:
    """SQLAlchemy adapter for idempotent webhook delivery state and attempts."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(
        self,
        delivery_id: WebhookDeliveryId,
    ) -> WebhookDelivery:
        delivery = self.find(delivery_id)
        if delivery is None:
            raise NotFoundError(
                "webhook delivery not found",
                code="webhook.delivery.not_found",
                context={
                    "delivery_id": str(delivery_id)
                },
            )
        return delivery

    def find(
        self,
        delivery_id: WebhookDeliveryId,
    ) -> WebhookDelivery | None:
        model = self.session.get(
            WebhookDeliveryModel,
            str(delivery_id),
        )
        return (
            None
            if model is None
            else webhook_delivery_from_model(model)
        )

    def find_by_subscription_event(
        self,
        subscription_id: WebhookSubscriptionId,
        event_id: EventId,
    ) -> WebhookDelivery | None:
        model = self.session.scalar(
            select(WebhookDeliveryModel).where(
                WebhookDeliveryModel.subscription_id
                == str(subscription_id),
                WebhookDeliveryModel.event_id
                == str(event_id),
            )
        )
        return (
            None
            if model is None
            else webhook_delivery_from_model(model)
        )

    def save(self, delivery: WebhookDelivery) -> None:
        with self.session.no_autoflush:
            existing = self.find_by_subscription_event(
                delivery.subscription_id,
                delivery.event_id,
            )
        if (
            existing is not None
            and existing.id != delivery.id
        ):
            raise DuplicateError(
                "webhook delivery already exists for subscription/event",
                code="webhook.delivery.duplicate",
                context={
                    "subscription_id": str(
                        delivery.subscription_id
                    ),
                    "event_id": str(delivery.event_id),
                },
            )
        model = self.session.get(
            WebhookDeliveryModel,
            str(delivery.id),
        )
        target = webhook_delivery_to_model(
            delivery,
            model,
        )
        if model is None:
            self.session.add(target)

    def search(
        self,
        query: WebhookDeliveryQuery,
        page: OffsetPageRequest,
    ) -> Page[WebhookDelivery]:
        statement = select(WebhookDeliveryModel)
        if query.subscription_id is not None:
            statement = statement.where(
                WebhookDeliveryModel.subscription_id
                == str(query.subscription_id)
            )
        if query.event_id is not None:
            statement = statement.where(
                WebhookDeliveryModel.event_id
                == str(query.event_id)
            )
        if query.state is not None:
            statement = statement.where(
                WebhookDeliveryModel.state
                == query.state.value
            )
        statement = statement.order_by(
            WebhookDeliveryModel.created_at.asc(),
            WebhookDeliveryModel.id.asc(),
        )
        return page_models(
            self.session,
            statement,
            page,
            webhook_delivery_from_model,
        )

    def list_due(
        self,
        at: datetime,
        page: OffsetPageRequest,
    ) -> Page[WebhookDelivery]:
        statement = (
            select(WebhookDeliveryModel)
            .where(
                WebhookDeliveryModel.state
                == WebhookDeliveryState.RETRY_SCHEDULED.value,
                WebhookDeliveryModel.next_attempt_at.is_not(None),
                WebhookDeliveryModel.next_attempt_at <= at,
            )
            .order_by(
                WebhookDeliveryModel.next_attempt_at.asc(),
                WebhookDeliveryModel.id.asc(),
            )
        )
        return page_models(
            self.session,
            statement,
            page,
            webhook_delivery_from_model,
        )

    def append_attempt(
        self,
        attempt: WebhookDeliveryAttempt,
    ) -> None:
        key = (
            str(attempt.delivery_id),
            attempt.attempt_number,
        )
        existing = self.session.get(
            WebhookDeliveryAttemptModel,
            key,
        )
        if existing is not None:
            if (
                webhook_attempt_from_model(existing)
                != attempt
            ):
                raise DuplicateError(
                    "webhook delivery attempt number conflicts",
                    code="webhook.delivery.attempt.duplicate",
                )
            return
        self.session.add(
            webhook_attempt_to_model(attempt)
        )

    def list_attempts(
        self,
        delivery_id: WebhookDeliveryId,
        page: OffsetPageRequest,
    ) -> Page[WebhookDeliveryAttempt]:
        self.get(delivery_id)
        statement = (
            select(WebhookDeliveryAttemptModel)
            .where(
                WebhookDeliveryAttemptModel.delivery_id
                == str(delivery_id)
            )
            .order_by(
                WebhookDeliveryAttemptModel.attempt_number.asc()
            )
        )
        return page_models(
            self.session,
            statement,
            page,
            webhook_attempt_from_model,
        )
