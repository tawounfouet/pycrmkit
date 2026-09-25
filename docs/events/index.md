# Events Foundation

PyCRMKit's event foundation started in `0.1.0b4`. `0.5.0a1` promotes the
existing event envelope toward a stable integration surface by adding an
explicit registry and deterministic serialization.

## DomainEvent envelope

Every event keeps the existing immutable envelope:

```text
id
type
schema_version
aggregate_type
aggregate_id
occurred_at
actor_id
correlation_id
causation_id
payload
metadata
```

The schema version belongs to the event contract and is independent from the
PyCRMKit package version.

## Event registry

`EventRegistry` registers exact `(event_type, schema_version)` pairs.

```python
from pycrmkit.events import EventRegistry

registry = EventRegistry()
registry.register("contact.created", 1)
registry.register("contact.created", 2)
assert registry.latest("contact.created").schema_version == 2
```

Duplicate type/version registrations raise `DuplicateError`. Unknown
contracts raise `NotFoundError`.

`default_event_registry()` returns a fresh registry containing the 41 stable
v1 event names emitted by the stable 0.1–0.4 facade domains.

## Stable serialization

`EventSerializer` validates every event against its registry before
serialization and after deserialization.

```python
from pycrmkit.events import EventSerializer, default_event_registry

serializer = EventSerializer(default_event_registry())
encoded = serializer.dumps(event)
restored = serializer.loads(encoded)
```

The JSON representation is deterministic: sorted keys, compact separators and
`ensure_ascii=False`. A canonical `contact.created` v1 fixture is maintained
under `tests/fixtures/events/` as a compatibility guard.

Registry enforcement applies to the public serialization/integration boundary;
this alpha does not force arbitrary internal/custom `DomainEvent` creation
through the registry.

## In-process event bus

`InProcessEventBus` remains synchronous and exact-type based. A subscriber
failure after commit does not roll back already committed domain state.

## Deferred

`0.5.0a1` does not add webhook subscriptions, HMAC signing, retry/backoff,
dead-letter state, durable delivery or a transactional outbox. Those belong to
later `0.5.x` milestones.
