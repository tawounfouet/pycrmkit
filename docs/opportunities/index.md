# Opportunities

`0.3.0a2` introduced first-class Opportunities; `0.3.0b1` connects them to configurable Pipeline/Stage transition policies.

An Opportunity represents a potential commercial transaction or business outcome.

## Domain model

```python
from datetime import date
from decimal import Decimal

from pycrmkit import CRM

crm = CRM.memory()
contact = crm.contacts.create(first_name="Ada", last_name="Lovelace")

opportunity = crm.opportunities.create(
    name="Enterprise renewal",
    contact_id=contact.id,
    pipeline_id="sales",
    stage_id="new",
    estimated_value=Decimal("25000.00"),
    currency="EUR",
    probability=Decimal("0.10"),
    expected_close_date=date(2026, 12, 31),
    owner_id="seller-1",
)
```

`stage_entered_at` records the UTC instant at which the current stage was entered. If an Opportunity is created with a stage and no explicit stage-entry time, it starts at `created_at`.

## Lifecycle and movement

The aggregate statuses remain:

```text
open → won
open → lost
open → cancelled
```

At `0.3.0b1`, stage changes must satisfy the persisted Pipeline definition:

```python
opportunity = crm.opportunities.move(opportunity.id, to="qualified")
```

Invalid transitions raise `InvalidStageTransition`. A target stage's default probability is applied automatically. Entering a terminal stage closes the Opportunity with the configured outcome.

`Opportunity.stage_duration(at)` reports elapsed time since the current `stage_entered_at`.

## Public facade

```text
crm.opportunities.create(...)
crm.opportunities.move(...)
```

Direct `mark_won`, `mark_lost`, `get`, and `list` remain outside the facade for this beta; terminal outcomes are reached through pipeline policy.

`opportunity.created`, `opportunity.stage_changed`, and terminal outcome events are emitted after commit and preserve normal actor/correlation context. Sales events are not yet projected into Timeline.

`crm.leads.convert(...)` remains deferred to `0.3.0b2`.
