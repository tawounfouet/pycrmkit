# CRM Facade

`CRM` is the high-level application surface for PyCRMKit. It coordinates domain
services, repositories, Unit of Work boundaries, timeline projections, audit
history, and post-commit event dispatch.

```python
from pycrmkit import CRM

crm = CRM.memory()
```

## Namespaces

The stable `0.1` API exposes Contacts, Organizations, Relationships, Tags,
Custom Fields, Events, and Audit. The stable `0.2` line adds `crm.activities`,
`crm.tasks`, and read-only `crm.timeline`.

The stable `0.3.x` Sales surface is:

```text
crm.leads.create/qualify/disqualify/convert
crm.opportunities.create/move
crm.pipelines.define/get/list
```

Direct Opportunity `mark_won`, `mark_lost`, `get`, and `list` remain outside the
facade: configured terminal Stages own public won/lost outcomes. Lead
`get/list` likewise remain service/repository capabilities rather than facade
methods.

`crm.timeline` remains read-only and Sales events are not projected into
Timeline in `0.3.x`.

## Lead conversion boundary

`crm.leads.convert(...)` coordinates one cross-aggregate Unit of Work. It
creates the Opportunity and marks the qualified Lead converted atomically. A
retry with the same idempotency key and equivalent request returns the already
created Opportunity without duplicating events or audit entries.

## Pipeline boundary

`crm.opportunities.move(...)` resolves the persisted Pipeline definition,
rejects undeclared transitions, applies target-Stage probability defaults and
maps terminal Stages to won/lost/cancelled Opportunity status.

## Transaction boundary

A mutation follows the shared facade transaction pattern:

```text
open UnitOfWork
    ↓
domain service mutation / policy validation
    ↓
create DomainEvent envelope
    ↓
stage AuditEntry (when enabled)
    ↓
stage DomainEvent for external subscribers (when enabled)
    ↓
commit domain + audit
    ↓
dispatch DomainEvent synchronously
```

Rollback or exit without commit discards domain changes, audit entries, and
pending events. Subscriber failures occur after persisted state has committed.
Durable retry/outbox semantics remain deferred.
