# Timeline

PyCRMKit `0.2.0b1` introduces a customer-facing, read-oriented relationship history.

Timeline is **not** Audit and is **not** a new aggregate source of truth:

```text
Domain mutation
    ↓
Domain Event
    ↓
Timeline Projector
    ↓
Immutable TimelineEntry
    ↓
TimelineRepository
```

Projection is staged inside the same Unit of Work as the source mutation, so domain state and timeline history commit atomically. External in-process subscribers still receive the DomainEvent after the commit succeeds.

## Projected events

The beta intentionally projects only meaningful relationship-history events:

```text
activity.created

task.created
task.started
task.completed
task.cancelled
task.reopened
```

Generic `activity.updated` and `task.updated` mutations remain available in Audit/Events but are not timeline entries, avoiding technical edit noise.

## Entry model

A `TimelineEntry` contains:

- a typed `TimelineEntryId` derived from the source Event ID;
- `kind` (`activity` or `task`);
- source `event_type` and `source_event_id`;
- source aggregate `EntityReference`;
- business `occurred_at` timestamp;
- title and optional summary;
- related CRM references (Contacts, Organizations, future entity kinds);
- optional actor/correlation context;
- JSON-compatible projection metadata.

Using the source Event ID as the Timeline entry ID makes replay idempotent.

## Querying

```python
history = crm.timeline.for_contact(contact.id)
history = crm.timeline.for_organization(organization.id)
```

Optional filters include Timeline kind, event type, occurrence interval, and standard `OffsetPageRequest` pagination.

Ordering is always:

```text
occurred_at DESC
kind ASC
id ASC
```

Activity projections use the Activity's business `occurred_at`. Task lifecycle entries use their relevant lifecycle timestamp.
