"""SQLAlchemy persistence models for versioned custom fields."""

from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Index, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from pycrmkit.storage.sqlalchemy.base import Base, TimestampedModelMixin


class CustomFieldDefinitionModel(TimestampedModelMixin, Base):
    __tablename__ = "pycrmkit_custom_field_definitions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(511), nullable=False)
    field_type: Mapped[str] = mapped_column(String(32), nullable=False)
    schema_version: Mapped[int] = mapped_column(nullable=False)
    applies_to_json: Mapped[list[str]] = mapped_column("applies_to", JSON, default=list)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    description: Mapped[str | None] = mapped_column(String(2048))
    options_json: Mapped[list[dict[str, str]]] = mapped_column("options", JSON, default=list)
    reference_kinds_json: Mapped[list[str]] = mapped_column("reference_kinds", JSON, default=list)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    metadata_json: Mapped[dict[str, object]] = mapped_column("metadata", JSON, default=dict)

    __table_args__ = (
        Index("ix_pycrmkit_custom_field_definition_revision", "key", "schema_version", unique=True),
    )


class CustomFieldValueModel(TimestampedModelMixin, Base):
    __tablename__ = "pycrmkit_custom_field_values"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    definition_id: Mapped[str] = mapped_column(
        ForeignKey("pycrmkit_custom_field_definitions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    entity_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    schema_version: Mapped[int] = mapped_column(nullable=False)
    value_json: Mapped[object] = mapped_column("value", JSON, nullable=True)

    __table_args__ = (
        Index("ix_pycrmkit_custom_field_values_entity", "entity_kind", "entity_id"),
    )
