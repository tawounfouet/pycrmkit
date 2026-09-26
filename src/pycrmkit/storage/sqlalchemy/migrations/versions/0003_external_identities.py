"""Add external identity mappings for the V0.9 data-operations line."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pycrmkit_external_identities",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("system", sa.String(length=128), nullable=False),
        sa.Column("external_id", sa.String(length=512), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.String(length=36), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pycrmkit_external_identities")),
        sa.UniqueConstraint(
            "system",
            "external_id",
            name="uq_pycrmkit_external_identities_system_external_id",
        ),
    )
    op.create_index(
        "ix_pycrmkit_external_identities_entity",
        "pycrmkit_external_identities",
        ["entity_type", "entity_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_pycrmkit_external_identities_entity",
        table_name="pycrmkit_external_identities",
    )
    op.drop_table("pycrmkit_external_identities")
