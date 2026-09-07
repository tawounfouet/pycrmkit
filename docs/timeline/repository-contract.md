# Timeline Repository Contract

`TimelineRepository` is the backend-neutral persistence contract for immutable timeline projections.

Required operations:

```text
get(entry_id)
find(entry_id)
append(entry)
list_for_reference(reference, page, ...filters)
```

## Append / replay semantics

`append` is idempotent when the existing entry with the same ID has identical content. A conflicting entry with the same ID must be rejected. This makes Domain Event replay safe while detecting projector corruption or incompatible projection logic.

## Query semantics

`list_for_reference` returns exact offset pagination and deterministic ordering:

```text
occurred_at DESC
kind ASC
id ASC
```

Backends must support filtering by:

- related `EntityReference`;
- optional `TimelineEntryKind`;
- optional `EventType`;
- optional half-open occurrence interval `[occurred_from, occurred_until)`.

The official `MemoryTimelineRepository` is the reference adapter for `0.2.0b1`. Future SQLAlchemy and Django adapters must satisfy the same behavior contract.
