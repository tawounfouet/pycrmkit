"""Add TaskType to persisted CRM tasks for the 1.1 sales-work line."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "pycrmkit_tasks",
        sa.Column(
            "task_type",
            sa.String(length=32),
            nullable=False,
            server_default="general",
        ),
    )
    op.create_index(
        "ix_pycrmkit_tasks_task_type",
        "pycrmkit_tasks",
        ["task_type"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_pycrmkit_tasks_task_type",
        table_name="pycrmkit_tasks",
    )
    op.drop_column("pycrmkit_tasks", "task_type")
