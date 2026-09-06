# Relationship Repository Contract

Every official Relationship persistence adapter must implement the same observable contract.

```text
get(id)       → Relationship or NotFoundError
find(id)      → Relationship or None
save(entity)  → persist current state without committing an outer UoW
end(id, at)   → idempotently end the relationship
search(...)   → exact Page[Relationship]
```

Required semantics include:

- deterministic ordering by `created_at`, then `id`;
- exact offset pagination;
- source and target filtering;
- participant filtering regardless of direction;
- relationship-type and primary-link filtering;
- ended relationships excluded by default;
- explicit `include_ended=True` history access;
- historical `active_at` evaluation using `[valid_from, valid_until)`;
- backend-specific exceptions mapped to PyCRMKit errors.

The reusable suite in `tests/contracts/relationships_repository.py` is the normative executable contract.
