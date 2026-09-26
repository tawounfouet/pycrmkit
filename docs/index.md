# PyCRMKit

PyCRMKit is a modular, headless Python CRM domain framework.

The current development version is **`0.5.0b2 — Webhook Delivery Engine`**.
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

`0.5.0a1` established the public event registry and deterministic serialization.
`0.5.0a2` defined causal propagation and `0.5.0b1` added persistent webhook
registrations. `0.5.0b2` now provides explicit signed delivery, retry/backoff,
idempotent delivery state, attempt history and dead-letter outcomes.

Automatic event-bus-to-webhook wiring and complete end-to-end qualification
remain scheduled for `0.5.0rc1`.
SQLAlchemy/PostgreSQL, FastAPI, Django, AI and agent integrations remain later
roadmap lines.
