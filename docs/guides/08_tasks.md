# 08 - Tasks

> Applies to PyCRMKit 1.0.x. Baseline: 1.0.0.

Tasks represent work that should happen in the customer relationship.

They complement Activities:

~~~text
Activity
= what happened

Task
= what needs to happen
~~~

A Task is not merely a row with a status column. PyCRMKit models Task status
changes as explicit domain transitions with timestamp invariants.

## What you will build

By the end of this chapter you will understand:

~~~text
Task
+-- TaskId
+-- title
+-- status
+-- priority
+-- description
+-- due_at
+-- owner_id
+-- assignee_id
+-- references
+-- source
+-- external_id
+-- metadata
+-- started_at
+-- completed_at
+-- cancelled_at
+-- created_at
+-- updated_at
~~~

The stable facade surface is:

~~~text
crm.tasks.create(...)
crm.tasks.get(...)
crm.tasks.update(...)
crm.tasks.start(...)
crm.tasks.complete(...)
crm.tasks.cancel(...)
crm.tasks.reopen(...)
crm.tasks.list(...)
~~~

## 1. Task lifecycle

The stable V1 lifecycle is explicit:

~~~text
open
 +-- start -------> in_progress
 +-- complete ----> completed
 +-- cancel ------> cancelled

in_progress
 +-- complete ----> completed
 +-- cancel ------> cancelled

completed
 +-- reopen ------> open

cancelled
 +-- reopen ------> open
~~~

Status cannot be changed through TaskUpdate.

That rule prevents application code, persistence adapters and future HTTP
integrations from bypassing lifecycle invariants.

## 2. Create a minimal Task

~~~python
from pycrmkit import CRM

crm = CRM.memory()

task = crm.tasks.create(
    title="Call customer",
)

assert task.status.value == "open"
assert task.priority.name.lower() == "normal"
~~~

New Tasks always begin OPEN through TaskService.create().

## 3. Title is required

Task.title is normalized using Unicode NFKC, trimming and whitespace collapse.

~~~python
task = crm.tasks.create(
    title="  Prepare   renewal proposal ",
)

assert task.title == "Prepare renewal proposal"
~~~

A blank title raises:

~~~text
ValidationError
code = task.title.required
~~~

The maximum title length is 300 characters.

## 4. Description

description is optional long-form text.

PyCRMKit normalizes Unicode and trims outer whitespace while preserving internal
content more closely than title.

The stable limit is 20,000 characters.

## 5. Task priorities

TaskPriority is an ordered IntEnum:

~~~text
LOW     = 10
NORMAL  = 20
HIGH    = 30
URGENT  = 40
~~~

So urgency ordering is:

~~~text
low < normal < high < urgent
~~~

You may pass:

~~~python
from pycrmkit.tasks import TaskPriority

crm.tasks.create(
    title="Prepare renewal",
    priority=TaskPriority.HIGH,
)
~~~

or a stable name:

~~~python
crm.tasks.create(
    title="Prepare renewal",
    priority="high",
)
~~~

or an exact enum numeric value:

~~~python
crm.tasks.create(
    title="Prepare renewal",
    priority=30,
)
~~~

Unknown names or numbers raise:

~~~text
ValidationError
code = task.priority.invalid
~~~

Boolean values are not treated as integer priorities.

## 6. due_at

due_at is optional and timezone-aware.

~~~python
from datetime import UTC, datetime

task = crm.tasks.create(
    title="Prepare proposal",
    due_at=datetime(
        2026,
        10,
        1,
        12,
        0,
        tzinfo=UTC,
    ),
)
~~~

PyCRMKit normalizes due_at to UTC.

A naive datetime is rejected by the shared timestamp contract.

## 7. Past due dates are valid

PyCRMKit deliberately permits:

~~~text
due_at < created_at
~~~

Why?

Because a CRM may import already-overdue work from another system.

So due_at is not validated as "must be future".

History and overdue state are different concerns.

## 8. owner_id vs assignee_id

Tasks expose two optional actor identifiers:

~~~text
owner_id
assignee_id
~~~

A useful application interpretation is:

~~~text
owner_id
= business ownership / responsibility context

assignee_id
= person or actor currently expected to perform the work
~~~

PyCRMKit keeps both as normalized strings without imposing an IAM/user model.

Example:

~~~python
task = crm.tasks.create(
    title="Prepare renewal proposal",
    owner_id="team-enterprise",
    assignee_id="seller-7",
)
~~~

The integration/application layer decides how these IDs map to real identities.

## 9. CRM references

A Task may reference CRM entities using EntityReference:

~~~python
from pycrmkit.core.references import EntityReference

contact = crm.contacts.create(
    display_name="Ada Lovelace",
)

contact_ref = EntityReference(
    kind="contact",
    id=contact.id,
)

task = crm.tasks.create(
    title="Call customer",
    references=(contact_ref,),
)
~~~

References answer:

~~~text
Which CRM entities is this work about?
~~~

A Task may reference several entities, for example a Contact and Organization.

Duplicate references are rejected:

~~~text
ValidationError
code = task.reference.duplicate
~~~

## 10. source, external_id and metadata

source records provenance:

~~~text
manual
workflow
legacy-crm
support-platform
sales-import
~~~

external_id preserves a source-system identifier.

metadata carries application/integration extension data.

Example:

~~~python
task = crm.tasks.create(
    title="Prepare renewal",
    source="legacy-crm",
    external_id="task-98765",
    metadata={
        "campaign": "renewal-2026",
    },
)
~~~

## 11. Start a Task

Only an OPEN Task may start:

~~~python
task = crm.tasks.start(task.id)

assert task.status.value == "in_progress"
assert task.started_at is not None
~~~

The transition sets:

~~~text
status       = in_progress
started_at   = transition time
completed_at = None
cancelled_at = None
updated_at   = transition time
~~~

Starting from any other status raises:

~~~text
InvalidStateError
code = task.transition.invalid
~~~

## 12. Complete a Task

A Task may be completed directly from:

~~~text
OPEN
IN_PROGRESS
~~~

Example:

~~~python
task = crm.tasks.complete(task.id)

assert task.status.value == "completed"
assert task.completed_at is not None
~~~

Completion does not require that the Task was started first.

That means this is valid:

~~~text
open -> completed
~~~

This is useful for quickly closing simple work items.

## 13. Cancel a Task

Cancellation is allowed from:

~~~text
OPEN
IN_PROGRESS
~~~

~~~python
task = crm.tasks.cancel(task.id)

assert task.status.value == "cancelled"
assert task.cancelled_at is not None
~~~

Cancellation clears completed_at and updates the transition timestamp.

## 14. Reopen a terminal Task

Only terminal Tasks can reopen:

~~~text
completed -> open
cancelled -> open
~~~

Example:

~~~python
task = crm.tasks.reopen(task.id)

assert task.status.value == "open"
~~~

Reopen starts a fresh work cycle and clears:

~~~text
started_at
completed_at
cancelled_at
~~~

This is important: reopen does not preserve the previous lifecycle timestamps as
current aggregate state.

Historical transition information belongs in events/audit/timeline.

## 15. Invalid lifecycle transitions

Examples that fail:

~~~text
in_progress -> start
completed   -> complete
cancelled   -> cancel
open        -> reopen
in_progress -> reopen
completed   -> start
~~~

All use:

~~~text
InvalidStateError
code = task.transition.invalid
~~~

The exception context contains:

~~~text
from
to
~~~

## 16. Transition timestamps cannot precede creation

A transition instant must satisfy:

~~~text
transition_at >= created_at
~~~

If a domain clock produces an earlier timestamp, the Task rejects it:

~~~text
ValidationError
code = task.transition.before_creation
~~~

This protects lifecycle chronology.

## 17. Lifecycle timestamp invariants

The Task aggregate validates status/timestamp coherence.

OPEN:

~~~text
started_at   = None
completed_at = None
cancelled_at = None
~~~

IN_PROGRESS:

~~~text
started_at   = required
completed_at = None
cancelled_at = None
~~~

COMPLETED:

~~~text
completed_at = required
cancelled_at = None
~~~

CANCELLED:

~~~text
cancelled_at = required
completed_at = None
~~~

These invariants are checked whenever a Task aggregate is constructed.

## 18. is_terminal

~~~python
assert task.is_terminal is True
~~~

for:

~~~text
completed
cancelled
~~~

and False for:

~~~text
open
in_progress
~~~

## 19. Overdue semantics

Task.is_overdue(at) returns True only when:

~~~text
status is OPEN or IN_PROGRESS
and due_at exists
and due_at < at
~~~

So overdue is strict:

~~~text
due_at == at
-> not overdue

due_at < at
-> overdue
~~~

Completed and cancelled Tasks are never overdue.

## 20. Update editable fields

Use TaskUpdate for non-lifecycle fields:

~~~python
from pycrmkit.tasks import TaskUpdate

task = crm.tasks.update(
    task.id,
    TaskUpdate(
        title="Prepare strategic renewal proposal",
        priority="urgent",
        assignee_id="seller-9",
    ),
)
~~~

Editable fields include:

~~~text
title
description
priority
due_at
owner_id
assignee_id
references
source
external_id
metadata
~~~

Status is intentionally absent.

## 21. UNSET vs None

TaskUpdate follows the standard PyCRMKit update semantics:

~~~text
UNSET
-> leave unchanged

None
-> explicitly clear a nullable field
~~~

Example:

~~~python
task = crm.tasks.update(
    task.id,
    TaskUpdate(
        due_at=None,
        assignee_id=None,
        external_id=None,
    ),
)
~~~

This clears those fields.

## 22. Updates preserve lifecycle state

Suppose a Task is IN_PROGRESS.

~~~python
task = crm.tasks.start(task.id)

updated = crm.tasks.update(
    task.id,
    TaskUpdate(
        priority="urgent",
    ),
)

assert updated.status.value == "in_progress"
assert updated.started_at == task.started_at
~~~

TaskUpdate edits profile/work metadata without silently changing the lifecycle.

## 23. Terminal Tasks may still be corrected

The V1 domain does not make COMPLETED/CANCELLED Tasks immutable.

For example, this is permitted:

~~~python
completed = crm.tasks.complete(task.id)

corrected = crm.tasks.update(
    completed.id,
    TaskUpdate(
        description="Corrected completion context",
    ),
)

assert corrected.status.value == "completed"
~~~

The lifecycle remains valid and the terminal timestamp is preserved.

This is different from archived Contacts/Organizations or ended Relationships.

## 24. Query Tasks

Use TaskQuery:

~~~python
from pycrmkit.tasks import TaskQuery

page = crm.tasks.list(
    TaskQuery(
        status="open",
    ),
)
~~~

Portable filters include:

~~~text
status
priority
owner_id
assignee_id
reference
source
external_id
due_from
due_until
overdue_at
~~~

## 25. Filter by status

~~~python
open_tasks = crm.tasks.list(
    TaskQuery(
        status="open",
    ),
)
~~~

TaskQuery converts status to TaskStatus.

## 26. Filter by priority

~~~python
urgent = crm.tasks.list(
    TaskQuery(
        priority="urgent",
    ),
)
~~~

Priority uses the same parse_priority contract as Task creation/update.

## 27. Filter by owner and assignee

~~~python
seller_tasks = crm.tasks.list(
    TaskQuery(
        assignee_id=" seller-7 ",
    ),
)
~~~

owner_id and assignee_id are whitespace-normalized.

Matching is exact after normalization.

## 28. Filter by CRM reference

~~~python
customer_tasks = crm.tasks.list(
    TaskQuery(
        reference=contact_ref,
    ),
)
~~~

This is how you ask:

~~~text
Which tasks are related to this Contact/Organization/etc.?
~~~

## 29. Filter by source

~~~python
legacy = crm.tasks.list(
    TaskQuery(
        source="LEGACY-CRM",
    ),
)
~~~

source matching is case-insensitive.

## 30. Filter by external_id

~~~python
page = crm.tasks.list(
    TaskQuery(
        external_id="task-98765",
    ),
)
~~~

external_id uses normalized exact matching.

## 31. Due-date windows

TaskQuery supports:

~~~text
due_from
due_until
~~~

The interval is half-open:

~~~text
due_from <= due_at < due_until
~~~

Example:

~~~python
from datetime import UTC, datetime

october = crm.tasks.list(
    TaskQuery(
        due_from=datetime(
            2026, 10, 1, tzinfo=UTC
        ),
        due_until=datetime(
            2026, 11, 1, tzinfo=UTC
        ),
    ),
)
~~~

Tasks without due_at do not match a due-date window.

## 32. Invalid due windows

This is invalid:

~~~text
due_until <= due_from
~~~

and raises:

~~~text
ValidationError
code = task.query.invalid_due_interval
~~~

## 33. overdue_at queries

~~~python
overdue = crm.tasks.list(
    TaskQuery(
        overdue_at=datetime(
            2026, 10, 15, tzinfo=UTC
        ),
    ),
)
~~~

This returns only unresolved Tasks whose due_at is strictly earlier than that
instant.

Completed/cancelled Tasks are excluded even if their due date is old.

## 34. Deterministic ordering

TaskRepository uses:

~~~text
due_at ASC
undated tasks last
created_at DESC
id ASC
~~~

So the work queue naturally prioritizes dated tasks by earliest due date.

When due dates tie, newer-created Tasks come first, then ID stabilizes ordering.

## 35. Pagination

~~~python
from pycrmkit.core.pagination import OffsetPageRequest

page = crm.tasks.list(
    TaskQuery(
        assignee_id="seller-7",
    ),
    OffsetPageRequest(
        limit=25,
        offset=0,
    ),
)
~~~

The shared stable pagination bounds apply:

~~~text
default limit = 50
maximum limit = 200
offset >= 0
~~~

## 36. Complete Task lifecycle example

~~~python
from datetime import UTC, datetime

from pycrmkit import CRM
from pycrmkit.core.references import EntityReference
from pycrmkit.core.time import FixedClock
from pycrmkit.tasks import (
    TaskPriority,
    TaskQuery,
    TaskStatus,
    TaskUpdate,
)

clock = FixedClock(
    datetime(2026, 9, 27, 10, 0, tzinfo=UTC)
)

crm = CRM.memory(
    clock=clock,
).with_context(
    actor_id="guide-user",
    correlation_id="tasks-guide-001",
)

contact = crm.contacts.create(
    display_name="Ada Lovelace",
)
contact_ref = EntityReference(
    kind="contact",
    id=contact.id,
)

task = crm.tasks.create(
    title="Prepare renewal proposal",
    description="Prepare the Q4 renewal package.",
    priority=TaskPriority.HIGH,
    due_at=datetime(
        2026, 10, 1, 12, 0, tzinfo=UTC
    ),
    owner_id="sales-team",
    assignee_id="seller-7",
    references=(contact_ref,),
    source="manual",
    external_id="renewal-task-001",
)

assert task.status is TaskStatus.OPEN
assert task.priority is TaskPriority.HIGH

task = crm.tasks.start(task.id)

assert task.status is TaskStatus.IN_PROGRESS
assert task.started_at == clock.now()

task = crm.tasks.update(
    task.id,
    TaskUpdate(
        priority="urgent",
        assignee_id="seller-9",
    ),
)

assert task.status is TaskStatus.IN_PROGRESS
assert task.priority is TaskPriority.URGENT
assert task.assignee_id == "seller-9"

task = crm.tasks.complete(task.id)

assert task.status is TaskStatus.COMPLETED
assert task.completed_at == clock.now()
assert task.is_terminal is True

task = crm.tasks.reopen(task.id)

assert task.status is TaskStatus.OPEN
assert task.started_at is None
assert task.completed_at is None
assert task.cancelled_at is None
~~~

## 37. Complete overdue/query example

~~~python
from datetime import UTC, datetime

crm = CRM.memory()

contact = crm.contacts.create(
    display_name="Ada Lovelace",
)
ref = EntityReference(
    kind="contact",
    id=contact.id,
)

overdue_task = crm.tasks.create(
    title="Old follow-up",
    priority="high",
    due_at=datetime(
        2026, 9, 1, tzinfo=UTC
    ),
    assignee_id="seller-7",
    references=(ref,),
)

future_task = crm.tasks.create(
    title="Future follow-up",
    priority="normal",
    due_at=datetime(
        2026, 11, 1, tzinfo=UTC
    ),
    assignee_id="seller-7",
    references=(ref,),
)

undated = crm.tasks.create(
    title="Backlog research",
    assignee_id="seller-7",
    references=(ref,),
)

page = crm.tasks.list(
    TaskQuery(
        assignee_id="seller-7",
        reference=ref,
    ),
)

assert page.items == (
    overdue_task,
    future_task,
    undated,
)

overdue = crm.tasks.list(
    TaskQuery(
        overdue_at=datetime(
            2026, 9, 27, tzinfo=UTC
        ),
    ),
)

assert overdue.items == (overdue_task,)
~~~

## 38. Direct completion example

A start transition is not mandatory:

~~~python
task = crm.tasks.create(
    title="Send confirmation",
)

completed = crm.tasks.complete(
    task.id,
)

assert completed.status is TaskStatus.COMPLETED
assert completed.started_at is None
assert completed.completed_at is not None
~~~

This is valid by design.

## 39. Reopen after cancellation

~~~python
task = crm.tasks.create(
    title="Schedule meeting",
)

cancelled = crm.tasks.cancel(
    task.id,
)

assert cancelled.status is TaskStatus.CANCELLED

reopened = crm.tasks.reopen(
    task.id,
)

assert reopened.status is TaskStatus.OPEN
assert reopened.cancelled_at is None
~~~

## 40. Task events and audit

Facade operations produce:

~~~text
task.created
task.updated
task.started
task.completed
task.cancelled
task.reopened
~~~

The event payload contains current:

~~~text
status
priority
~~~

With CRM context, actor_id/correlation_id propagate through the same audit/event
infrastructure as other CRM domains.

## 41. Task and Timeline

Task lifecycle events are projected into Timeline.

Conceptually:

~~~text
task.created
task.started
task.completed
task.reopened
task.cancelled
      |
      v
Timeline entries
      |
      v
Contact / Organization history
~~~

If the Task references both a Contact and Organization, the same Task lifecycle
can become visible in both timelines.

Chapter 09 covers the projection/read model in detail.

## 42. Transaction semantics

Each facade command runs through a Unit of Work:

~~~text
Application
    |
    v
crm.tasks
    |
    v
TaskService
    |
    v
Task aggregate transition/update
    |
    v
TaskRepository
    |
    +-- save state
    +-- stage event
    +-- stage audit
    |
    v
commit
~~~

Storage adapters must not invent different lifecycle semantics.

## 43. TaskRepository contract

Adapter authors implement:

~~~text
get(TaskId) -> Task
find(TaskId) -> Task | None
save(Task) -> None
list(TaskQuery, OffsetPageRequest) -> Page[Task]
~~~

The contract requires:

~~~text
get raises NotFoundError
find returns None
save replaces current state
no implicit outer commit
exact offset pagination
deterministic due-date ordering
status/priority/owner/assignee/reference filters
half-open due windows
terminal-safe overdue semantics
~~~

Lifecycle transitions remain aggregate/service responsibilities.

## Common mistakes

### Using Activity instead of Task

Activity records history. Task represents pending/actionable work.

### Updating status through TaskUpdate

Impossible by design. Use explicit transition methods.

### Assuming start is required before complete

OPEN can transition directly to COMPLETED.

### Treating completed/cancelled tasks as overdue

Terminal Tasks are never overdue.

### Considering due_at == now overdue

Overdue uses strict due_at < instant.

### Rejecting imported past due dates

Past due dates are valid and useful for historical/imported work.

### Assuming reopen resumes the previous work cycle

Reopen resets lifecycle timestamps and creates a fresh OPEN cycle.

### Assuming terminal Tasks are immutable

Lifecycle transitions are restricted, but TaskUpdate can still correct editable
fields while preserving terminal status/timestamps.

### Using naive datetimes

due_at/query timestamps use timezone-aware UTC semantics.

### Querying ORM models directly

Use TaskQuery so all qualified persistence adapters preserve the same behavior.

## Testing Task workflows

Test public transitions rather than mutating status directly:

~~~python
from pycrmkit import CRM
from pycrmkit.tasks import TaskQuery, TaskStatus

def test_task_can_be_started_and_completed() -> None:
    crm = CRM.memory()

    task = crm.tasks.create(
        title="Prepare proposal",
        priority="high",
    )

    task = crm.tasks.start(task.id)
    assert task.status is TaskStatus.IN_PROGRESS

    task = crm.tasks.complete(task.id)
    assert task.status is TaskStatus.COMPLETED

    completed = crm.tasks.list(
        TaskQuery(
            status=TaskStatus.COMPLETED,
        ),
    )

    assert completed.items == (task,)
~~~

Persistent adapter contract tests then prove the same observable behavior
against PostgreSQL and other supported adapters.

## What you learned

You can now explain and use:

- Task and TaskId;
- TaskStatus;
- TaskPriority and parse_priority;
- required title and description semantics;
- due_at and imported overdue work;
- owner_id vs assignee_id;
- EntityReference associations;
- source / external_id / metadata;
- explicit start/complete/cancel/reopen transitions;
- lifecycle timestamp invariants;
- direct OPEN -> COMPLETED;
- reopen reset semantics;
- is_terminal;
- strict overdue semantics;
- TaskUpdate and UNSET/None;
- terminal Task corrections;
- TaskQuery filters;
- half-open due windows;
- overdue_at queries;
- deterministic due-date ordering;
- pagination;
- Task events/audit;
- TaskRepository and Unit of Work boundaries.

## Next

The next chapter is **09 - Timeline**.

Activities answer:

~~~text
What happened?
~~~

Tasks answer:

~~~text
What needs to happen?
~~~

Timeline answers:

~~~text
What is the ordered customer history produced by those domain events?
~~~

Chapter 09 will close LEVEL 2 by showing how Activity and Task events are
projected into a read-only customer history for Contacts and Organizations.
