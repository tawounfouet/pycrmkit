# PyCRMKit

PyCRMKit is a modular, headless Python CRM domain framework.

The current stable version is **`0.6.0 — Persistence Foundation Stable`**.
The stable `0.1`–`0.5` CRM Core, Activity/Timeline, Sales, Communication,
and Eventing/Webhooks contracts are compatibility-governed:

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
Memory / SQLAlchemy + PostgreSQL / Email providers
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

`0.5.0` promotes the qualified Eventing & Webhooks line to stable. The stable
path now covers registry/versioned serialization, actor/correlation/causation,
persistent subscriptions, HMAC signing, retry/backoff, idempotent delivery,
dead-letter history, and automatic post-commit EventBus bridging.

`0.6.0rc1` now qualifies the complete persistence foundation as one system:
the stable `0.1`–`0.5` facade runs on PostgreSQL, repository contracts are
replayed on the production-reference backend, migrations advance to revision
`0002`, transaction rollback is qualified, and the installed wheel applies its
packaged migrations before a PostgreSQL smoke test.

`0.6.0` promotes the fully qualified persistence release candidate to stable
without adding new persistence scope. SQLAlchemy repositories, Unit-of-Work
transactions, PostgreSQL and Alembic revision `0002` now form the stable
production-reference persistence baseline.

The next roadmap milestone is **`0.7.0 — FastAPI Integration`**. Django, data
operations, AI and agent integrations remain later roadmap lines.
