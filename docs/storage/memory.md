# Memory Adapter

`0.1.0b3` introduced the first official PyCRMKit persistence adapter. `0.1.0b4` extends the same transaction snapshot with append-only audit entries and post-commit event staging.

The Memory adapter is intended for:

```text
tests
examples
CLI prototypes
tutorials
embedded/local development
```

It is a conformant adapter, not a mock. The same repository contracts used to define Contact, Organization, Relationship, Tag, and Custom Field persistence are executed against the real Memory repositories.

## Public components

```python
from pycrmkit.storage.memory import (
    MemoryAuditRepository,
    MemoryContactRepository,
    MemoryCustomFieldRepository,
    MemoryOrganizationRepository,
    MemoryRelationshipRepository,
    MemoryStore,
    MemoryTagRepository,
    MemoryUnitOfWork,
)
```

## Copy isolation

Repositories use copy-on-save and copy-on-read semantics.

```python
repository.save(contact)

loaded = repository.get(contact.id)
loaded.source = "changed-without-save"

assert repository.get(contact.id).source != "changed-without-save"
```

This deliberately mirrors persistent-database semantics: mutating a Python object does not change persisted state until `save()` is called.

## Unit of Work

`MemoryStore` owns committed state. `MemoryUnitOfWork` creates a private transaction snapshot shared by all transactional repositories.

```python
store = MemoryStore()

with MemoryUnitOfWork(store) as uow:
    uow.contacts.save(contact)
    uow.organizations.save(organization)
    uow.commit()
```

A later transaction sees both committed changes:

```python
with MemoryUnitOfWork(store) as uow:
    contact = uow.contacts.get(contact_id)
    organization = uow.organizations.get(organization_id)
```

## Explicit commit

Leaving a UoW without `commit()` rolls back staged changes.

```python
with MemoryUnitOfWork(store) as uow:
    uow.contacts.save(contact)
    # no commit

# contact was not persisted
```

Exceptions also roll back staged state. `rollback()` may be called explicitly to discard changes while keeping the current context usable.

## Transaction boundary

All repositories inside one `MemoryUnitOfWork` share the same transaction snapshot:

```text
MemoryUnitOfWork
└── transaction snapshot
    ├── contacts
    ├── organizations
    ├── relationships
    ├── tags
    ├── custom_fields
    └── audit
```

`commit()` replaces the committed `MemoryStore` state atomically with a deep copy of that snapshot.

## Nested/concurrent transactions

A single `MemoryStore` permits one active `MemoryUnitOfWork` at a time. Nested or concurrent UoWs using the same store fail explicitly with `InvalidStateError`.

This is intentional for the initial in-process adapter. The Memory adapter does not claim production concurrency semantics.

## Contract qualification

The official Memory repositories execute the reusable suites for:

```text
ContactRepository
OrganizationRepository
RelationshipRepository
TagRepository
CustomFieldRepository
AuditRepository
```

Additional adapter tests verify copy isolation and UoW transaction behavior.

## Boundaries

This milestone does not introduce:

```text
SQLAlchemy
PostgreSQL
Django ORM
optimistic database locking
persistent migrations
durable outbox / distributed event transport
CRM facade
```

Those remain separate roadmap milestones.


## Events and audit

`MemoryUnitOfWork.audit` is transaction-bound like the other repositories. Audit entries are therefore committed or rolled back with the same snapshot.

`MemoryUnitOfWork.add_event()` stages immutable `DomainEvent` objects. They are dispatched through the configured `EventPublisher` only after `MemoryStore` accepts the committed state. Pending events are discarded on rollback or uncommitted exit.

This adapter does not provide durable retry/outbox semantics.
