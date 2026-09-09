# Opportunity Repository Contract

`OpportunityRepository` is backend-neutral and participates in the shared Unit of Work.

Required operations:

```text
get
find
save
list
```

## Persistence fidelity

Adapters must preserve:

```text
name
contact_id
organization_id
pipeline_id
stage_id
estimated_value + currency
probability
expected_close_date
owner_id
status
created_at / updated_at
```

Money values must preserve `Decimal` precision and explicit currency semantics. `won`, `lost`, and `cancelled` terminal states must round-trip unchanged.

## Listing

The portable `OpportunityQuery` supports filters for:

```text
status
contact_id
organization_id
pipeline_id
stage_id
owner_id
currency
expected_close_date
```

Ordering is deterministic:

```text
created_at DESC
id ASC
```

Pagination uses exact `OffsetPageRequest` / `Page` semantics.

## Error and isolation semantics

- `get` raises `NotFoundError(code="opportunity.not_found")` when missing.
- `find` returns `None` when missing.
- Memory persistence is copy-on-save and copy-on-read.
- repository writes do not commit the outer Unit of Work.

## Pipeline boundary

`0.3.0a2` persists `pipeline_id` and `stage_id` as opaque references only. Stage existence, ordering, transition policies, terminal stages, probability defaults, and stage-entry timestamps are introduced in `0.3.0b1`.
