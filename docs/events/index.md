# Events Foundation

PyCRMKit's event foundation started in `0.1.0b4`. `0.5.0a1` added an
explicit registry and deterministic serialization; `0.5.0a2` defines
correlation, causation and actor propagation for event-triggered work.

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
`default_event_registry()` returns a fresh registry containing the stable v1
event names emitted by the stable `0.1`–`0.4` domains.

## Stable serialization

`EventSerializer` validates each event against its registry and emits
deterministic JSON using sorted keys, compact separators and
`ensure_ascii=False`.

## Correlation and causation

For work caused by a parent event:

```python
child_crm = crm.with_event(parent_event)
child_crm.tasks.create(title="Follow up")
```

the emitted child event follows this rule:

```text
actor_id       = parent.actor_id
correlation_id = parent.correlation_id
causation_id   = parent.id
```

If the parent has no explicit correlation identifier, its own event ID becomes
the correlation root for descendants.

A multi-hop chain therefore behaves like:

```text
A: correlation=request-1, causation=None
B: correlation=request-1, causation=A
C: correlation=request-1, causation=B
```

`CRMContext.from_event(event)` exposes the same propagation rule independently
of the facade helper.

The serialized public event envelope preserves `actor_id`, `correlation_id`
and `causation_id` unchanged.

## In-process event bus

`InProcessEventBus` remains synchronous and exact-type based. Subscriber
failures after commit do not roll back already committed domain state.

## Deferred

Webhook registration begins in `0.5.0b1`. HMAC signing, retry/backoff,
delivery logging, idempotent external delivery and dead-letter behavior remain
scheduled for `0.5.0b2`.
