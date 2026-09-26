"""SQLAlchemy persistence models for reusable tags and assignments."""

from __future__ import annotations

from sqlalchemy import JSON, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from pycrmkit.storage.sqlalchemy.base import Base, TimestampedModelMixin


class TagModel(TimestampedModelMixin, Base):
    __tablename__ = "pycrmkit_tags"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    metadata_json: Mapped[dict[str, object]] = mapped_column("metadata", JSON, default=dict)


class TagAssignmentModel(TimestampedModelMixin, Base):
    __tablename__ = "pycrmkit_tag_assignments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tag_id: Mapped[str] = mapped_column(
        ForeignKey("pycrmkit_tags.id", ondelete="CASCADE"), nullable=False, index=True
    )
    entity_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)

    __table_args__ = (
        Index("ix_pycrmkit_tag_assignments_entity", "entity_kind", "entity_id"),
        UniqueConstraint(
            "tag_id",
            "entity_kind",
            "entity_id",
            name="uq_pycrmkit_tag_assignments_target",
        ),
    )
