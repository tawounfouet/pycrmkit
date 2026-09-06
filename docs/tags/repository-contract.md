# Tag Repository Contract

Official adapters implement `TagRepository` with these observable semantics:

- `get()` raises `NotFoundError` when absent;
- `find()` returns `None` when absent;
- normalized tag names are unique;
- search and pagination are deterministic;
- assigning the same tag/entity pair twice raises `DuplicateError`;
- assignment removal is idempotent;
- `list_for_entity()` returns only currently assigned tags.

The reusable contract suite lives in `tests/contracts/tags_repository.py`.
