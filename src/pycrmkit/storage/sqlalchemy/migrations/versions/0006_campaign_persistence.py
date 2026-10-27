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


