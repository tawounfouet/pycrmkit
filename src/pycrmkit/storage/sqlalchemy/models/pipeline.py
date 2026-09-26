"""SQLAlchemy persistence models for pipelines, stages and transitions."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from pycrmkit.storage.sqlalchemy.base import Base


class PipelineModel(Base):
    __tablename__ = "pycrmkit_pipelines"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    name: Mapped[str] = mapped_column(String(511), nullable=False)


class PipelineStageModel(Base):
    __tablename__ = "pycrmkit_pipeline_stages"

    pipeline_id: Mapped[str] = mapped_column(
        ForeignKey("pycrmkit_pipelines.id", ondelete="CASCADE"), primary_key=True
    )
    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    name: Mapped[str] = mapped_column(String(511), nullable=False)
    position: Mapped[int] = mapped_column(nullable=False)
    default_probability: Mapped[Decimal | None] = mapped_column(Numeric(7, 6))
    terminal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    outcome: Mapped[str | None] = mapped_column(String(32))


class PipelineTransitionModel(Base):
    __tablename__ = "pycrmkit_pipeline_transitions"

    pipeline_id: Mapped[str] = mapped_column(
        ForeignKey("pycrmkit_pipelines.id", ondelete="CASCADE"), primary_key=True
    )
    from_stage: Mapped[str] = mapped_column(String(255), primary_key=True)
    to_stage: Mapped[str] = mapped_column(String(255), primary_key=True)
