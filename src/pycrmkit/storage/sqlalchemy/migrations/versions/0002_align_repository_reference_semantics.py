"""align repository reference semantics

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-26 16:20:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Remove cross-aggregate FKs not required by repository contracts."""

    op.drop_constraint(
        op.f("fk_pycrmkit_leads_contact_id_pycrmkit_contacts"),
        "pycrmkit_leads",
        type_="foreignkey",
    )
    op.drop_constraint(
        op.f("fk_pycrmkit_leads_organization_id_pycrmkit_organizations"),
        "pycrmkit_leads",
        type_="foreignkey",
    )
    op.drop_constraint(
        op.f("fk_pycrmkit_opportunities_contact_id_pycrmkit_contacts"),
        "pycrmkit_opportunities",
        type_="foreignkey",
    )
    op.drop_constraint(
        op.f("fk_pycrmkit_opportunities_organization_id_pycrmkit_organizations"),
        "pycrmkit_opportunities",
        type_="foreignkey",
    )
    op.drop_constraint(
        op.f(
            "fk_pycrmkit_webhook_deliveries_subscription_id_"
            "pycrmkit_webhook_subscriptions"
        ),
        "pycrmkit_webhook_deliveries",
        type_="foreignkey",
    )


def downgrade() -> None:
    """Restore the stricter 0001 cross-aggregate FK policy."""

    op.create_foreign_key(
        op.f(
            "fk_pycrmkit_webhook_deliveries_subscription_id_"
            "pycrmkit_webhook_subscriptions"
        ),
        "pycrmkit_webhook_deliveries",
        "pycrmkit_webhook_subscriptions",
        ["subscription_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        op.f("fk_pycrmkit_opportunities_organization_id_pycrmkit_organizations"),
        "pycrmkit_opportunities",
        "pycrmkit_organizations",
        ["organization_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        op.f("fk_pycrmkit_opportunities_contact_id_pycrmkit_contacts"),
        "pycrmkit_opportunities",
        "pycrmkit_contacts",
        ["contact_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        op.f("fk_pycrmkit_leads_organization_id_pycrmkit_organizations"),
        "pycrmkit_leads",
        "pycrmkit_organizations",
        ["organization_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        op.f("fk_pycrmkit_leads_contact_id_pycrmkit_contacts"),
        "pycrmkit_leads",
        "pycrmkit_contacts",
        ["contact_id"],
        ["id"],
        ondelete="RESTRICT",
    )
