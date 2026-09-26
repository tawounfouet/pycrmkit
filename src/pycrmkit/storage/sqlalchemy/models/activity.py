"""SQLAlchemy persistence models for activities and participants."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from pycrmkit.storage.sqlalchemy.base import Base, TimestampedModelMixin


class ActivityModel(TimestampedModelMixin, Base):
    __tablename__ = "pycrmkit_activities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    subject: Mapped[str | None] = mapped_column(String(511))
    description: Mapped[str | None] = mapped_column(Text)
    direction: Mapped[str | None] = mapped_column(String(32))
    duration_seconds: Mapped[int | None]
    source: Mapped[str | None] = mapped_column(String(255))
    external_id: Mapped[str | None] = mapped_column(String(255), index=True)
    metadata_json: Mapped[dict[str, object]] = mapped_column("metadata", JSON, default=dict)


class ActivityParticipantModel(Base):
    __tablename__ = "pycrmkit_activity_participants"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    activity_id: Mapped[str] = mapped_column(
        ForeignKey("pycrmkit_activities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(nullable=False, default=0)
    entity_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    role: Mapped[str | None] = mapped_column(String(255))
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        Index("ix_pycrmkit_activity_participants_entity", "entity_kind", "entity_id"),
    )


class ActivityReferenceModel(Base):
    __tablename__ = "pycrmkit_activity_references"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    activity_id: Mapped[str] = mapped_column(
        ForeignKey("pycrmkit_activities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(nullable=False, default=0)
    entity_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)

    __table_args__ = (
        Index("ix_pycrmkit_activity_references_entity", "entity_kind", "entity_id"),
    )
