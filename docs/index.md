# PyCRMKit

PyCRMKit is a modular, headless Python CRM domain framework.

The current **`0.3.0 — Sales Foundation Stable`** release promotes the
qualified Sales Foundation on top of the stable `0.1` CRM Core and stable
`0.2` Activity/Task/Timeline contract:

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

The stable Sales path is:

```text
Lead
  ↓ qualify
Qualified Lead
  ↓ atomic/idempotent convert
Opportunity
  ↓ Pipeline initial Stage
new → qualified → proposal → won/lost
```

The `0.3.x` line now compatibility-governs the documented Lead, Opportunity
and Pipeline facade surface. Sales events remain outside Timeline projection.

The next roadmap line begins with **`0.4.0a1 — Communication Domain`**.
Django, FastAPI, SQLAlchemy, PostgreSQL, durable event delivery, AI and agent
integrations remain later milestones.
