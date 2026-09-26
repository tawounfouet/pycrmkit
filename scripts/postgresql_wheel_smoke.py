"""Installed-wheel smoke test against an already migrated PostgreSQL database."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from pycrmkit import CRM, __version__
from pycrmkit.core.time import FixedClock
from pycrmkit.core.unit_of_work import UnitOfWork
from pycrmkit.events import InProcessEventBus
from pycrmkit.pipelines import Stage, StageTransition
from pycrmkit.storage.sqlalchemy import SQLAlchemyUnitOfWork


def main() -> None:
    database_url = os.environ["PYCRMKIT_TEST_POSTGRES_URL"]
    engine = create_engine(database_url, pool_pre_ping=True)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    bus = InProcessEventBus()

    def uow_factory() -> UnitOfWork:
        return SQLAlchemyUnitOfWork(factory, event_publisher=bus)

    crm = CRM(
        uow_factory=uow_factory,
        event_bus=bus,
        clock=FixedClock(datetime(2026, 9, 26, 16, 0, tzinfo=UTC)),
        webhook_auto_delivery=False,
    ).with_context(
        actor_id="wheel-smoke",
        correlation_id="wheel-smoke-postgresql",
    )

    contact = crm.contacts.create(
        first_name="Wheel",
        last_name="PostgreSQL",
    )
    crm.pipelines.define(
        id="wheel-sales",
        name="Wheel Sales",
        stages=(
            Stage("new", "New", 0, Decimal("0.10")),
            Stage("won", "Won", 10, terminal=True, outcome="won"),
        ),
        transitions=(StageTransition("new", "won"),),
    )
    lead = crm.leads.create(contact_id=contact.id, source="wheel")
    crm.leads.qualify(lead.id)
    opportunity = crm.leads.convert(
        lead.id,
        pipeline_id="wheel-sales",
        idempotency_key="wheel-postgresql-smoke",
    )
    opportunity = crm.opportunities.move(opportunity.id, to="won")

    with SQLAlchemyUnitOfWork(factory) as uow:
        assert uow.contacts.get(contact.id) == contact
        assert uow.opportunities.get(opportunity.id) == opportunity

    assert crm.audit.by_correlation("wheel-smoke-postgresql").total >= 4
    print(f"PyCRMKit {__version__} wheel PostgreSQL smoke: OK")
    engine.dispose()


if __name__ == "__main__":
    main()
