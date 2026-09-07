# Task Repository Contract

Every Task persistence adapter must satisfy the reusable `TaskRepositoryContract`.

Required operations:

```text
get
find
save
list
```

Contractual behavior includes:

- `get()` raises `NotFoundError` and `find()` returns `None` for missing IDs;
- `save()` replaces current aggregate state without committing an outer transaction;
- copy-isolation for the official Memory adapter;
- exact offset pagination;
- deterministic `due_at ASC (undated last), created_at DESC, id ASC` ordering;
- filtering by lifecycle status, priority, assignee, owner and related CRM references;
- half-open due-date window semantics;
- overdue queries that exclude terminal tasks.

Task lifecycle transitions are aggregate/service responsibilities and must not be implemented differently by storage adapters.
