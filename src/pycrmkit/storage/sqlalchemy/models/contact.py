"""SQLAlchemy persistence models for contacts and contact points."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from pycrmkit.storage.sqlalchemy.base import Base, TimestampedModelMixin


class ContactModel(TimestampedModelMixin, Base):
    __tablename__ = "pycrmkit_contacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    first_name: Mapped[str | None] = mapped_column(String(255))
    last_name: Mapped[str | None] = mapped_column(String(255))
    display_name: Mapped[str | None] = mapped_column(String(511))
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    owner_id: Mapped[str | None] = mapped_column(String(255), index=True)
    source: Mapped[str | None] = mapped_column(String(255))
    metadata_json: Mapped[dict[str, object]] = mapped_column("metadata", JSON, default=dict)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class ContactEmailModel(Base):
    __tablename__ = "pycrmkit_contact_emails"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    contact_id: Mapped[str] = mapped_column(
        ForeignKey("pycrmkit_contacts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(nullable=False, default=0)
    value: Mapped[str] = mapped_column(String(320), nullable=False)
    normalized: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    verification: Mapped[str] = mapped_column(String(32), nullable=False)

    __table_args__ = (Index("ix_pycrmkit_contact_emails_contact_position", "contact_id", "position"),)


class ContactPhoneModel(Base):
    __tablename__ = "pycrmkit_contact_phones"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    contact_id: Mapped[str] = mapped_column(
        ForeignKey("pycrmkit_contacts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(nullable=False, default=0)
    value: Mapped[str] = mapped_column(String(64), nullable=False)
    normalized: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    verification: Mapped[str] = mapped_column(String(32), nullable=False)


class ContactAddressModel(Base):
    __tablename__ = "pycrmkit_contact_addresses"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    contact_id: Mapped[str] = mapped_column(
        ForeignKey("pycrmkit_contacts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(nullable=False, default=0)
    line1: Mapped[str] = mapped_column(String(511), nullable=False)
    line2: Mapped[str | None] = mapped_column(String(511))
    city: Mapped[str] = mapped_column(String(255), nullable=False)
    postal_code: Mapped[str | None] = mapped_column(String(64))
    region: Mapped[str | None] = mapped_column(String(255))
    country_code: Mapped[str | None] = mapped_column(String(2), index=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
