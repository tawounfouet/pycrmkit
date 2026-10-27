"""SQLAlchemy persistence models for Campaigns and Campaign-owned records."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from pycrmkit.storage.sqlalchemy.base import Base, TimestampedModelMixin


class CampaignModel(TimestampedModelMixin, Base):
    """Current persisted state of one Campaign aggregate."""

    __tablename__ = "pycrmkit_campaigns"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    key: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2000))
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
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

    __table_args__ = (
        Index("ix_pycrmkit_campaigns_created_at", "created_at"),
    )


class CampaignMemberModel(Base):
    """Direct Campaign audience membership row."""

    __tablename__ = "pycrmkit_campaign_members"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    campaign_id: Mapped[str] = mapped_column(
        ForeignKey("pycrmkit_campaigns.id", ondelete="CASCADE"),
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
            "ix_pycrmkit_campaign_members_entity",
            "entity_kind",
            "entity_id",
        ),
        UniqueConstraint(
            "campaign_id",
            "entity_kind",
            "entity_id",
            name="uq_pycrmkit_campaign_members_target",
        ),
    )


class CampaignSegmentSourceModel(Base):
    """Attached Segment source and capture provenance for a Campaign."""

    __tablename__ = "pycrmkit_campaign_segment_sources"

    campaign_id: Mapped[str] = mapped_column(
        ForeignKey("pycrmkit_campaigns.id", ondelete="CASCADE"),
        primary_key=True,
    )
    segment_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    segment_revision: Mapped[int] = mapped_column(nullable=False)
    entity_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    attached_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    member_count: Mapped[int] = mapped_column(nullable=False)
    actor_id: Mapped[str | None] = mapped_column(String(255))
    metadata_json: Mapped[dict[str, object]] = mapped_column(
        "metadata",
        JSON,
        default=dict,
    )

    __table_args__ = (
        Index("ix_pycrmkit_campaign_segment_sources_segment_id", "segment_id"),
        Index(
            "ix_pycrmkit_campaign_segment_sources_campaign_attached",
            "campaign_id",
            "attached_at",
        ),
    )


class CampaignSegmentMemberModel(Base):
    """Materialized member captured from one attached Segment source."""

    __tablename__ = "pycrmkit_campaign_segment_members"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    campaign_id: Mapped[str] = mapped_column(String(36), nullable=False)
    segment_id: Mapped[str] = mapped_column(String(36), nullable=False)
    entity_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ("campaign_id", "segment_id"),
            (
                "pycrmkit_campaign_segment_sources.campaign_id",
                "pycrmkit_campaign_segment_sources.segment_id",
            ),
            name="fk_pycrmkit_campaign_segment_members_source",
            ondelete="CASCADE",
        ),
        Index(
            "ix_pycrmkit_campaign_segment_members_source",
            "campaign_id",
            "segment_id",
        ),
        Index(
            "ix_pycrmkit_campaign_segment_members_entity",
            "entity_kind",
            "entity_id",
        ),
        UniqueConstraint(
            "campaign_id",
            "segment_id",
            "entity_kind",
            "entity_id",
            name="uq_pycrmkit_campaign_segment_members_target",
        ),
    )


class CampaignAttributionModel(Base):
    """Lightweight Campaign attribution/provenance reference."""

    __tablename__ = "pycrmkit_campaign_attributions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    campaign_id: Mapped[str] = mapped_column(
        ForeignKey("pycrmkit_campaigns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    target_id: Mapped[str] = mapped_column(String(36), nullable=False)
    source: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    external_ref: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        default="",
    )
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actor_id: Mapped[str | None] = mapped_column(String(255))
    metadata_json: Mapped[dict[str, object]] = mapped_column(
        "metadata",
        JSON,
        default=dict,
    )

    __table_args__ = (
        Index(
            "ix_pycrmkit_campaign_attributions_target",
            "target_kind",
            "target_id",
        ),
        Index(
            "ix_pycrmkit_campaign_attributions_campaign_recorded",
            "campaign_id",
            "recorded_at",
        ),
        UniqueConstraint(
            "campaign_id",
            "target_kind",
            "target_id",
            "source",
            "external_ref",
            name="uq_pycrmkit_campaign_attributions_reference",
        ),
    )


class CampaignCommunicationLinkModel(Base):
    """Reference from a Campaign to an existing CommunicationRecord."""

    __tablename__ = "pycrmkit_campaign_communication_links"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    campaign_id: Mapped[str] = mapped_column(
        ForeignKey("pycrmkit_campaigns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    communication_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    role: Mapped[str] = mapped_column(String(120), nullable=False)
    actor_id: Mapped[str | None] = mapped_column(String(255))
    metadata_json: Mapped[dict[str, object]] = mapped_column(
        "metadata",
        JSON,
        default=dict,
    )

    __table_args__ = (
        Index(
            "ix_pycrmkit_campaign_communication_links_campaign_linked",
            "campaign_id",
            "linked_at",
        ),
        UniqueConstraint(
            "campaign_id",
            "communication_id",
            name="uq_pycrmkit_campaign_communication_links_record",
        ),
    )


__all__ = [
    "CampaignAttributionModel",
    "CampaignCommunicationLinkModel",
    "CampaignMemberModel",
    "CampaignModel",
    "CampaignSegmentMemberModel",
    "CampaignSegmentSourceModel",
]
