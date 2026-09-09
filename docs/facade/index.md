# CRM Facade

`CRM` is the high-level application surface for PyCRMKit. It coordinates domain services, repositories, Unit of Work boundaries, timeline projections, audit history, and post-commit event dispatch.

```python
from pycrmkit import CRM

crm = CRM.memory()
```

## Namespaces

The stable `0.1` API exposes Contacts, Organizations, Relationships, Tags, Custom Fields, Events, and Audit. The stable `0.2` line adds `crm.activities`, `crm.tasks`, and read-only `crm.timeline`.

The Sales Foundation now adds:

```text
crm.leads          # 0.3.0a1
crm.opportunities  # 0.3.0a2 + stage movement in 0.3.0b1
crm.pipelines      # 0.3.0b1
```

At `0.3.0b1`:

```text
crm.leads.create/qualify/disqualify
crm.opportunities.create/move
crm.pipelines.define/get/list
```

`crm.leads.convert(...)` remains deferred to `0.3.0b2`. Direct Opportunity `mark_won/mark_lost` remain outside the facade: configured terminal stages own those outcomes.

`crm.timeline` remains read-only and Sales events are not projected into Timeline in this beta.

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

Rollback or exit without commit discards domain changes, audit entries, and pending events. Subscriber failures occur after persisted state has committed. Durable retry/outbox semantics remain deferred.
