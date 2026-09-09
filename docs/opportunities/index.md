# Opportunities

`0.3.0a2` introduces the first-class Opportunity domain without yet introducing configurable Pipeline/Stage definitions.

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
    stage_id="proposal",
    estimated_value=Decimal("25000.00"),
    currency="EUR",
    probability=Decimal("0.65"),
    expected_close_date=date(2026, 12, 31),
    owner_id="seller-1",
)
```

Fields:

```text
name
contact_id
organization_id
pipeline_id
stage_id
estimated_value
currency
probability
expected_close_date
owner_id
status
```

## Invariants

- `name` is required and normalized.
- `contact_id` is a typed `ContactId`.
- `organization_id` is an optional typed `OrganizationId`.
- `stage_id` requires `pipeline_id`; stage validity is not checked until `0.3.0b1`.
- estimated value uses `Decimal` and requires a currency; float persistence is rejected through `Money`.
- probability is optional `Decimal` in the closed interval `[0, 1]`.
- expected close is a calendar `date`, not a timestamp.

## Lifecycle

The Opportunity aggregate supports:

```text
open → won
open → lost
open → cancelled
```

Terminal opportunities reject a second outcome transition.

These lifecycle operations are available on the aggregate/service contract in `0.3.0a2`, but the public facade remains deliberately narrow while the Pipeline API is still under construction.

## Public facade

`0.3.0a2` exposes only:

```text
crm.opportunities.create(...)
```

The following remain deferred:

```text
crm.opportunities.move(...)       → 0.3.0b1
crm.leads.convert(...)            → 0.3.0b2
```

`opportunity.created` is emitted after commit and receives the normal facade actor/correlation context. Opportunity events are not projected into Timeline in this alpha.
