# Lead Repository Contract

Every `LeadRepository` adapter must implement the same observable semantics.

## Operations

```text
get
find
save
list
```

`get` raises `NotFoundError` when the Lead does not exist; `find` returns `None`. Repository writes do not commit an outer Unit of Work.

## State fidelity

Adapters must preserve all declared Lead states, including `disqualified` and `converted`, even though public conversion is deferred to a later milestone.

## Query semantics

Portable filters cover:

```text
status
contact_id
organization_id
source
```

Results use deterministic ordering:

```text
created_at DESC, id ASC
```

and exact offset pagination.

## Adapter isolation

The official Memory adapter is copy-isolated: mutating an object after `save`, or mutating an object returned by `get/find/list`, must not mutate persisted repository state without another explicit `save`.

The reusable contract suite is executed against `MemoryLeadRepository` and will be reused by future persistent adapters.
