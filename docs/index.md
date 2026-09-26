# PyCRMKit

PyCRMKit is a modular, headless Python CRM domain framework.

The current stable version is **`0.5.0 — Eventing & Webhooks Stable`**.
The latest persistence prerelease is **`0.6.0b1 — Unit of Work & Transactions`**.
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

`0.5.0` promotes the qualified Eventing & Webhooks line to stable. The stable
path now covers registry/versioned serialization, actor/correlation/causation,
persistent subscriptions, HMAC signing, retry/backoff, idempotent delivery,
dead-letter history, and automatic post-commit EventBus bridging.

`0.6.0b1` now provides the SQLAlchemy Unit of Work: all repositories in one
transaction share a Session, commit/rollback ownership is centralized, and
domain events are released only after a successful database commit.

The next roadmap milestone is **`0.6.0b2 — PostgreSQL`**, followed by Alembic
in `0.6.0b3` and full persistence qualification in `0.6.0rc1`. FastAPI,
Django, data operations, AI and agent integrations remain later roadmap lines.
