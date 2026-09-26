"""SQLAlchemy persistence model for append-only audit entries."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from pycrmkit.storage.sqlalchemy.base import Base


class AuditEntryModel(Base):
    __tablename__ = "pycrmkit_audit_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    actor_id: Mapped[str | None] = mapped_column(String(255), index=True)
    action: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(128), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(255), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    changes_json: Mapped[dict[str, object]] = mapped_column("changes", JSON, default=dict)
    correlation_id: Mapped[str | None] = mapped_column(String(255), index=True)

    __table_args__ = (Index("ix_pycrmkit_audit_entity", "entity_type", "entity_id"),)
