"""SQLAlchemy persistence model for external identity mappings."""

from __future__ import annotations

from sqlalchemy import JSON, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from pycrmkit.storage.sqlalchemy.base import Base, TimestampedModelMixin


class ExternalIdentityModel(TimestampedModelMixin, Base):
    __tablename__ = "pycrmkit_external_identities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    system: Mapped[str] = mapped_column(String(128), nullable=False)
    external_id: Mapped[str] = mapped_column(String(512), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    metadata_json: Mapped[dict[str, object]] = mapped_column(
        "metadata",
        JSON,
        default=dict,
    )

    __table_args__ = (
        UniqueConstraint(
            "system",
            "external_id",
            name="uq_pycrmkit_external_identities_system_external_id",
        ),
        Index(
            "ix_pycrmkit_external_identities_entity",
            "entity_type",
            "entity_id",
        ),
    )


__all__ = ["ExternalIdentityModel"]
