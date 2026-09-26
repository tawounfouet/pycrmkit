# PyCRMKit

PyCRMKit is a modular, headless Python CRM domain framework.

The current development version is **`0.5.0a2 — Correlation & Causation`**.
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

The stable Communication path remains:

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
Communication persistence, and Communication Timeline projection.

`0.5.0a1` established the version-aware public event registry and deterministic
serialization. `0.5.0a2` now defines causal propagation: child work inherits
actor identity, preserves a correlation root and points `causation_id` to the
direct parent event.

Webhook registration and delivery remain subsequent `0.5.x` milestones.
SQLAlchemy/PostgreSQL, FastAPI, Django, AI and agent integrations remain later
roadmap lines.
