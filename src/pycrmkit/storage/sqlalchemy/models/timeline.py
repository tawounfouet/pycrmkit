"""SQLAlchemy persistence models for immutable timeline projections."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from pycrmkit.storage.sqlalchemy.base import Base


class TimelineEntryModel(Base):
    __tablename__ = "pycrmkit_timeline_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source_event_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    entity_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(511), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    actor_id: Mapped[str | None] = mapped_column(String(255), index=True)
    correlation_id: Mapped[str | None] = mapped_column(String(255), index=True)
    metadata_json: Mapped[dict[str, object]] = mapped_column(
        "metadata", JSON, default=dict
    )

    __table_args__ = (
        Index("ix_pycrmkit_timeline_entity", "entity_kind", "entity_id"),
    )


class TimelineReferenceModel(Base):
    __tablename__ = "pycrmkit_timeline_references"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    entry_id: Mapped[str] = mapped_column(
        ForeignKey("pycrmkit_timeline_entries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    position: Mapped[int] = mapped_column(nullable=False, default=0)
    entity_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)

    __table_args__ = (
        Index("ix_pycrmkit_timeline_reference_entity", "entity_kind", "entity_id"),
    )
