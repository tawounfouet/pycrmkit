"""Persist Segments, memberships and SavedQuery revisions."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pycrmkit_segments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("key", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("entity_kind", sa.String(length=64), nullable=False),
        sa.Column("mode", sa.String(length=32), nullable=False),
        sa.Column("description", sa.String(length=2000), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("query", sa.JSON(), nullable=True),
        sa.Column("saved_query_id", sa.String(length=36), nullable=True),
        sa.Column("saved_query_revision", sa.Integer(), nullable=True),
        sa.Column("owner_id", sa.String(length=36), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pycrmkit_segments")),
        sa.UniqueConstraint("key", name=op.f("uq_pycrmkit_segments_key")),
    )
    op.create_index(
        op.f("ix_pycrmkit_segments_archived_at"),
        "pycrmkit_segments",
        ["archived_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_pycrmkit_segments_entity_kind"),
        "pycrmkit_segments",
        ["entity_kind"],
        unique=False,
    )
    op.create_index(
        op.f("ix_pycrmkit_segments_mode"),
        "pycrmkit_segments",
        ["mode"],
        unique=False,
    )
    op.create_index(
        op.f("ix_pycrmkit_segments_owner_id"),
        "pycrmkit_segments",
        ["owner_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_pycrmkit_segments_saved_query_id"),
        "pycrmkit_segments",
        ["saved_query_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_pycrmkit_segments_status"),
        "pycrmkit_segments",
        ["status"],
        unique=False,
    )

    op.create_table(
        "pycrmkit_saved_queries",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("entity_kind", sa.String(length=64), nullable=False),
        sa.Column("expression", sa.JSON(), nullable=False),
        sa.Column("ordering", sa.JSON(), nullable=False),
        sa.Column("owner_id", sa.String(length=36), nullable=True),
        sa.Column("visibility", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint(
            "id",
            "revision",
            name=op.f("pk_pycrmkit_saved_queries"),
        ),
        sa.UniqueConstraint(
            "key",
            "revision",
            name="uq_pycrmkit_saved_queries_key_revision",
        ),
    )
    op.create_index(
        op.f("ix_pycrmkit_saved_queries_archived_at"),
        "pycrmkit_saved_queries",
        ["archived_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_pycrmkit_saved_queries_entity_kind"),
        "pycrmkit_saved_queries",
        ["entity_kind"],
        unique=False,
    )
    op.create_index(
        "ix_pycrmkit_saved_queries_id_revision",
        "pycrmkit_saved_queries",
        ["id", "revision"],
        unique=False,
    )
    op.create_index(
        op.f("ix_pycrmkit_saved_queries_key"),
        "pycrmkit_saved_queries",
        ["key"],
        unique=False,
    )
    op.create_index(
        op.f("ix_pycrmkit_saved_queries_owner_id"),
        "pycrmkit_saved_queries",
        ["owner_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_pycrmkit_saved_queries_status"),
        "pycrmkit_saved_queries",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_pycrmkit_saved_queries_visibility"),
        "pycrmkit_saved_queries",
        ["visibility"],
        unique=False,
    )

    op.create_table(
        "pycrmkit_segment_members",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("segment_id", sa.String(length=36), nullable=False),
        sa.Column("entity_kind", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.String(length=36), nullable=False),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(length=120), nullable=False),
        sa.Column("actor_id", sa.String(length=255), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["segment_id"],
            ["pycrmkit_segments.id"],
            name=op.f(
                "fk_pycrmkit_segment_members_segment_id_pycrmkit_segments"
            ),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pycrmkit_segment_members")),
        sa.UniqueConstraint(
            "segment_id",
            "entity_kind",
            "entity_id",
            name="uq_pycrmkit_segment_members_target",
        ),
    )
    op.create_index(
        "ix_pycrmkit_segment_members_entity",
        "pycrmkit_segment_members",
        ["entity_kind", "entity_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_pycrmkit_segment_members_segment_id"),
        "pycrmkit_segment_members",
        ["segment_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_pycrmkit_segment_members_segment_id"),
        table_name="pycrmkit_segment_members",
    )
    op.drop_index(
        "ix_pycrmkit_segment_members_entity",
        table_name="pycrmkit_segment_members",
    )
    op.drop_table("pycrmkit_segment_members")

    op.drop_index(
        op.f("ix_pycrmkit_saved_queries_visibility"),
        table_name="pycrmkit_saved_queries",
    )
    op.drop_index(
        op.f("ix_pycrmkit_saved_queries_status"),
        table_name="pycrmkit_saved_queries",
    )
    op.drop_index(
        op.f("ix_pycrmkit_saved_queries_owner_id"),
        table_name="pycrmkit_saved_queries",
    )
    op.drop_index(
        op.f("ix_pycrmkit_saved_queries_key"),
        table_name="pycrmkit_saved_queries",
    )
    op.drop_index(
        "ix_pycrmkit_saved_queries_id_revision",
        table_name="pycrmkit_saved_queries",
    )
    op.drop_index(
        op.f("ix_pycrmkit_saved_queries_entity_kind"),
        table_name="pycrmkit_saved_queries",
    )
    op.drop_index(
        op.f("ix_pycrmkit_saved_queries_archived_at"),
        table_name="pycrmkit_saved_queries",
    )
    op.drop_table("pycrmkit_saved_queries")

    op.drop_index(
        op.f("ix_pycrmkit_segments_status"),
        table_name="pycrmkit_segments",
    )
    op.drop_index(
        op.f("ix_pycrmkit_segments_saved_query_id"),
        table_name="pycrmkit_segments",
    )
    op.drop_index(
        op.f("ix_pycrmkit_segments_owner_id"),
        table_name="pycrmkit_segments",
    )
    op.drop_index(
        op.f("ix_pycrmkit_segments_mode"),
        table_name="pycrmkit_segments",
    )
    op.drop_index(
        op.f("ix_pycrmkit_segments_entity_kind"),
        table_name="pycrmkit_segments",
    )
    op.drop_index(
        op.f("ix_pycrmkit_segments_archived_at"),
        table_name="pycrmkit_segments",
    )
    op.drop_table("pycrmkit_segments")
