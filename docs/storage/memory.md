# Memory Adapter

`0.1.0b3` introduces the first official PyCRMKit persistence adapter.

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

`MemoryStore` owns committed state. `MemoryUnitOfWork` creates a private transaction snapshot shared by all five repositories.

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
    └── custom_fields
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
events / audit
CRM facade
```

Those remain separate roadmap milestones.
