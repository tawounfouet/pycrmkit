# CRM Facade

`CRM` is the high-level application surface for PyCRMKit. It coordinates domain services, repositories, Unit of Work boundaries, timeline projections, audit history, and post-commit event dispatch.

```python
from pycrmkit import CRM

crm = CRM.memory()
```

## Namespaces

The stable `0.1` API exposes Contacts, Organizations, Relationships, Tags, Custom Fields, Events, and Audit. The additive `0.2` line adds:

```text
crm.activities
crm.tasks
crm.timeline
```

`crm.timeline` is read-only. It exposes customer/relationship history projected from meaningful Activity/Task domain events.

## Transaction boundary

A Timeline-producing mutation follows this sequence:

```text
open UnitOfWork
    ↓
domain service mutation
    ↓
create DomainEvent envelope
    ↓
project TimelineEntry in same transaction (when supported)
    ↓
stage AuditEntry (when enabled)
    ↓
stage DomainEvent for external subscribers (when enabled)
    ↓
commit domain + timeline + audit
    ↓
dispatch DomainEvent synchronously
```

Rollback or exit without commit discards domain changes, timeline projections, audit entries, and pending events.

Subscriber failures occur after persisted state has committed and therefore do not perform a fake rollback. Durable retry/outbox semantics are intentionally deferred.

## Context

```python
scoped = crm.with_context(
    actor_id="user-42",
    correlation_id="corr-42",
)
```

Projected Timeline entries preserve actor/correlation context from the source event where provided.

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

Events and Audit can be disabled independently. Timeline projection remains active for supported Activity/Task history events because it is a CRM read model, not an external event-delivery feature.
