# Audit Foundation

`0.1.0b4` adds an append-only audit trail for system mutation history.

Audit is intentionally different from the future customer-facing timeline.

```text
Timeline → relationship/customer history
Audit    → system mutation history
```

## AuditEntry

An audit record contains:

```text
id
actor_id
action
entity_type
entity_id
occurred_at
changes
correlation_id
```

Actions use stable dotted names such as `contact.email_changed`.

`changes` is JSON-compatible and deeply immutable. Historical records are append-only; corrections should be represented by new audit entries rather than rewriting existing history.

## Privacy rule

`AuditService` requires callers to provide `changes` explicitly. `record_event()` copies event identity/context but does not copy the event payload automatically.

That deliberate default prevents event payloads containing PII from silently becoming permanent audit history.

## Repository contract

`AuditRepository` defines:

- append;
- get/find;
- entity history;
- actor history;
- correlation history;
- deterministic chronological ordering;
- duplicate-ID rejection.

`MemoryAuditRepository` is the first official implementation and passes the reusable contract suite.

## Transaction semantics

`MemoryUnitOfWork.audit` participates in the same working snapshot as Contacts, Organizations, Relationships, Tags and Custom Fields.

Therefore:

```text
mutation + required audit entry + commit
```

become visible atomically, while rollback removes both.
