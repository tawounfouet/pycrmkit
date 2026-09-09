from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from pycrmkit import CRM
from pycrmkit.core.time import FixedClock
from pycrmkit.opportunities import OpportunityStatus
from pycrmkit.pipelines import InvalidStageTransition, Stage, StageTransition


def test_opportunity_moves_through_pipeline_and_closes_won() -> None:
    clock = FixedClock(datetime(2026, 9, 9, 9, tzinfo=UTC))
    crm = CRM.memory(clock=clock)
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
    contact = crm.contacts.create(first_name="Ada", last_name="Lovelace")
    opportunity = crm.opportunities.create(
        name="Enterprise renewal",
        contact_id=contact.id,
        pipeline_id="sales",
        stage_id="new",
        probability=Decimal("0.10"),
    )

    with pytest.raises(InvalidStageTransition):
        crm.opportunities.move(opportunity.id, to="won")

    for stage in ("qualified", "proposal", "won"):
        clock.advance(timedelta(hours=1))
        opportunity = crm.opportunities.move(opportunity.id, to=stage)

    assert opportunity.status is OpportunityStatus.WON
    assert opportunity.stage_id == "won"
    assert opportunity.probability == Decimal("1")
