"""SQLAlchemy persistence models for organizations."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from pycrmkit.storage.sqlalchemy.base import Base, TimestampedModelMixin


class OrganizationModel(TimestampedModelMixin, Base):
    __tablename__ = "pycrmkit_organizations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    legal_name: Mapped[str] = mapped_column(String(511), nullable=False, index=True)
    trading_name: Mapped[str | None] = mapped_column(String(511))
    display_name: Mapped[str | None] = mapped_column(String(511))
    registration_number: Mapped[str | None] = mapped_column(String(255), index=True)
    tax_id: Mapped[str | None] = mapped_column(String(255), index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    owner_id: Mapped[str | None] = mapped_column(String(255), index=True)
    source: Mapped[str | None] = mapped_column(String(255))
    metadata_json: Mapped[dict[str, object]] = mapped_column("metadata", JSON, default=dict)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class OrganizationDomainModel(Base):
    __tablename__ = "pycrmkit_organization_domains"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("pycrmkit_organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(nullable=False, default=0)
    value: Mapped[str] = mapped_column(String(253), nullable=False)
    normalized: Mapped[str] = mapped_column(String(253), nullable=False, index=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class OrganizationAddressModel(Base):
    __tablename__ = "pycrmkit_organization_addresses"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("pycrmkit_organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(nullable=False, default=0)
    line1: Mapped[str] = mapped_column(String(511), nullable=False)
    line2: Mapped[str | None] = mapped_column(String(511))
    city: Mapped[str] = mapped_column(String(255), nullable=False)
    postal_code: Mapped[str | None] = mapped_column(String(64))
    region: Mapped[str | None] = mapped_column(String(255))
    country_code: Mapped[str | None] = mapped_column(String(2), index=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
