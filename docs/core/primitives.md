# Core Primitives

Version `0.1.0a1` introduces the foundational primitives shared by future PyCRMKit domain modules.

## Typed UUID identifiers

```python
from pycrmkit.core import EntityId, UUID4Factory

factory = UUID4Factory()
entity_id = factory.new(EntityId)
```

Domain-specific IDs can subclass `UUIDId` / `EntityId` while keeping the same factory contract. IDs are immutable and backed by `uuid.UUID`.

## Time

```python
from datetime import UTC, datetime, timedelta
from pycrmkit.core import FixedClock, SystemClock

clock = SystemClock()
now = clock.now()  # timezone-aware UTC

fixed = FixedClock(datetime(2026, 9, 6, 10, 0, tzinfo=UTC))
fixed.advance(timedelta(minutes=30))
```

Naive datetimes are rejected. `FixedClock` exists for deterministic tests and controlled simulations.

## Entities

`Entity` defines identity semantics: two entities are equal when they have the same concrete type and domain ID. `TimestampedEntity` adds `created_at` / `updated_at`, normalizes both to UTC, and rejects an update timestamp older than creation.

## Value objects

`ValueObject` is the immutable marker/convention for value-semantic domain objects. Concrete value objects should remain frozen dataclasses.

## Errors

Public errors live in `pycrmkit.exceptions` and expose a machine-readable `code`, a human-readable message, and structured context.

```python
from pycrmkit.exceptions import NotFoundError

raise NotFoundError(
    "Contact not found",
    code="contact.not_found",
    context={"contact_id": "..."},
)
```

The current hierarchy includes validation, not-found, conflict/duplicate, invalid-state, repository, and integration errors.
