# PyCRMKit

PyCRMKit is a modular, headless Python CRM domain framework.

The current **`0.3.0b2 — Lead Conversion`** milestone builds on the stable
`0.1` CRM Core and stable `0.2` Activity/Task/Timeline contract with the Sales
Foundation:

```text
Application
    ↓
CRM facade
    ↓
Contacts / Organizations / Relationships
Activities / Tasks / Timeline
Leads / Opportunities / Pipelines
    ↓
Domain services + policies + events
    ↓
Unit of Work / Repository contracts
    ↓
Memory adapter
```

A minimal sales flow can now run fully in memory:

```python
from decimal import Decimal

from pycrmkit import CRM
from pycrmkit.pipelines import Stage, StageTransition

crm = CRM.memory()
contact = crm.contacts.create(first_name="Ada", last_name="Lovelace")
lead = crm.leads.create(contact_id=contact.id)
lead = crm.leads.qualify(lead.id)

crm.pipelines.define(
    id="sales",
    name="Sales",
    stages=(
        Stage("new", "New", 0, Decimal("0.10")),
        Stage("won", "Won", 10, terminal=True, outcome="won"),
    ),
    transitions=(StageTransition("new", "won"),),
)

opportunity = crm.leads.convert(
    lead.id,
    estimated_value=Decimal("25000"),
    currency="EUR",
    pipeline_id="sales",
    idempotency_key="lead-conversion-demo",
)
opportunity = crm.opportunities.move(opportunity.id, to="won")
```

Lead conversion is atomic at the Unit-of-Work boundary and idempotent at the
domain workflow level. Activities and Tasks continue to feed the customer
Timeline; Sales Timeline projection remains outside this beta.

Django, FastAPI, SQLAlchemy, PostgreSQL, communication providers, AI, and agent
integrations remain optional later milestones.
