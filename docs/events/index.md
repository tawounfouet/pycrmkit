# Events Foundation

`0.1.0b4` introduces the first CRM domain-event surface.

## DomainEvent envelope

Every event uses the same immutable envelope:

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

Public event names are normalized dotted identifiers such as:

```text
contact.created
organization.updated
relationship.removed
```

`schema_version` belongs to the event contract and is independent from the PyCRMKit package version.

## JSON contract

`payload` and `metadata` must contain JSON-compatible values. They are recursively frozen inside the event so a published occurrence cannot be mutated casually after creation.

`DomainEvent.to_dict()` exposes the stable JSON-compatible envelope used by compatibility fixtures. `DomainEvent.from_dict()` reconstructs that envelope without introducing an event registry yet.

## In-process event bus

`InProcessEventBus` supports exact event-type subscriptions:

```python
bus.subscribe("contact.created", handler)

@bus.on("contact.updated")
def on_contact_updated(event):
    ...
```

Handlers run synchronously in subscription order. Duplicate registration of the same handler/event pair is idempotent. Handler exceptions propagate to the publisher.

No distributed transport, webhook delivery, retry, dead-letter queue, transactional outbox, or durable event store is part of `0.1.0b4`.

## Transaction boundary

`MemoryUnitOfWork.add_event()` stages events while the transaction is active:

```text
domain mutation
    +
staged DomainEvent
    ↓
commit state
    ↓
dispatch staged events
```

Rollback, exceptions before commit, and context exit without commit discard pending events.

A subscriber failure after commit does **not** roll back state that was already committed. Durable delivery/retry semantics require the later outbox/webhook milestones.
