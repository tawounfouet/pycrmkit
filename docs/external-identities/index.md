# External Identities

External identities map records owned by another system to stable PyCRMKit
entities without polluting Contact or Organization domain models with
provider-specific IDs.

```python
contact = crm.contacts.create(
    first_name="Ada",
    last_name="Lovelace",
)

identity = crm.external_identities.attach(
    contact,
    system="hubspot",
    external_id="123456",
    metadata={"portal": "eu"},
)
```

## Domain model

```text
ExternalIdentity
├── id
├── created_at
├── updated_at
├── system
├── external_id
├── entity_type
├── entity_id
└── metadata
```

The system key is normalized to a stable lowercase identifier. The external ID
is Unicode-normalized and trimmed, but its case is preserved because upstream
identifier semantics are provider-owned.

## Ownership invariant

PyCRMKit `0.9.0a1` defines one external record as:

```text
(system, external_id)
```

That pair may belong to exactly one PyCRMKit entity.

Attaching the same pair to the same entity is idempotent. Attaching it to a
different entity raises:

```text
external_identity.owner.conflict
```

This invariant is reinforced by Memory, SQLAlchemy/PostgreSQL and Django
repository adapters.

## Resolve

```python
identity = crm.external_identities.resolve(
    "hubspot",
    "123456",
)
```

Absence raises `external_identity.not_found`.

## List for an entity

```python
page = crm.external_identities.list_for_entity(contact)

for identity in page.items:
    print(identity.system, identity.external_id)
```

Listings use the normal `OffsetPageRequest` contract and deterministic ordering.

## Detach

```python
removed = crm.external_identities.detach(
    "hubspot",
    "123456",
)
```

Detach is idempotent:

```text
first detach   → True
later detach   → False
```

## Accepted targets

The high-level facade accepts Contact and Organization entities directly, matching
the primary CRM use case:

```python
crm.external_identities.attach(contact, ...)
crm.external_identities.attach(organization, ...)
```

For other PyCRMKit entity kinds, pass an explicit `EntityReference`:

```python
from pycrmkit.core.references import EntityReference

crm.external_identities.attach(
    EntityReference("lead", lead.id),
    system="legacy_crm",
    external_id="lead-42",
)
```

## Events

First-time attachment and successful detach emit:

```text
external_identity.attached
external_identity.detached
```

Idempotent attachment retries do not emit duplicate attachment events.

## Persistence

The alpha is qualified across:

```text
Memory
SQLAlchemy / PostgreSQL
Django ORM / PostgreSQL
```

SQLAlchemy databases advance through Alembic revision `0003`.

Django applications advance through migration
`pycrmkit_crm.0002_external_identity`.

Migrations remain explicit deployment operations.

## Deferred

`0.9.0a1` does not implement the import pipeline. That begins with
**`0.9.0a2 — Import Framework`**.
