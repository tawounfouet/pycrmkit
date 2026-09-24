# PyCRMKit

PyCRMKit is a modular, headless Python CRM domain framework.

The current **`0.3.0rc1 — Sales Integration`** milestone qualifies and freezes
the candidate `0.3` Sales Foundation on top of the stable `0.1` CRM Core and
stable `0.2` Activity/Task/Timeline contract:

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

The complete Sales path is now release-candidate qualified:

```text
Lead
  ↓ qualify
Qualified Lead
  ↓ atomic/idempotent convert
Opportunity
  ↓ Pipeline initial Stage
new → qualified → proposal → won/lost
```

The RC also freezes the candidate facade surface and qualifies normalized Sales
events, transactional audit, invalid-transition rejection, won/lost outcomes,
Python 3.11–3.13, package build, installed-wheel smoke and strict docs.

Sales events are not yet projected into Timeline. Django, FastAPI, SQLAlchemy,
PostgreSQL, communication providers, durable event delivery, AI, and agent
integrations remain later milestones.
