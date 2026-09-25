# PyCRMKit

PyCRMKit is a modular, headless Python CRM domain framework.

The current **`0.4.0 — Communication Stable`** release promotes the complete
Communication line on top of the stable `0.1` CRM Core, `0.2`
Activity/Task/Timeline and `0.3` Sales contracts:

```text
Application
    ↓
CRM facade
    ↓
Contacts / Organizations / Relationships
Activities / Tasks / Timeline
Leads / Opportunities / Pipelines
Communication / Email
    ↓
Domain services + policies + events
    ↓
Timeline Projectors / Repository contracts
    ↓
Memory adapter / Email providers
```

The stable Communication path is:

```text
CommunicationIntent
      ↓ queue
EmailProvider
      ↓ accepted / failed
DeliveryAttempt
      ↓
CommunicationRecord
      ↓ provider callbacks
Delivery history
      ↓
Communication Timeline
```

The `0.4.x` line compatibility-governs the documented `crm.email` facade,
provider-neutral email contracts, normalized lifecycle events, Memory
Communication persistence, and Communication Timeline projection. SMTP is
implemented with the Python standard library; Jinja2 and Resend remain optional
extras.

Communication records are projected directly into Timeline as
`TimelineEntryKind.COMMUNICATION`. PyCRMKit does not create duplicate
`Activity(type="email")` rows for the same communication.

The next roadmap line is **`0.5.0a1 — Event Registry & Serialization`**.
Durable webhook delivery, SQLAlchemy/PostgreSQL, FastAPI, Django, AI and agent
integrations remain later milestones.
