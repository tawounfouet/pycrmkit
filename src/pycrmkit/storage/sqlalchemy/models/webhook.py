"""SQLAlchemy persistence models for webhook subscriptions and deliveries."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from pycrmkit.storage.sqlalchemy.base import Base, TimestampedModelMixin


class WebhookSubscriptionModel(TimestampedModelMixin, Base):
    __tablename__ = "pycrmkit_webhook_subscriptions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    signing_secret: Mapped[str] = mapped_column(String(255), nullable=False)
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class WebhookSubscriptionEventModel(Base):
    __tablename__ = "pycrmkit_webhook_subscription_events"

    subscription_id: Mapped[str] = mapped_column(
        ForeignKey("pycrmkit_webhook_subscriptions.id", ondelete="CASCADE"), primary_key=True
    )
    event_type: Mapped[str] = mapped_column(String(255), primary_key=True, index=True)


class WebhookDeliveryModel(TimestampedModelMixin, Base):
    __tablename__ = "pycrmkit_webhook_deliveries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    subscription_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    event_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    state: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    attempt_count: Mapped[int] = mapped_column(nullable=False, default=0)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_status_code: Mapped[int | None]
    last_error_code: Mapped[str | None] = mapped_column(String(255))

    __table_args__ = (
        Index("ix_pycrmkit_webhook_delivery_subscription_event", "subscription_id", "event_id", unique=True),
    )


class WebhookDeliveryAttemptModel(Base):
    __tablename__ = "pycrmkit_webhook_delivery_attempts"

    delivery_id: Mapped[str] = mapped_column(
        ForeignKey("pycrmkit_webhook_deliveries.id", ondelete="CASCADE"), primary_key=True
    )
    attempt_number: Mapped[int] = mapped_column(primary_key=True)
    attempted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    status_code: Mapped[int | None]
    error_code: Mapped[str | None] = mapped_column(String(255))
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
