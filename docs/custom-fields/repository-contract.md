# Custom Field Repository Contract

`CustomFieldRepository` stores two related concerns:

1. immutable-in-history definition revisions;
2. the current value for each definition/entity pair.

Required semantics include:

- definition keys are unique across stable definition identities;
- schema revisions are append-only and sequential;
- `get_definition(id)` returns the latest revision;
- `get_definition(id, version)` retrieves a specific historical revision;
- searches operate on latest revisions only;
- current values are unique per `(definition_id, entity_reference)` pair;
- value removal is idempotent;
- value pagination is deterministic.

The first-party contract suite is `tests/contracts/custom_fields_repository.py`.
