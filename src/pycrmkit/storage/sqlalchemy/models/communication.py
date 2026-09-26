"""SQLAlchemy persistence models for communication intent and delivery history."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from pycrmkit.storage.sqlalchemy.base import Base, TimestampedModelMixin


class CommunicationIntentModel(TimestampedModelMixin, Base):
    __tablename__ = "pycrmkit_communication_intents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    channel: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    direction: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    subject: Mapped[str | None] = mapped_column(String(998))
    text_body: Mapped[str | None] = mapped_column(Text)
    html_body: Mapped[str | None] = mapped_column(Text)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), unique=True)
    metadata_json: Mapped[dict[str, object]] = mapped_column("metadata", JSON, default=dict)
    queued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CommunicationRecipientModel(Base):
    __tablename__ = "pycrmkit_communication_recipients"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    intent_id: Mapped[str] = mapped_column(
        ForeignKey("pycrmkit_communication_intents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(nullable=False, default=0)
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    value: Mapped[str] = mapped_column(String(511), nullable=False)
    normalized: Mapped[str] = mapped_column(String(511), nullable=False, index=True)
    display_name: Mapped[str | None] = mapped_column(String(511))
    reference_kind: Mapped[str | None] = mapped_column(String(64))
    reference_id: Mapped[str | None] = mapped_column(String(36))


class CommunicationIntentReferenceModel(Base):
    __tablename__ = "pycrmkit_communication_intent_references"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    intent_id: Mapped[str] = mapped_column(
        ForeignKey("pycrmkit_communication_intents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(nullable=False, default=0)
    entity_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)


class DeliveryAttemptModel(TimestampedModelMixin, Base):
    __tablename__ = "pycrmkit_delivery_attempts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    intent_id: Mapped[str] = mapped_column(
        ForeignKey("pycrmkit_communication_intents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    attempt_number: Mapped[int] = mapped_column(nullable=False)
    attempted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    provider: Mapped[str | None] = mapped_column(String(128), index=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(255), index=True)
    failure_code: Mapped[str | None] = mapped_column(String(255))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[dict[str, object]] = mapped_column("metadata", JSON, default=dict)

    __table_args__ = (
        Index("ix_pycrmkit_delivery_attempt_intent_number", "intent_id", "attempt_number", unique=True),
    )


class CommunicationRecordModel(TimestampedModelMixin, Base):
    __tablename__ = "pycrmkit_communication_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    channel: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    direction: Mapped[str] = mapped_column(String(32), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    subject: Mapped[str | None] = mapped_column(String(998))
    intent_id: Mapped[str | None] = mapped_column(
        ForeignKey("pycrmkit_communication_intents.id", ondelete="SET NULL"), index=True
    )
    delivery_attempt_id: Mapped[str | None] = mapped_column(
        ForeignKey("pycrmkit_delivery_attempts.id", ondelete="SET NULL"), index=True
    )
    external_id: Mapped[str | None] = mapped_column(String(255), index=True)
    delivery_status: Mapped[str | None] = mapped_column(String(32), index=True)
    last_delivery_event_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[dict[str, object]] = mapped_column("metadata", JSON, default=dict)


class CommunicationCounterpartyModel(Base):
    __tablename__ = "pycrmkit_communication_counterparties"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    record_id: Mapped[str] = mapped_column(
        ForeignKey("pycrmkit_communication_records.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(nullable=False, default=0)
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    value: Mapped[str] = mapped_column(String(511), nullable=False)
    normalized: Mapped[str] = mapped_column(String(511), nullable=False, index=True)


class CommunicationRecordReferenceModel(Base):
    __tablename__ = "pycrmkit_communication_record_references"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    record_id: Mapped[str] = mapped_column(
        ForeignKey("pycrmkit_communication_records.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(nullable=False, default=0)
    entity_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)

    __table_args__ = (Index("ix_pycrmkit_communication_record_ref_entity", "entity_kind", "entity_id"),)


class EmailDeliveryEventModel(Base):
    __tablename__ = "pycrmkit_email_delivery_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    intent_id: Mapped[str] = mapped_column(
        ForeignKey("pycrmkit_communication_intents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    delivery_attempt_id: Mapped[str | None] = mapped_column(
        ForeignKey("pycrmkit_delivery_attempts.id", ondelete="SET NULL"), index=True
    )
    provider: Mapped[str | None] = mapped_column(String(128), index=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(255), index=True)
    external_event_id: Mapped[str | None] = mapped_column(String(255), index=True)
    recipient_channel: Mapped[str | None] = mapped_column(String(32))
    recipient_value: Mapped[str | None] = mapped_column(String(511))
    recipient_normalized: Mapped[str | None] = mapped_column(String(511), index=True)
    failure_code: Mapped[str | None] = mapped_column(String(255))
    metadata_json: Mapped[dict[str, object]] = mapped_column("metadata", JSON, default=dict)
