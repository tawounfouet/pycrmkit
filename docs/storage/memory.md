# Memory Adapter

The official Memory adapter is the reference in-process persistence implementation for tests, examples, CLI prototypes, tutorials, and local development.

It is a conformant adapter, not a mock. Repository contracts are executed against the actual Memory repositories.

## Public components

```python
from pycrmkit.storage.memory import (
    MemoryActivityRepository,
    MemoryAuditRepository,
    MemoryContactRepository,
    MemoryCustomFieldRepository,
    MemoryOrganizationRepository,
    MemoryRelationshipRepository,
    MemoryStore,
    MemoryTagRepository,
    MemoryTaskRepository,
    MemoryTimelineRepository,
    MemoryUnitOfWork,
)
```

## Copy / immutability semantics

Mutable aggregates use copy-on-save and copy-on-read semantics. Immutable Audit and Timeline entries can safely be shared across transaction snapshots.

## Unit of Work

`MemoryStore` owns committed state. `MemoryUnitOfWork` creates a private transaction snapshot shared by all repositories:

```text
MemoryUnitOfWork
└── transaction snapshot
    ├── activities
    ├── contacts
    ├── organizations
    ├── relationships
    ├── tasks
    ├── timeline
    ├── tags
    ├── custom_fields
    └── audit
```

Leaving the context without `commit()` rolls back staged changes. Exceptions and explicit `rollback()` also discard uncommitted work.

## Timeline projection

`0.2.0b1` stores immutable `TimelineEntry` values in the same transaction snapshot as source domain mutations. The facade builds a `DomainEvent`, runs the Timeline projector against the active UoW, then commits domain state, audit, and timeline together. Public EventBus subscribers are invoked only after the commit succeeds.

This ordering deliberately avoids opening a nested `MemoryUnitOfWork`; one `MemoryStore` permits only one active UoW at a time.

## Contract qualification

The official Memory repositories execute reusable suites for Contacts, Organizations, Relationships, Tags, Custom Fields, Audit, Activities, Tasks, and Timeline.

Timeline contract requirements include idempotent identical replay, conflicting replay rejection, exact pagination, deterministic reverse chronology, and reference/kind/event/time filters.

## Boundaries

The Memory adapter does not claim production concurrency semantics and does not provide SQLAlchemy/PostgreSQL persistence, migrations, durable outbox/retry, or distributed event transport. Those remain dedicated roadmap milestones.
