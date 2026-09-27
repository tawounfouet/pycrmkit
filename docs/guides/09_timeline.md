# 09 - Timeline

> Applies to PyCRMKit 1.0.x. Baseline: 1.0.0.

Timeline closes LEVEL 2 - Customer Activity.

Activities tell you what happened. Tasks tell you what needs to happen. Timeline
turns meaningful domain events into an ordered, customer-facing history.

~~~text
Activity / Task / Communication mutation
                |
                v
           Domain Event
                |
                v
        Timeline Projector
                |
                v
       immutable TimelineEntry
                |
                v
        TimelineRepository
                |
                v
 Contact / Organization history
~~~

Timeline is a read model. It is not the source of truth for Activities, Tasks or
Communications.

## What you will build

By the end of this chapter you will understand:

~~~text
TimelineEntry
+-- TimelineEntryId
+-- kind
+-- event_type
+-- source_event_id
+-- source entity
+-- occurred_at
+-- title
+-- summary
+-- related references
+-- actor_id
+-- correlation_id
+-- metadata
~~~

and the stable read surface:

~~~text
crm.timeline.get(...)
crm.timeline.for_contact(...)
crm.timeline.for_organization(...)
~~~

There is deliberately no create/update/delete Timeline facade.

## 1. Timeline is a projection

A Timeline entry is derived from another domain event.

For example:

~~~text
Activity created
      |
      v
activity.created
      |
      v
TimelineEntry(kind=activity)
~~~

or:

~~~text
Task completed
      |
      v
task.completed
      |
      v
TimelineEntry(kind=task)
~~~

The source aggregate remains the Activity or Task.

Timeline provides a convenient customer-history view over those facts.

## 2. Timeline is not Audit

Timeline and Audit answer different questions.

~~~text
Timeline
What meaningful relationship-history events should a user see?

Audit
What mutation occurred, by whom, and in which operational context?
~~~

For example, generic technical corrections such as:

~~~text
activity.updated
task.updated
~~~

are available to Event/Audit infrastructure but are intentionally not projected
as Timeline entries.

This prevents a customer timeline from becoming noisy with every technical edit.

## 3. Timeline is read-only

Applications do not manually append Timeline entries through CRM facade code.

Correct:

~~~python
activity = crm.activities.log(
    type="meeting",
    subject="Quarterly review",
)

history = crm.timeline.for_contact(contact.id)
~~~

The source mutation creates the relevant Domain Event, and the projector stages
the Timeline entry automatically when that event type is supported.

## 4. Projected Activity events

The stable Activity projection includes:

~~~text
activity.created
~~~

It deliberately does not project:

~~~text
activity.updated
~~~

A correction to an Activity changes the source aggregate and remains observable
through Events/Audit, but does not inject technical edit noise into customer
history.

## 5. Projected Task events

The stable Task projection includes meaningful lifecycle events:

~~~text
task.created
task.started
task.completed
task.cancelled
task.reopened
~~~

It deliberately does not project:

~~~text
task.updated
~~~

Changing priority or assignee is not treated as a new customer-history
occurrence by the Timeline projector.

## 6. Communication projection in V1

The current V1 projector also supports selected email lifecycle events:

~~~text
email.queued
email.sent
email.delivered
email.opened
email.clicked
email.bounced
email.failed
~~~

These use:

~~~text
TimelineEntryKind.COMMUNICATION
~~~

The deeper communication model is introduced later in the Zero-to-Hero path.
For LEVEL 2, Activities and Tasks remain the primary learning examples.

## 7. TimelineEntryKind

The stable enum currently contains:

~~~text
ACTIVITY
TASK
COMMUNICATION
~~~

Example:

~~~python
from pycrmkit.timeline import TimelineEntryKind

assert TimelineEntryKind.ACTIVITY.value == "activity"
assert TimelineEntryKind.TASK.value == "task"
assert TimelineEntryKind.COMMUNICATION.value == "communication"
~~~

## 8. Entry identity comes from the source Event

TimelineEntryId is derived from the source EventId.

The invariant is:

~~~text
TimelineEntry.id.value
==
TimelineEntry.source_event_id.value
~~~

Why?

Because a Domain Event already uniquely identifies the occurrence being
projected.

Using the same UUID value gives replay-safe identity.

## 9. ID mismatch is rejected

A TimelineEntry cannot claim to represent one source event while carrying a
different ID.

The constructor rejects:

~~~text
TimelineEntryId != source EventId
~~~

with:

~~~text
ValidationError
code = timeline.id.event_mismatch
~~~

This protects deterministic replay semantics.

## 10. TimelineEntry is immutable

TimelineEntry is a frozen dataclass.

Once projected, it is not edited in place.

That model matches the meaning of an occurrence:

~~~text
Something happened
      |
      v
immutable historical projection
~~~

If the source domain changes later, a different meaningful event may produce a
new entry. Existing projected history is not rewritten casually.

## 11. Source entity vs related references

TimelineEntry contains two different concepts:

~~~text
entity
= source aggregate represented by the entry

references
= CRM entities whose history this occurrence belongs to
~~~

For an Activity:

~~~text
entity
= activity:<ActivityId>

references
= participants + Activity.references
~~~

For a Task:

~~~text
entity
= task:<TaskId>

references
= Task.references
~~~

This is how one source occurrence can appear in several customer histories.

## 12. Multi-entity projection

Suppose a Task references both a Contact and an Organization:

~~~python
task = crm.tasks.create(
    title="Prepare renewal",
    references=(
        contact_ref,
        organization_ref,
    ),
)
~~~

The Task has one Timeline entry per projected Domain Event, but that entry
contains both references.

Therefore:

~~~python
contact_history = crm.timeline.for_contact(contact.id)
organization_history = crm.timeline.for_organization(organization.id)
~~~

can expose the same entry.

Timeline does not duplicate the historical occurrence merely because it belongs
to two entity histories.

## 13. Activity projection merges participants and references

For activity.created, projected references are built from:

~~~text
ActivityParticipant.reference
+
Activity.references
~~~

then deduplicated while preserving order.

So an interaction participant automatically becomes part of the Activity
timeline association even if it was not separately listed in
Activity.references.

## 14. Duplicate Timeline references are normalized away

TimelineEntry itself also deduplicates references.

Conceptually:

~~~text
(contact_ref, contact_ref, organization_ref)
        |
        v
(contact_ref, organization_ref)
~~~

This is normalization rather than a validation failure.

That differs from source Activity/Task aggregate rules, where duplicate
references may be rejected before projection.

## 15. Activity occurred_at uses business occurrence time

For Activity projection:

~~~text
TimelineEntry.occurred_at
=
Activity.occurred_at
~~~

not:

~~~text
Activity.created_at
DomainEvent.occurred_at
~~~

This preserves imported historical interaction chronology.

Example:

~~~text
Activity happened: 2024
Imported into PyCRMKit: 2026
Timeline position: 2024
~~~

## 16. Task occurred_at uses lifecycle time

Task projection chooses the business timestamp appropriate to the event.

~~~text
task.created   -> Task.created_at
task.started   -> Task.started_at
task.completed -> Task.completed_at
task.cancelled -> Task.cancelled_at
task.reopened  -> Task.updated_at
~~~

For supported events where a specific lifecycle timestamp is unavailable, the
projection falls back to Task.updated_at.

## 17. Timeline titles for Activities

An Activity entry title uses:

~~~text
Activity.subject
~~~

when present.

Otherwise it falls back to:

~~~text
"<ActivityType> activity"
~~~

Examples:

~~~text
Quarterly account review

Call activity

Note activity
~~~

Activity.description becomes the optional Timeline summary.

## 18. Timeline titles for Tasks

Task lifecycle titles make the occurrence explicit:

~~~text
Task created: Prepare renewal
Task started: Prepare renewal
Task completed: Prepare renewal
Task cancelled: Prepare renewal
Task reopened: Prepare renewal
~~~

Task.description becomes the optional summary.

## 19. Projection metadata

Activity metadata includes selected read-oriented fields:

~~~text
activity_type
direction
duration_seconds
source
~~~

Task metadata includes:

~~~text
status
priority
due_at
owner_id
assignee_id
source
~~~

Communication entries include delivery-oriented metadata such as:

~~~text
delivery_status
provider
~~~

Projection metadata is JSON-compatible and frozen inside TimelineEntry.

## 20. Actor and correlation context

Domain Event context is copied into Timeline entries:

~~~text
actor_id
correlation_id
~~~

Example:

~~~python
crm = CRM.memory().with_context(
    actor_id="sales-user-42",
    correlation_id="renewal-flow-001",
)
~~~

A Task/Activity occurrence projected from that scoped CRM preserves those values
for relationship-history traceability.

## 21. Read a Contact timeline

~~~python
history = crm.timeline.for_contact(
    contact.id,
)

for entry in history.items:
    print(
        entry.occurred_at,
        entry.kind,
        entry.event_type,
        entry.title,
    )
~~~

The facade creates the Contact EntityReference internally.

## 22. Read an Organization timeline

~~~python
history = crm.timeline.for_organization(
    organization.id,
)
~~~

Again, the facade builds the Organization EntityReference internally.

The repository contract itself remains generic and works with any
EntityReference.

## 23. Read one entry by ID

~~~python
entry = crm.timeline.get(
    timeline_entry_id,
)
~~~

Missing entries raise:

~~~text
NotFoundError
code = timeline.not_found
~~~

TimelineRepository also exposes find() for nullable repository-level access.

## 24. Reverse-chronological ordering

The stable ordering is:

~~~text
occurred_at DESC
kind ASC
id ASC
~~~

The primary sort key is business occurrence time.

That ensures the newest meaningful customer-history occurrence appears first.

kind and ID stabilize ties.

## 25. Why occurrence ordering matters

Imagine this history:

~~~text
2026 task completed
2026 task created
2024 imported meeting
~~~

Even if the 2024 meeting was imported after the Task lifecycle, Timeline still
orders it at 2024 because the Activity projector uses Activity.occurred_at.

This is a core customer-history invariant.

## 26. Filter by kind

~~~python
from pycrmkit.timeline import TimelineEntryKind

tasks = crm.timeline.for_contact(
    contact.id,
    kind=TimelineEntryKind.TASK,
)
~~~

Available kinds include Activity, Task and Communication.

## 27. Filter by event type

~~~python
completed = crm.timeline.for_contact(
    contact.id,
    event_type="task.completed",
)
~~~

event_type is parsed through the stable EventType contract.

## 28. Filter by occurrence window

Timeline supports:

~~~text
occurred_from
occurred_until
~~~

with half-open semantics:

~~~text
occurred_from <= occurred_at < occurred_until
~~~

Example:

~~~python
from datetime import UTC, datetime

history = crm.timeline.for_contact(
    contact.id,
    occurred_from=datetime(
        2026, 9, 1, tzinfo=UTC
    ),
    occurred_until=datetime(
        2026, 10, 1, tzinfo=UTC
    ),
)
~~~

September 1 is included. October 1 is excluded.

## 29. Invalid occurrence windows

This is invalid:

~~~text
occurred_until <= occurred_from
~~~

and raises:

~~~text
ValidationError
code = timeline.query.invalid_interval
~~~

Timestamps follow the shared timezone-aware UTC contract.

## 30. Combine filters

Filters may be combined:

~~~python
history = crm.timeline.for_contact(
    contact.id,
    kind=TimelineEntryKind.TASK,
    event_type="task.completed",
    occurred_from=start,
    occurred_until=end,
)
~~~

This remains a read-side query over immutable projections.

## 31. Pagination

Timeline uses OffsetPageRequest:

~~~python
from pycrmkit.core.pagination import OffsetPageRequest

page = crm.timeline.for_contact(
    contact.id,
    OffsetPageRequest(
        limit=25,
        offset=0,
    ),
)

print(page.items)
print(page.total)
print(page.has_next)
print(page.has_previous)
~~~

Repository adapters must return exact totals and deterministic offset pages.

## 32. Complete Activity + Task history example

~~~python
from datetime import UTC, datetime, timedelta

from pycrmkit import CRM
from pycrmkit.activities import ActivityParticipant
from pycrmkit.core.references import EntityReference
from pycrmkit.core.time import FixedClock

clock = FixedClock(
    datetime(2026, 9, 27, 10, 0, tzinfo=UTC)
)

crm = CRM.memory(clock=clock).with_context(
    actor_id="guide-user",
    correlation_id="timeline-guide-001",
)

contact = crm.contacts.create(
    display_name="Ada Lovelace",
)
organization = crm.organizations.create(
    legal_name="Analytical Engines Ltd",
)

contact_ref = EntityReference(
    kind="contact",
    id=contact.id,
)
organization_ref = EntityReference(
    kind="organization",
    id=organization.id,
)

historical = crm.activities.log(
    type="meeting",
    occurred_at=datetime(
        2024, 1, 15, 9, 0, tzinfo=UTC
    ),
    subject="Imported discovery meeting",
    participants=(
        ActivityParticipant(
            reference=contact_ref,
            is_primary=True,
        ),
    ),
    references=(organization_ref,),
    source="legacy-crm",
)

clock.advance(timedelta(hours=1))

task = crm.tasks.create(
    title="Prepare renewal",
    priority="high",
    references=(
        contact_ref,
        organization_ref,
    ),
)

clock.advance(timedelta(hours=1))
crm.tasks.start(task.id)

clock.advance(timedelta(hours=1))
crm.tasks.complete(task.id)

history = crm.timeline.for_contact(
    contact.id,
)

assert [
    str(entry.event_type)
    for entry in history.items
] == [
    "task.completed",
    "task.started",
    "task.created",
    "activity.created",
]

assert history.items[-1].occurred_at == historical.occurred_at
~~~

## 33. The same history can belong to Organization

Because both Activity and Task referenced the Organization:

~~~python
organization_history = crm.timeline.for_organization(
    organization.id,
)

assert organization_history.items == history.items
~~~

This is a powerful property of the EntityReference model:

~~~text
one occurrence
many related CRM histories
~~~

## 34. Timeline ignores generic updates

Suppose you update the Activity subject or Task priority.

Those operations emit Activity/Task update events for the Event/Audit systems,
but TimelineProjector does not project them.

Customer history remains focused on meaningful occurrences.

## 35. Projection happens in the same Unit of Work

CRMRuntime.record_change() creates the Domain Event and, when Timeline supports
that event type, invokes TimelineProjector using repositories from the current
Unit of Work.

Conceptually:

~~~text
source mutation
      |
      +-- save aggregate
      |
      +-- create DomainEvent
      |
      +-- project TimelineEntry
      |
      +-- stage Audit
      |
      v
    commit
~~~

This makes source state and customer history atomic.

## 36. Rollback removes the projection too

If the Unit of Work rolls back:

~~~text
source aggregate write     rolled back
Timeline projection        rolled back
Audit mutation             rolled back
external event dispatch    never committed
~~~

The Timeline does not retain a ghost entry for a mutation that failed to commit.

This behavior is explicitly qualified by PyCRMKit's E2E tests.

## 37. External event subscribers run after commit

Timeline projection occurs inside the transaction.

External InProcessEventBus subscribers receive staged Domain Events only after
successful commit.

This means:

~~~text
transactional read model
= Timeline

post-commit notification
= external event subscribers
~~~

The two mechanisms serve different consistency boundaries.

## 38. Replay is idempotent

TimelineRepository.append() has a strict replay contract.

If the same TimelineEntry ID with identical content is appended twice:

~~~text
first append  -> stored
second append -> no-op
~~~

The history still contains one entry.

This makes Domain Event replay safe.

## 39. Conflicting replay is rejected

If the same TimelineEntryId is reused with different content:

~~~text
same ID
different projection content
        |
        v
DuplicateError
code = timeline.projection.conflict
~~~

That detects projector corruption or incompatible projection behavior instead of
silently rewriting history.

## 40. Why source Event ID makes replay safe

The projector computes:

~~~text
TimelineEntryId(event.id.value)
~~~

Therefore projecting the same Domain Event again naturally targets the same
Timeline entry identity.

Replay safety is a consequence of deterministic identity, not an afterthought.

## 41. TimelineEntry normalization

TimelineEntry validates and normalizes:

~~~text
typed TimelineEntryId
typed EventId
matching entry/event UUID
TimelineEntryKind
EventType
EntityReference source entity
UTC occurred_at
required title
optional summary
deduplicated references
actor/correlation text
frozen JSON metadata
~~~

title is limited to 300 characters.

summary is limited to 2,000 characters.

## 42. Serialize an entry

TimelineEntry provides:

~~~python
payload = entry.to_dict()
~~~

The result uses JSON-compatible primitives:

~~~text
UUID-like IDs -> strings
kind -> string
event_type -> string
occurred_at -> ISO datetime
entity/reference IDs -> strings
metadata -> thawed JSON data
~~~

This is useful for transport/read APIs without exposing mutable internal state.

## 43. TimelineRepository contract

Adapter authors implement:

~~~text
get(TimelineEntryId) -> TimelineEntry
find(TimelineEntryId) -> TimelineEntry | None
append(TimelineEntry) -> None
list_for_reference(
    EntityReference,
    OffsetPageRequest,
    kind=...,
    event_type=...,
    occurred_from=...,
    occurred_until=...,
) -> Page[TimelineEntry]
~~~

The contract requires:

~~~text
immutable projections
idempotent identical replay
conflicting replay rejection
exact pagination
occurred_at DESC / kind ASC / id ASC
reference filtering
kind filtering
event-type filtering
half-open occurrence windows
no implicit outer commit
~~~

## 44. TimelineProjector contract

TimelineProjector receives repositories for source domains plus the Timeline
repository.

It answers two questions:

~~~text
supports(event_type)?
project(event)
~~~

Unsupported events return no Timeline entry.

Supported events load the source aggregate, build the deterministic projection
and call TimelineRepository.append().

## 45. Source aggregate loading matters

The projector does not rely only on a small Domain Event payload.

For Activities and Tasks it loads current source aggregate state from the same
Unit of Work.

This allows the projection to include:

~~~text
Activity subject/description/participants/references
Task title/description/references/priority/due/assignee
~~~

while keeping the Domain Event payload compact.

## 46. Querying Activity-only history

~~~python
activity_history = crm.timeline.for_contact(
    contact.id,
    kind=TimelineEntryKind.ACTIVITY,
)

assert all(
    entry.kind is TimelineEntryKind.ACTIVITY
    for entry in activity_history.items
)
~~~

## 47. Querying a Task transition exactly

~~~python
completed = crm.timeline.for_contact(
    contact.id,
    kind=TimelineEntryKind.TASK,
    event_type="task.completed",
)

assert [
    str(entry.event_type)
    for entry in completed.items
] == ["task.completed"]
~~~

## 48. Half-open boundary example

Suppose:

~~~text
task.created   at 08:00
task.started   at 09:00
task.completed at 10:00
~~~

Query:

~~~text
[08:00, 09:00)
~~~

returns only task.created.

Query:

~~~text
[09:00, 10:00)
~~~

returns only task.started.

The upper boundary is excluded.

## 49. Complete pagination/filter example

~~~python
from pycrmkit.core.pagination import OffsetPageRequest
from pycrmkit.timeline import TimelineEntryKind

first = crm.timeline.for_contact(
    contact.id,
    OffsetPageRequest(
        limit=1,
        offset=0,
    ),
    kind=TimelineEntryKind.TASK,
)

second = crm.timeline.for_contact(
    contact.id,
    OffsetPageRequest(
        limit=1,
        offset=1,
    ),
    kind=TimelineEntryKind.TASK,
)

assert first.total >= 2
assert first.has_next is True
assert second.has_previous is True
~~~

## 50. Timeline, Event and Audit mental model

Keep these three concepts separate:

~~~text
Domain Event
= something meaningful happened in the domain

Timeline
= customer-facing read projection of selected meaningful events

Audit
= operational trace of mutations and actor/context
~~~

They cooperate but they are not interchangeable.

## Common mistakes

### Treating Timeline as source of truth

Load Activities/Tasks/Communications from their own domains. Timeline is a read
projection.

### Manually creating customer-history entries

Use source domain operations. The projector owns projection semantics.

### Expecting every Domain Event in Timeline

Only selected meaningful events are projected.

### Expecting activity.updated or task.updated in Timeline

They are intentionally excluded to avoid edit noise.

### Ordering by created_at

Timeline orders by business occurred_at.

### Losing imported historical occurrence time

Activity projection deliberately uses Activity.occurred_at.

### Duplicating one entry per related Contact/Organization

One entry may contain multiple EntityReference values and appear in several
histories.

### Treating replay as "insert another row"

Replay of identical source events is idempotent.

### Silently overwriting a conflicting replay

The repository must raise timeline.projection.conflict.

### Projecting after the transaction commits

PyCRMKit stages Timeline projection inside the same Unit of Work so rollback is
atomic.

## Testing Timeline workflows

A public-level test can stay simple:

~~~python
from pycrmkit import CRM
from pycrmkit.core.references import EntityReference

def test_task_history_is_visible_for_contact() -> None:
    crm = CRM.memory()

    contact = crm.contacts.create(
        display_name="Ada Lovelace",
    )
    ref = EntityReference(
        kind="contact",
        id=contact.id,
    )

    task = crm.tasks.create(
        title="Prepare proposal",
        references=(ref,),
    )
    crm.tasks.complete(task.id)

    history = crm.timeline.for_contact(
        contact.id,
    )

    assert [
        str(entry.event_type)
        for entry in history.items
    ] == [
        "task.completed",
        "task.created",
    ]
~~~

Repository/projector tests can separately prove idempotent replay, conflict
detection and transactional rollback.

## What you learned

You can now explain and use:

- Timeline as a read-only projection;
- Timeline vs source aggregates vs Audit;
- TimelineEntry / TimelineEntryId;
- TimelineEntryKind;
- EventId-derived replay-safe identity;
- immutable entry semantics;
- source entity vs related references;
- Activity participant/reference projection;
- Activity business occurrence timestamps;
- Task lifecycle occurrence timestamps;
- Activity/Task/Communication projected events;
- actor/correlation propagation;
- Contact and Organization histories;
- kind/event/time filters;
- half-open occurrence windows;
- deterministic reverse-chronological ordering;
- pagination;
- TimelineEntry.to_dict();
- TimelineRepository replay contract;
- TimelineProjector;
- same-Unit-of-Work atomic projection;
- rollback behavior;
- post-commit external event dispatch.

## LEVEL 2 complete

You now understand the customer-activity layer:

~~~text
Activity
What happened?
    |
    v
Task
What needs to happen?
    |
    v
Timeline
What is the ordered customer history?
~~~

Together:

~~~text
CRM Core
Contacts / Organizations / Relationships
              |
              v
       Customer Activity
      Activities + Tasks
              |
              v
           Timeline
              |
              v
   relationship history
~~~

The next learning level is **LEVEL 3 - Sales**:

~~~text
10 Leads
11 Opportunities
12 Pipelines
13 Lead Conversion
~~~

That level moves from customer history into the sales process itself.
