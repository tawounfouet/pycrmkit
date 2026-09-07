# Activity Repository Contract

Every `ActivityRepository` adapter must satisfy the same behavior.

Required operations:

```text
get
find
save
list
```

Semantics:

- `get(id)` returns exactly one `Activity` or raises `NotFoundError`.
- `find(id)` is explicitly nullable.
- `save(activity)` persists current state without committing an outer Unit of Work.
- `list(query, page)` returns exact totals and deterministic pagination.
- ordering is `occurred_at DESC, id ASC`.
- participant filters match `ActivityParticipant.reference`.
- generic reference filters match `Activity.references`.
- time windows use `[occurred_from, occurred_until)`.
- adapters must isolate persisted state from unsaved Python-object mutation.

The official `MemoryActivityRepository` is the first adapter executing this shared contract suite.
