# PyCRMKit

PyCRMKit is a modular, headless Python CRM domain framework.

The current development version is **`0.5.0a1 — Event Registry & Serialization`**.
The stable `0.1`–`0.4` CRM Core, Activity/Timeline, Sales and Communication
contracts remain compatibility-frozen:

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

`0.5.0a1` adds a version-aware registry for public DomainEvent contracts and
deterministic JSON serialization suitable for later signing and delivery.
Correlation/causation integration and webhooks remain subsequent `0.5.x`
milestones. SQLAlchemy/PostgreSQL, FastAPI, Django, AI and agent integrations
remain later roadmap lines.
