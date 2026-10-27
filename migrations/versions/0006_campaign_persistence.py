"""Persist Campaign metadata, audiences, attribution and communication linkage."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pycrmkit_campaigns",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("key", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.String(length=2000), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("owner_id", sa.String(length=36), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pycrmkit_campaigns")),
        sa.UniqueConstraint("key", name=op.f("uq_pycrmkit_campaigns_key")),
    )
    op.create_index(op.f("ix_pycrmkit_campaigns_status"), "pycrmkit_campaigns", ["status"])
    op.create_index(op.f("ix_pycrmkit_campaigns_owner_id"), "pycrmkit_campaigns", ["owner_id"])
    op.create_index(op.f("ix_pycrmkit_campaigns_archived_at"), "pycrmkit_campaigns", ["archived_at"])
    op.create_index("ix_pycrmkit_campaigns_created_at", "pycrmkit_campaigns", ["created_at"])

    op.create_table(
        "pycrmkit_campaign_members",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("campaign_id", sa.String(length=36), nullable=False),
        sa.Column("entity_kind", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.String(length=36), nullable=False),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(length=120), nullable=False),
        sa.Column("actor_id", sa.String(length=255), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["pycrmkit_campaigns.id"],
            name=op.f("fk_pycrmkit_campaign_members_campaign_id_pycrmkit_campaigns"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pycrmkit_campaign_members")),
        sa.UniqueConstraint(
            "campaign_id", "entity_kind", "entity_id",
            name="uq_pycrmkit_campaign_members_target",
        ),
    )
    op.create_index(
        op.f("ix_pycrmkit_campaign_members_campaign_id"),
        "pycrmkit_campaign_members",
        ["campaign_id"],
    )
    op.create_index(
        "ix_pycrmkit_campaign_members_entity",
        "pycrmkit_campaign_members",
        ["entity_kind", "entity_id"],
    )


    op.create_table(
        "pycrmkit_campaign_segment_sources",
        sa.Column("campaign_id", sa.String(length=36), nullable=False),
        sa.Column("segment_id", sa.String(length=36), nullable=False),
        sa.Column("segment_revision", sa.Integer(), nullable=False),
        sa.Column("entity_kind", sa.String(length=64), nullable=False),
        sa.Column("attached_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("member_count", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.String(length=255), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["pycrmkit_campaigns.id"],
            name=op.f(
                "fk_pycrmkit_campaign_segment_sources_campaign_id_pycrmkit_campaigns"
            ),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "campaign_id",
            "segment_id",
            name=op.f("pk_pycrmkit_campaign_segment_sources"),
        ),
    )
    op.create_index(
        "ix_pycrmkit_campaign_segment_sources_segment_id",
        "pycrmkit_campaign_segment_sources",
        ["segment_id"],
    )
    op.create_index(
        "ix_pycrmkit_campaign_segment_sources_campaign_attached",
        "pycrmkit_campaign_segment_sources",
        ["campaign_id", "attached_at"],
    )

    op.create_table(
        "pycrmkit_campaign_segment_members",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("campaign_id", sa.String(length=36), nullable=False),
        sa.Column("segment_id", sa.String(length=36), nullable=False),
        sa.Column("entity_kind", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(
            ["campaign_id", "segment_id"],
            [
                "pycrmkit_campaign_segment_sources.campaign_id",
                "pycrmkit_campaign_segment_sources.segment_id",
            ],
            name="fk_pycrmkit_campaign_segment_members_source",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name=op.f("pk_pycrmkit_campaign_segment_members"),
        ),
        sa.UniqueConstraint(
            "campaign_id",
            "segment_id",
            "entity_kind",
            "entity_id",
            name="uq_pycrmkit_campaign_segment_members_target",
        ),
    )
    op.create_index(
        "ix_pycrmkit_campaign_segment_members_source",
        "pycrmkit_campaign_segment_members",
        ["campaign_id", "segment_id"],
    )
    op.create_index(
        "ix_pycrmkit_campaign_segment_members_entity",
        "pycrmkit_campaign_segment_members",
        ["entity_kind", "entity_id"],
    )


    op.create_table(
        "pycrmkit_campaign_attributions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("campaign_id", sa.String(length=36), nullable=False),
        sa.Column("target_kind", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.String(length=36), nullable=False),
        sa.Column("source", sa.String(length=120), nullable=False),
        sa.Column("external_ref", sa.String(length=512), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_id", sa.String(length=255), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["pycrmkit_campaigns.id"],
            name=op.f(
                "fk_pycrmkit_campaign_attributions_campaign_id_pycrmkit_campaigns"
            ),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name=op.f("pk_pycrmkit_campaign_attributions"),
        ),
        sa.UniqueConstraint(
            "campaign_id",
            "target_kind",
            "target_id",
            "source",
            "external_ref",
            name="uq_pycrmkit_campaign_attributions_reference",
        ),
    )
    op.create_index(
        op.f("ix_pycrmkit_campaign_attributions_campaign_id"),
        "pycrmkit_campaign_attributions",
        ["campaign_id"],
    )
    op.create_index(
        op.f("ix_pycrmkit_campaign_attributions_source"),
        "pycrmkit_campaign_attributions",
        ["source"],
    )
    op.create_index(
        "ix_pycrmkit_campaign_attributions_target",
        "pycrmkit_campaign_attributions",
        ["target_kind", "target_id"],
    )
    op.create_index(
        "ix_pycrmkit_campaign_attributions_campaign_recorded",
        "pycrmkit_campaign_attributions",
        ["campaign_id", "recorded_at"],
    )

    op.create_table(
        "pycrmkit_campaign_communication_links",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("campaign_id", sa.String(length=36), nullable=False),
        sa.Column("communication_id", sa.String(length=36), nullable=False),
        sa.Column("linked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("role", sa.String(length=120), nullable=False),
        sa.Column("actor_id", sa.String(length=255), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["pycrmkit_campaigns.id"],
            name=op.f(
                "fk_pycrmkit_campaign_communication_links_campaign_id_pycrmkit_campaigns"
            ),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name=op.f("pk_pycrmkit_campaign_communication_links"),
        ),
        sa.UniqueConstraint(
            "campaign_id",
            "communication_id",
            name="uq_pycrmkit_campaign_communication_links_record",
        ),
    )
    op.create_index(
        op.f("ix_pycrmkit_campaign_communication_links_campaign_id"),
        "pycrmkit_campaign_communication_links",
        ["campaign_id"],
    )
    op.create_index(
        op.f("ix_pycrmkit_campaign_communication_links_communication_id"),
        "pycrmkit_campaign_communication_links",
        ["communication_id"],
    )
    op.create_index(
        "ix_pycrmkit_campaign_communication_links_campaign_linked",
        "pycrmkit_campaign_communication_links",
        ["campaign_id", "linked_at"],
    )


def downgrade() -> None:
    op.drop_table("pycrmkit_campaign_communication_links")
    op.drop_table("pycrmkit_campaign_attributions")
    op.drop_table("pycrmkit_campaign_segment_members")
    op.drop_table("pycrmkit_campaign_segment_sources")
    op.drop_table("pycrmkit_campaign_members")
    op.drop_table("pycrmkit_campaigns")
