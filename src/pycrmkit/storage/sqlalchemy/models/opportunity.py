"""SQLAlchemy persistence model for opportunities."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from pycrmkit.storage.sqlalchemy.base import Base, TimestampedModelMixin


class OpportunityModel(TimestampedModelMixin, Base):
    __tablename__ = "pycrmkit_opportunities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(511), nullable=False)
    contact_id: Mapped[str] = mapped_column(
        ForeignKey("pycrmkit_contacts.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    organization_id: Mapped[str | None] = mapped_column(
        ForeignKey("pycrmkit_organizations.id", ondelete="SET NULL"), index=True
    )
    pipeline_id: Mapped[str | None] = mapped_column(String(255), index=True)
    stage_id: Mapped[str | None] = mapped_column(String(255), index=True)
    stage_entered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    estimated_value: Mapped[Decimal | None] = mapped_column(Numeric(19, 4))
    currency: Mapped[str | None] = mapped_column(String(3))
    probability: Mapped[Decimal | None] = mapped_column(Numeric(7, 6))
    expected_close_date: Mapped[date | None] = mapped_column(Date)
    owner_id: Mapped[str | None] = mapped_column(String(255), index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
