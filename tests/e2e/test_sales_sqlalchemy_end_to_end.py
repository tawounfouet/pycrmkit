"""Sales transaction qualification through the SQLAlchemy Unit of Work."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from pycrmkit import CRM
from pycrmkit.core.time import FixedClock
from pycrmkit.core.unit_of_work import UnitOfWork
from pycrmkit.events import InProcessEventBus
from pycrmkit.leads import LeadStatus
from pycrmkit.opportunities import OpportunityStatus
from pycrmkit.pipelines import Stage, StageTransition
from pycrmkit.storage.sqlalchemy import Base, SQLAlchemyUnitOfWork

NOW = datetime(2026, 9, 26, 13, 0, tzinfo=UTC)


def _crm(tmp_path: Path) -> CRM:
    engine = create_engine(
        f"sqlite+pysqlite:///{tmp_path / 'sales.sqlite'}",
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    bus = InProcessEventBus()

    def uow_factory() -> UnitOfWork:
        return SQLAlchemyUnitOfWork(factory, event_publisher=bus)

    return CRM(
        uow_factory=uow_factory,
        event_bus=bus,
        clock=FixedClock(NOW),
        webhook_auto_delivery=False,
    )


def _define_pipeline(crm: CRM) -> None:
    crm.pipelines.define(
        id="sales",
        name="Sales",
        stages=(
            Stage("new", "New", 0, Decimal("0.10")),
            Stage("qualified", "Qualified", 10, Decimal("0.30")),
            Stage("proposal", "Proposal", 20, Decimal("0.60")),
            Stage("won", "Won", 30, terminal=True, outcome="won"),
            Stage("lost", "Lost", 40, terminal=True, outcome="lost"),
        ),
        transitions=(
            StageTransition("new", "qualified"),
            StageTransition("qualified", "proposal"),
            StageTransition("proposal", "won"),
            StageTransition("proposal", "lost"),
        ),
    )


def test_lead_conversion_commits_shared_transaction(tmp_path: Path) -> None:
    crm = _crm(tmp_path).with_context(
        actor_id="seller-sqlalchemy",
        correlation_id="corr-sqlalchemy-convert",
    )
    contact = crm.contacts.create(first_name="Ada", last_name="Lovelace")
    organization = crm.organizations.create(legal_name="Analytical Engines")
    _define_pipeline(crm)

    lead = crm.leads.create(
        contact_id=contact.id,
        organization_id=organization.id,
        source="website",
    )
    crm.leads.qualify(lead.id)

    opportunity = crm.leads.convert(
        lead.id,
        name="SQLAlchemy rollout",
        estimated_value=Decimal("25000"),
        currency="EUR",
        pipeline_id="sales",
        idempotency_key="sqlalchemy-convert-001",
    )

    with crm._runtime.uow_factory() as uow:
        persisted_lead = uow.leads.get(lead.id)
        persisted_opportunity = uow.opportunities.get(opportunity.id)

    assert persisted_lead.status is LeadStatus.CONVERTED
    assert persisted_lead.converted_opportunity_id == opportunity.id
    assert persisted_opportunity == opportunity
    assert persisted_opportunity.stage_id == "new"
    assert persisted_opportunity.probability == Decimal("0.10")

    audit = crm.audit.by_correlation("corr-sqlalchemy-convert")
    assert {entry.action for entry in audit.items} >= {
        "lead.converted",
        "opportunity.created",
    }


def test_pipeline_transition_persists_with_audit_in_same_uow(tmp_path: Path) -> None:
    crm = _crm(tmp_path).with_context(
        actor_id="seller-sqlalchemy",
        correlation_id="corr-sqlalchemy-pipeline",
    )
    contact = crm.contacts.create(display_name="Pipeline Customer")
    _define_pipeline(crm)
    lead = crm.leads.create(contact_id=contact.id)
    crm.leads.qualify(lead.id)
    opportunity = crm.leads.convert(
        lead.id,
        pipeline_id="sales",
        idempotency_key="sqlalchemy-pipeline-001",
    )

    for stage in ("qualified", "proposal", "won"):
        opportunity = crm.opportunities.move(opportunity.id, to=stage)

    assert opportunity.status is OpportunityStatus.WON
    assert opportunity.stage_id == "won"
    assert opportunity.probability == Decimal("1")

    with crm._runtime.uow_factory() as uow:
        assert uow.opportunities.get(opportunity.id) == opportunity

    actions = {entry.action for entry in crm.audit.by_correlation(
        "corr-sqlalchemy-pipeline"
    ).items}
    assert "opportunity.stage_changed" in actions
    assert "opportunity.won" in actions
