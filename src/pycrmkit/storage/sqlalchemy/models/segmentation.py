"""SQLAlchemy persistence models for Segments and Saved Queries."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from pycrmkit.storage.sqlalchemy.base import Base, TimestampedModelMixin


class SegmentModel(TimestampedModelMixin, Base):
    """Current persisted state of one Segment definition."""

    __tablename__ = "pycrmkit_segments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    key: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    entity_kind: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    mode: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(String(2000))
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    query_json: Mapped[dict[str, object] | None] = mapped_column("query", JSON)
    saved_query_id: Mapped[str | None] = mapped_column(String(36), index=True)
    saved_query_revision: Mapped[int | None] = mapped_column()
    owner_id: Mapped[str | None] = mapped_column(String(36), index=True)
    revision: Mapped[int] = mapped_column(nullable=False)
    metadata_json: Mapped[dict[str, object]] = mapped_column(
        "metadata",
        JSON,
        default=dict,
    )
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        index=True,
    )


class SegmentMemberModel(Base):
    """Stored Static/Snapshot membership row."""

    __tablename__ = "pycrmkit_segment_members"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    segment_id: Mapped[str] = mapped_column(
        ForeignKey("pycrmkit_segments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    entity_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[str] = mapped_column(String(120), nullable=False)
    actor_id: Mapped[str | None] = mapped_column(String(255))
    metadata_json: Mapped[dict[str, object]] = mapped_column(
        "metadata",
        JSON,
        default=dict,
    )

    __table_args__ = (
        Index(
            "ix_pycrmkit_segment_members_entity",
            "entity_kind",
            "entity_id",
        ),
        UniqueConstraint(
            "segment_id",
            "entity_kind",
            "entity_id",
            name="uq_pycrmkit_segment_members_target",
        ),
    )


class SavedQueryModel(TimestampedModelMixin, Base):
    """One immutable revision of a SavedQuery definition."""

    __tablename__ = "pycrmkit_saved_queries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    revision: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    entity_kind: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    expression_json: Mapped[dict[str, object]] = mapped_column(
        "expression",
        JSON,
        nullable=False,
    )
    ordering_json: Mapped[list[dict[str, str]]] = mapped_column(
        "ordering",
        JSON,
        default=list,
    )
    owner_id: Mapped[str | None] = mapped_column(String(36), index=True)
    visibility: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    metadata_json: Mapped[dict[str, object]] = mapped_column(
        "metadata",
        JSON,
        default=dict,
    )
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        index=True,
    )

    __table_args__ = (
        UniqueConstraint(
            "key",
            "revision",
            name="uq_pycrmkit_saved_queries_key_revision",
        ),
        Index(
            "ix_pycrmkit_saved_queries_id_revision",
            "id",
            "revision",
        ),
    )


__all__ = [
    "SavedQueryModel",
    "SegmentMemberModel",
    "SegmentModel",
]
