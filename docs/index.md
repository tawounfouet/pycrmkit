# PyCRMKit

PyCRMKit is a modular, headless Python CRM domain framework.

The current stable version is **`0.8.0 — Django Integration Stable`**.  
The latest data-operations prerelease is **`0.9.0a1 — External Identities`**.
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

`0.7.0a1` introduced the optional Pydantic transport schemas, request-context
dependency bridge, pagination conversion and typed error payload foundation.

`0.7.0b1` adds reusable facade-backed routers for Contacts, Organizations,
Relationships, Activities, Tasks, Leads, Opportunities and Timeline. The core
remains FastAPI/Pydantic-independent, and routers never access ORM models,
Sessions or repositories directly.

`0.7.0b2` completes the beta API contract with stable domain-error → HTTP
status mapping, normalized request-validation errors, application-level
exception handlers and selective OpenAPI response examples.

`0.7.0rc1` qualifies the complete FastAPI integration against PostgreSQL 17.
The reference application under `examples/fastapi_postgres/` uses packaged
Alembic migrations, `SQLAlchemyUnitOfWork`, the reusable router/error layer,
real API E2E and a clean installed-wheel smoke.

`0.7.0` promotes the release candidate to stable without adding new FastAPI
feature scope. The transport schemas, dependency bridge, routers, error mapping,
OpenAPI contract, PostgreSQL reference application and clean-wheel API
qualification now form one compatibility-governed integration line.

`0.8.0a1` started the optional Django adapter with `PyCRMKitDjangoConfig`, distinct ORM persistence representations and contract-backed repositories for Contacts, Organizations and Relationships.

`0.8.0b1` adds the adapter-specific Django migration lifecycle, admin helpers and an explicit `DjangoTransactionBridge`. The bridge preserves explicit commit/rollback semantics and defers staged domain events until the actual outer Django transaction commits when it joins an ambient `transaction.atomic()` block. It is intentionally bounded to the Django repositories currently implemented; full Django application qualification remains scheduled for the release candidate.

`0.8.0b2` adds an optional Django REST Framework bridge. Its serializers preserve PyCRMKit domain/value-object semantics, its ViewSets call the public `CRM` facade rather than ORM models, request actor/correlation headers flow into the facade context, and PyCRMKit errors retain stable machine-readable codes over HTTP. The plain `django` extra remains DRF-free.

`0.8.0rc1` qualifies the current Django integration as a complete release-candidate path. The reference application under `examples/django/` mounts the PyCRMKit Django app, admin and DRF router, applies packaged Django migrations to PostgreSQL 17, persists Contact → Organization → Relationship through the public `CRM` facade, and verifies the same records from a fresh Django process. The same journey is repeated from a clean installed wheel.

`0.8.0` promotes the fully qualified release candidate to stable without adding new Django feature scope. The Django app bootstrap, persistence representations, Contact/Organization/Relationship repositories, migration `0001_initial`, transaction bridge, admin helpers, optional DRF transport, PostgreSQL 17 reference application and clean-wheel E2E now form one compatibility-governed integration line.

`0.9.0a1` introduces provider-neutral external identities. A normalized `(system, external_id)` pair maps to one PyCRMKit entity, same-owner attach is idempotent, conflicting ownership is explicit, and the repository contract is qualified across Memory, SQLAlchemy/PostgreSQL and Django. SQLAlchemy advances to Alembic `0003`; Django advances to `0002_external_identity`.

The next roadmap milestone is **`0.9.0a2 — Import Framework`**.
