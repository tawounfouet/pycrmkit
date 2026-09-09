from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from pycrmkit import CRM
from pycrmkit.core.time import FixedClock
from pycrmkit.pipelines import InvalidStageTransition, Stage, StageTransition


def define_sales_pipeline(crm: CRM) -> None:
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


def test_pipeline_definition_and_opportunity_move_emit_events_and_audit() -> None:
    clock = FixedClock(datetime(2026, 9, 9, 9, tzinfo=UTC))
    crm = CRM.memory(clock=clock)
    define_sales_pipeline(crm)
    assert crm.pipelines.get("sales").initial_stage.id == "new"

    contact = crm.contacts.create(first_name="Ada", last_name="Lovelace")
    opportunity = crm.opportunities.create(
        name="Enterprise renewal",
        contact_id=contact.id,
        pipeline_id="sales",
        stage_id="new",
        probability=Decimal("0.10"),
    )
    events = []
    crm.events.subscribe("opportunity.stage_changed", events.append)

    clock.advance(timedelta(hours=1))
    moved = crm.opportunities.move(opportunity.id, to="qualified")
    assert moved.stage_id == "qualified"
    assert moved.probability == Decimal("0.30")
    assert moved.stage_entered_at == clock.now()
    assert len(events) == 1
    assert events[0].payload["from_stage"] == "new"
    assert events[0].payload["to_stage"] == "qualified"

    audits = crm.audit.for_entity("opportunity", str(opportunity.id))
    assert "opportunity.stage_changed" in {entry.action for entry in audits.items}


def test_invalid_jump_rolls_back_without_event_or_audit() -> None:
    crm = CRM.memory()
    define_sales_pipeline(crm)
    contact = crm.contacts.create(first_name="Grace", last_name="Hopper")
    opportunity = crm.opportunities.create(
        name="Compiler deal",
        contact_id=contact.id,
        pipeline_id="sales",
        stage_id="new",
    )
    events = []
    crm.events.subscribe("opportunity.stage_changed", events.append)
    before_audit = crm.audit.for_entity("opportunity", str(opportunity.id)).total

    with pytest.raises(InvalidStageTransition):
        crm.opportunities.move(opportunity.id, to="won")

    assert events == []
    assert crm.audit.for_entity("opportunity", str(opportunity.id)).total == before_audit
