# CRM Facade

`CRM` is the high-level application surface for PyCRMKit. It coordinates domain services, repositories, Unit of Work boundaries, audit history, and post-commit event dispatch.

```python
from pycrmkit import CRM

crm = CRM.memory()
```

## Namespaces

The stable `0.1` API exposes:

```text
crm.contacts
crm.organizations
crm.relationships
crm.tags
crm.custom_fields
crm.events
crm.audit
```

Mutating domain namespaces use one Unit of Work per facade call. Read methods use the same repository contracts but do not commit mutations.

## Transaction boundary

A facade mutation follows this sequence:

```text
open UnitOfWork
    ↓
domain service mutation
    ↓
stage AuditEntry in same transaction
    ↓
stage DomainEvent
    ↓
commit persisted state + audit
    ↓
dispatch DomainEvent synchronously
```

Rollback or exit without commit discards both domain changes and staged audit/event work.

Subscriber failures occur after persisted state has committed and therefore do not perform a fake rollback. Durable retry/outbox semantics are intentionally deferred.

## Context

```python
scoped = crm.with_context(
    actor_id="user-42",
    correlation_id="corr-42",
)
```

`with_context()` returns a lightweight facade view sharing the same storage and event bus. `causation_id` can also be supplied for event chains.

## Configuration

```python
from pycrmkit import CRM, CRMConfig

crm = CRM.memory(
    config=CRMConfig(
        events_enabled=True,
        audit_enabled=True,
        default_actor_id="system",
    )
)
```

Events and audit can be disabled independently.
