"""SQLAlchemy persistence model for leads."""

from __future__ import annotations

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from pycrmkit.storage.sqlalchemy.base import Base, TimestampedModelMixin


class LeadModel(TimestampedModelMixin, Base):
    __tablename__ = "pycrmkit_leads"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    contact_id: Mapped[str] = mapped_column(
        ForeignKey("pycrmkit_contacts.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    organization_id: Mapped[str | None] = mapped_column(
        ForeignKey("pycrmkit_organizations.id", ondelete="SET NULL"), index=True
    )
    source: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    converted_opportunity_id: Mapped[str | None] = mapped_column(String(36), index=True)
    conversion_idempotency_key: Mapped[str | None] = mapped_column(String(255), unique=True)
    conversion_request_fingerprint: Mapped[str | None] = mapped_column(String(128))
