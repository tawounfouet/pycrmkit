# Pipelines & Stages

`0.3.0b1` introduces configurable commercial pipelines and explicit stage-transition policies.

## Definition

```python
from decimal import Decimal

from pycrmkit import CRM
from pycrmkit.opportunities import OpportunityStatus
from pycrmkit.pipelines import Stage, StageTransition

crm = CRM.memory()
crm.pipelines.define(
    id="sales",
    name="Sales",
    stages=(
        Stage("new", "New", 0, Decimal("0.10")),
        Stage("qualified", "Qualified", 1, Decimal("0.35")),
        Stage("proposal", "Proposal", 2, Decimal("0.65")),
        Stage("won", "Won", 3, terminal=True, outcome=OpportunityStatus.WON),
        Stage("lost", "Lost", 4, terminal=True, outcome=OpportunityStatus.LOST),
    ),
    transitions=(
        StageTransition("new", "qualified"),
        StageTransition("qualified", "proposal"),
        StageTransition("proposal", "won"),
        StageTransition("proposal", "lost"),
    ),
)
```

## Invariants

- pipeline and stage IDs are stable normalized string keys;
- stages have unique IDs and unique ordering positions;
- transition endpoints must exist in the pipeline;
- terminal stages cannot have outgoing transitions;
- terminal stages declare `won`, `lost`, or `cancelled` outcomes;
- stage probabilities are finite `Decimal` values in `[0, 1]`;
- terminal `won` defaults to probability `1`, while `lost/cancelled` default to `0`;
- invalid movement raises `InvalidStageTransition`.

## Opportunity movement

```python
opportunity = crm.opportunities.create(
    name="Enterprise renewal",
    contact_id=contact.id,
    pipeline_id="sales",
    stage_id="new",
)

opportunity = crm.opportunities.move(opportunity.id, to="qualified")
opportunity = crm.opportunities.move(opportunity.id, to="proposal")
opportunity = crm.opportunities.move(opportunity.id, to="won")
```

Each accepted movement updates `stage_id`, `stage_entered_at`, `updated_at`, and the stage default probability. Entering a terminal stage also closes the Opportunity with the stage outcome.

`Opportunity.stage_duration(at)` reports elapsed time in the current stage. Historical per-stage duration records are intentionally deferred; `0.3.0b1` establishes the stage-entry timestamp needed for that future projection.

## Events and audit

Pipeline creation emits `pipeline.created`. Opportunity movement emits `opportunity.stage_changed`; entering a terminal stage additionally emits `opportunity.won`, `opportunity.lost`, or `opportunity.cancelled`. Audit records are staged in the same Unit of Work and external event subscribers run after commit.

Lead conversion remains outside this milestone and is scheduled for `0.3.0b2`.
