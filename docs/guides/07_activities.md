# 07 - Activities

> Applies to PyCRMKit 1.0.x. Baseline: 1.0.0.

Activities are the first domain in LEVEL 2 - Customer Activity. They record
something that happened in the customer relationship without coupling the CRM
core to an email provider, telephony platform, calendar, document store or
workflow engine.

The central idea is:

~~~text
CRM structure
Contacts / Organizations / Relationships
              |
              v
         Interactions
              |
              v
          Activity
~~~

An Activity is history.

A Task, introduced in the next chapter, is work that should happen.

## What you will build

By the end of this chapter you will be able to model:

~~~text
Activity
+-- ActivityId
+-- type
+-- occurred_at
+-- subject
+-- description
+-- direction
+-- duration_seconds
+-- participants
+-- references
+-- source
+-- external_id
+-- metadata
+-- created_at
+-- updated_at
~~~

and query that interaction history by:

~~~text
type
participant
reference
direction
source
external_id
time window
~~~

The stable application-facing surface is:

~~~text
crm.activities.log(...)
crm.activities.get(...)
crm.activities.update(...)
crm.activities.list(...)
~~~

## 1. Activity means "something happened"

Use Activity for facts in customer history:

~~~text
a call happened
an email interaction was recorded
a meeting happened
a note was written
a message was exchanged
a document interaction was recorded
a business event happened
~~~

Do not use Activity as a future-work queue.

That distinction is fundamental:

~~~text
Activity
= interaction/history

Task
= action/work to perform
~~~

## 2. Activity is provider-independent

PyCRMKit Activity does not itself:

~~~text
send email
place a phone call
schedule a calendar meeting
store document bytes
run a workflow
~~~

It records CRM interaction history.

Provider-specific communication behavior belongs to the Communication,
Email, Events and integration layers introduced later in the course.

## 3. Activity types

ActivityType is a closed V1 enum:

~~~text
EMAIL
CALL
MEETING
NOTE
MESSAGE
DOCUMENT
EVENT
CUSTOM
~~~

Example:

~~~python
from pycrmkit.activities import ActivityType

activity_type = ActivityType.CALL

assert activity_type.value == "call"
~~~

The CUSTOM type gives applications an escape hatch when the base vocabulary is
not specific enough.

Unlike RelationshipType, ActivityType is not an open-ended normalized string.

## 4. Log a minimal Activity

An Activity must carry meaningful interaction context.

This is valid:

~~~python
from pycrmkit import CRM

crm = CRM.memory()

activity = crm.activities.log(
    type="note",
    description="Customer requested a revised proposal.",
)
~~~

This is also valid:

~~~python
activity = crm.activities.log(
    type="call",
    subject="Commercial follow-up",
)
~~~

The domain requires at least one of:

~~~text
subject
description
participants
references
external_id
~~~

## 5. Empty Activities are rejected

This is invalid:

~~~python
crm.activities.log(
    type="note",
)
~~~

because type alone is not enough interaction context.

It raises:

~~~text
ValidationError
code = activity.context.required
~~~

Fields such as direction, duration, source or metadata do not by themselves make
an Activity meaningful.

## 6. occurred_at is not created_at

This is one of the most important Activity concepts.

~~~text
occurred_at
= when the interaction actually happened

created_at
= when this Activity record entered PyCRMKit
~~~

These can be very different.

For a live interaction:

~~~text
occurred_at ~= created_at
~~~

For historical import:

~~~text
interaction happened in 2024
record imported in 2026

occurred_at = 2024
created_at  = 2026
~~~

## 7. Default occurred_at

When occurred_at is omitted, the Activity service uses the domain clock:

~~~python
activity = crm.activities.log(
    type="meeting",
    subject="Discovery meeting",
)

assert activity.occurred_at == activity.created_at
~~~

With a custom/fixed clock, both use that clock at creation time.

## 8. Import historical interaction data

Use an explicit timezone-aware datetime:

~~~python
from datetime import UTC, datetime

historical = crm.activities.log(
    type="meeting",
    occurred_at=datetime(
        2024,
        1,
        15,
        9,
        0,
        tzinfo=UTC,
    ),
    subject="Imported discovery meeting",
    source="legacy-crm",
)
~~~

The Activity preserves that historical occurrence time even though the record is
created now.

This is essential for correct customer history and Timeline ordering.

## 9. Timestamps must be timezone-aware

PyCRMKit timestamp normalization uses UTC.

Naive datetimes are rejected rather than interpreted using the machine's local
timezone.

Conceptually:

~~~text
timezone-aware datetime
        |
        v
normalize to UTC

naive datetime
        |
        v
ValueError
~~~

This prevents infrastructure-dependent timestamp interpretation.

## 10. ActivityDirection

Directional interactions may use:

~~~text
INBOUND
OUTBOUND
INTERNAL
~~~

Example:

~~~python
from pycrmkit.activities import ActivityDirection

call = crm.activities.log(
    type="call",
    subject="Renewal discussion",
    direction=ActivityDirection.OUTBOUND,
)
~~~

Direction is optional.

A Note or Document activity may not have meaningful inbound/outbound semantics.

## 11. Duration

Use duration_seconds when the interaction has measurable duration:

~~~python
call = crm.activities.log(
    type="call",
    subject="Renewal discussion",
    duration_seconds=480,
)
~~~

Duration must be:

~~~text
integer
>= 0
~~~

Negative durations and boolean values are rejected.

Invalid duration raises:

~~~text
ValidationError
code = activity.duration.invalid
~~~

## 12. Subject normalization

subject is optional and normalized for CRM display:

~~~text
Unicode NFKC
trim
collapse whitespace
~~~

Example:

~~~python
activity = crm.activities.log(
    type="meeting",
    subject="  Customer   discovery  ",
)

assert activity.subject == "Customer discovery"
~~~

subject is limited to 300 characters.

## 13. Description semantics

description is optional long-form text.

PyCRMKit:

~~~text
normalizes Unicode
trims outer whitespace
preserves internal text more closely than subject
limits length to 10,000 characters
~~~

An empty/whitespace-only description becomes None.

## 14. Participants

ActivityParticipant connects an Activity to an entity that actively
participated in the interaction.

~~~python
from pycrmkit.activities import ActivityParticipant
from pycrmkit.core.references import EntityReference

contact = crm.contacts.create(
    display_name="Ada Lovelace",
)

contact_ref = EntityReference(
    kind="contact",
    id=contact.id,
)

participant = ActivityParticipant(
    reference=contact_ref,
    role="customer",
    is_primary=True,
)
~~~

A participant is a Value Object.

## 15. Participant role

role is optional and open-ended:

~~~text
customer
host
attendee
speaker
account-manager
decision-maker
~~~

PyCRMKit normalizes whitespace but does not impose a closed role taxonomy.

The maximum role length is 120 characters.

## 16. Primary participant

An Activity may have at most one primary participant.

Valid:

~~~python
participants=(
    ActivityParticipant(
        reference=contact_ref,
        role="customer",
        is_primary=True,
    ),
    ActivityParticipant(
        reference=organization_ref,
        role="account",
    ),
)
~~~

Invalid:

~~~text
two participants with is_primary=True
~~~

raises:

~~~text
ValidationError
code = activity.participant.multiple_primary
~~~

## 17. A participant entity may appear only once

The same EntityReference cannot be repeated in participants, even with different
roles.

This is invalid:

~~~text
contact:123 as customer
contact:123 as attendee
~~~

and raises:

~~~text
ValidationError
code = activity.participant.duplicate
~~~

If one entity has several business interpretations, model one participant role
or express additional information in metadata/application semantics.

## 18. references are different from participants

participants answer:

~~~text
Who participated in this interaction?
~~~

references answer:

~~~text
What other CRM entities is this interaction associated with?
~~~

Example:

~~~python
activity = crm.activities.log(
    type="meeting",
    subject="Contract review",
    participants=(
        ActivityParticipant(
            reference=contact_ref,
            role="customer",
            is_primary=True,
        ),
    ),
    references=(
        organization_ref,
    ),
)
~~~

Here:

~~~text
Contact participated
Organization is associated/referenced
~~~

This distinction becomes important for Timeline projection.

## 19. References must be unique

The same EntityReference cannot appear twice in references.

Duplicate references raise:

~~~text
ValidationError
code = activity.reference.duplicate
~~~

An entity may, however, appear as a participant and also be otherwise relevant
to application semantics; participant/reference collections are validated
independently.

## 20. source

source identifies where the interaction record came from:

~~~text
manual
legacy-crm
calendar-import
support-platform
email-sync
mobile-app
~~~

Example:

~~~python
activity = crm.activities.log(
    type="meeting",
    subject="Imported discovery",
    source="legacy-crm",
)
~~~

source is normalized for display, while ActivityQuery compares it
case-insensitively.

## 21. external_id

external_id stores an external source identifier:

~~~python
activity = crm.activities.log(
    type="email",
    subject="Welcome message",
    source="email-sync",
    external_id="msg-2026-00042",
)
~~~

This is useful for integration traceability and source-system correlation.

external_id is normalized for surrounding/duplicate whitespace and limited to
255 characters.

## 22. metadata

metadata carries application/integration extension data:

~~~python
activity = crm.activities.log(
    type="call",
    subject="Renewal discussion",
    metadata={
        "campaign": "renewal-2026",
        "recording_available": True,
    },
)
~~~

Metadata should not replace stable typed Activity concepts when those concepts
already exist.

## 23. Complete interaction example

~~~python
from datetime import UTC, datetime

from pycrmkit import CRM
from pycrmkit.activities import (
    ActivityDirection,
    ActivityParticipant,
    ActivityType,
)
from pycrmkit.core.references import EntityReference

crm = CRM.memory().with_context(
    actor_id="guide-user",
    correlation_id="activities-guide-001",
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

activity = crm.activities.log(
    type=ActivityType.MEETING,
    occurred_at=datetime(
        2026,
        9,
        27,
        15,
        0,
        tzinfo=UTC,
    ),
    subject="Quarterly account review",
    description="Reviewed roadmap, risks and next steps.",
    direction=ActivityDirection.OUTBOUND,
    duration_seconds=3600,
    participants=(
        ActivityParticipant(
            reference=contact_ref,
            role="customer",
            is_primary=True,
        ),
    ),
    references=(organization_ref,),
    source="manual",
    external_id="meeting-2026-q3-ada",
    metadata={
        "channel": "video",
    },
)
~~~

## 24. Read an Activity

~~~python
reloaded = crm.activities.get(
    activity.id,
)

assert reloaded == activity
~~~

The repository contract also exposes nullable find(id) for adapter/domain
extension use, while the facade uses get(id).

Missing get operations raise:

~~~text
NotFoundError
code = activity.not_found
~~~

## 25. Activities are correctable

CRM history sometimes needs correction:

~~~text
wrong subject
wrong source
wrong participant role
wrong occurrence timestamp
import mapping correction
~~~

Use ActivityUpdate rather than mutating the object directly.

~~~python
from pycrmkit.activities import ActivityUpdate

updated = crm.activities.update(
    activity.id,
    ActivityUpdate(
        subject="Quarterly customer review",
        source="crm-ui",
    ),
)
~~~

Identity and created_at remain stable while updated_at advances.

## 26. UNSET vs None

ActivityUpdate follows the same partial-update contract used elsewhere:

~~~text
UNSET
-> keep current field

None
-> explicitly clear a nullable field
~~~

Example:

~~~python
updated = crm.activities.update(
    activity.id,
    ActivityUpdate(
        direction=None,
        external_id=None,
    ),
)
~~~

This clears direction and external_id.

## 27. Updates must still produce a valid Activity

ActivityUpdate rebuilds and revalidates the complete candidate aggregate.

So you cannot clear the final meaningful context.

Example conceptually:

~~~text
Activity has only subject
        |
update subject=None
        |
        v
no subject
no description
no participants
no references
no external_id
        |
        v
activity.context.required
~~~

Validation is therefore enforced on both creation and correction.

## 28. Replace participants/references explicitly

ActivityUpdate collection fields represent resulting aggregate state.

Example:

~~~python
updated = crm.activities.update(
    activity.id,
    ActivityUpdate(
        participants=(
            ActivityParticipant(
                reference=contact_ref,
                role="decision-maker",
                is_primary=True,
            ),
        ),
        references=(),
    ),
)
~~~

This replaces the participant/reference tuples.

It is not an implicit append/remove command.

## 29. Query Activities

Use ActivityQuery:

~~~python
from pycrmkit.activities import ActivityQuery

page = crm.activities.list(
    ActivityQuery(
        participant=contact_ref,
    ),
)
~~~

Available filters:

~~~text
type
participant
reference
direction
source
external_id
occurred_from
occurred_until
~~~

These are portable repository semantics rather than ORM-specific filters.

## 30. Filter by Activity type

~~~python
from pycrmkit.activities import ActivityType

calls = crm.activities.list(
    ActivityQuery(
        type=ActivityType.CALL,
    ),
)
~~~

## 31. Filter by participant

participant matches:

~~~text
ActivityParticipant.reference
~~~

Example:

~~~python
page = crm.activities.list(
    ActivityQuery(
        participant=contact_ref,
    ),
)
~~~

This answers:

~~~text
Which interactions did this CRM entity participate in?
~~~

## 32. Filter by generic reference

reference matches Activity.references:

~~~python
page = crm.activities.list(
    ActivityQuery(
        reference=organization_ref,
    ),
)
~~~

This answers a different question:

~~~text
Which interactions are associated with this CRM entity?
~~~

## 33. Filter by direction

~~~python
outbound = crm.activities.list(
    ActivityQuery(
        direction=ActivityDirection.OUTBOUND,
    ),
)
~~~

## 34. Filter by source

~~~python
legacy = crm.activities.list(
    ActivityQuery(
        source="LEGACY-CRM",
    ),
)
~~~

ActivityQuery normalizes source using case-folded comparison semantics.

## 35. Filter by external_id

~~~python
page = crm.activities.list(
    ActivityQuery(
        external_id="meeting-2026-q3-ada",
    ),
)
~~~

external_id uses normalized exact matching rather than case-folded source
semantics.

## 36. Time-window queries

ActivityQuery supports:

~~~text
occurred_from
occurred_until
~~~

The window is half-open:

~~~text
occurred_from <= occurred_at < occurred_until
~~~

Example:

~~~python
from datetime import UTC, datetime

page = crm.activities.list(
    ActivityQuery(
        occurred_from=datetime(
            2026, 9, 1, tzinfo=UTC
        ),
        occurred_until=datetime(
            2026, 10, 1, tzinfo=UTC
        ),
    ),
)
~~~

This includes September 1 and excludes October 1.

## 37. Invalid query windows

This is invalid:

~~~text
occurred_until <= occurred_from
~~~

and raises:

~~~text
ValidationError
code = activity.query.invalid_interval
~~~

## 38. Deterministic ordering

ActivityRepository returns interaction history in:

~~~text
occurred_at DESC
id ASC
~~~

So the newest interaction occurrence appears first.

This is based on occurred_at, not created_at.

That means imported historical data lands at its correct point in customer
history instead of appearing at the top simply because it was imported today.

## 39. Pagination

~~~python
from pycrmkit.core.pagination import OffsetPageRequest

page = crm.activities.list(
    ActivityQuery(
        participant=contact_ref,
    ),
    OffsetPageRequest(
        limit=25,
        offset=0,
    ),
)

print(page.total)
print(page.has_next)
print(page.has_previous)
~~~

The shared stable limits apply:

~~~text
default limit = 50
maximum limit = 200
offset >= 0
~~~

## 40. Historical import example

Suppose today is 2026 but the source CRM says a meeting happened in 2024.

~~~python
historical = crm.activities.log(
    type="meeting",
    occurred_at=datetime(
        2024,
        1,
        15,
        9,
        0,
        tzinfo=UTC,
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
~~~

The Activity has:

~~~text
occurred_at = historical interaction timestamp
created_at  = current PyCRMKit insertion timestamp
~~~

Timeline projection later preserves occurred_at so the interaction appears in
the correct historical location.

## 41. Activity and Timeline

Activity is the source interaction aggregate.

Timeline is a read-side projection introduced in chapter 09.

Conceptually:

~~~text
Activity
   |
activity.created / activity.updated
   |
   v
Timeline projection
   |
   v
Contact / Organization history
~~~

Participants and references determine which CRM entities can receive relevant
Activity history in timeline projections.

The full Timeline contract is deliberately deferred to chapter 09.

## 42. Activity events and audit

Facade mutations record:

~~~text
activity.created
activity.updated
~~~

The event payload contains the Activity type, while audit/change information
tracks changed field names.

With context:

~~~python
crm = CRM.memory().with_context(
    actor_id="sales-user-42",
    correlation_id="renewal-flow-001",
)
~~~

the interaction participates in the same actor/correlation trace as the rest of
the CRM workflow.

## 43. Transaction semantics

Through the CRM facade:

~~~text
open Unit of Work
      |
      v
ActivityService
      |
      v
ActivityRepository
      |
      +-- save Activity
      +-- stage domain event
      +-- stage audit change
      |
      v
commit
~~~

Events are dispatched after successful commit.

Activity persistence and Timeline projection can therefore participate in
transactional qualification instead of becoming disconnected history.

## 44. ActivityRepository contract

Adapter authors implement:

~~~text
get(ActivityId) -> Activity
find(ActivityId) -> Activity | None
save(Activity) -> None
list(ActivityQuery, OffsetPageRequest) -> Page[Activity]
~~~

The contract requires:

~~~text
exact total
deterministic pagination
occurred_at DESC, id ASC ordering
participant filtering
reference filtering
half-open occurrence windows
copy/state isolation
no implicit outer transaction commit
~~~

## 45. Complete Activity example

~~~python
from datetime import UTC, datetime

from pycrmkit import CRM
from pycrmkit.activities import (
    ActivityDirection,
    ActivityParticipant,
    ActivityQuery,
    ActivityType,
    ActivityUpdate,
)
from pycrmkit.core.pagination import OffsetPageRequest
from pycrmkit.core.references import EntityReference

crm = CRM.memory().with_context(
    actor_id="guide-user",
    correlation_id="activities-guide-001",
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

activity = crm.activities.log(
    type=ActivityType.MEETING,
    occurred_at=datetime(
        2026,
        9,
        27,
        15,
        0,
        tzinfo=UTC,
    ),
    subject="Quarterly account review",
    description="Reviewed roadmap and next steps.",
    direction=ActivityDirection.OUTBOUND,
    duration_seconds=3600,
    participants=(
        ActivityParticipant(
            reference=contact_ref,
            role="customer",
            is_primary=True,
        ),
    ),
    references=(organization_ref,),
    source="manual",
    external_id="meeting-2026-q3-ada",
)

assert activity.type is ActivityType.MEETING
assert activity.direction is ActivityDirection.OUTBOUND
assert activity.subject == "Quarterly account review"

updated = crm.activities.update(
    activity.id,
    ActivityUpdate(
        subject="Quarterly customer review",
        source="crm-ui",
    ),
)

assert updated.id == activity.id
assert updated.created_at == activity.created_at
assert updated.subject == "Quarterly customer review"

page = crm.activities.list(
    ActivityQuery(
        type=ActivityType.MEETING,
        participant=contact_ref,
        reference=organization_ref,
        direction=ActivityDirection.OUTBOUND,
        source="CRM-UI",
        external_id="meeting-2026-q3-ada",
        occurred_from=datetime(
            2026, 9, 1, tzinfo=UTC
        ),
        occurred_until=datetime(
            2026, 10, 1, tzinfo=UTC
        ),
    ),
    OffsetPageRequest(
        limit=10,
        offset=0,
    ),
)

assert page.total == 1
assert page.items == (updated,)
~~~

## 46. Complete historical-ordering example

~~~python
from datetime import UTC, datetime

crm = CRM.memory()

old = crm.activities.log(
    type="note",
    occurred_at=datetime(
        2024, 1, 1, tzinfo=UTC
    ),
    subject="Historical interaction",
)

newer = crm.activities.log(
    type="note",
    occurred_at=datetime(
        2026, 1, 1, tzinfo=UTC
    ),
    subject="Recent interaction",
)

page = crm.activities.list()

assert page.items[0] == newer
assert page.items[1] == old
~~~

Ordering follows the interaction time rather than insertion order.

## Common mistakes

### Using Activity for future work

Use Task for actionable work. Activity represents history.

### Treating created_at as interaction time

Use occurred_at for the business interaction timestamp.

### Importing historical data without occurred_at

The record will default to the current domain clock and lose historical
placement.

### Using naive datetimes

PyCRMKit rejects naive timestamps rather than guessing a timezone.

### Treating participants and references as synonyms

Participants took part in the interaction. References are associated CRM
entities.

### Repeating the same participant

One entity may appear only once in participants.

### Marking multiple primary participants

Only one participant may be primary.

### Logging context-free Activities

type/source/direction/metadata alone are not enough. Supply meaningful context.

### Using backend-specific queries

Use ActivityQuery so Memory, SQLAlchemy/PostgreSQL and other adapters preserve
the same observable semantics.

### Assuming Activity sends communication

Activity records interaction history. Provider actions live elsewhere.

## Testing Activity workflows

A useful application-level test focuses on public behavior:

~~~python
from pycrmkit import CRM
from pycrmkit.activities import (
    ActivityParticipant,
    ActivityQuery,
)
from pycrmkit.core.references import EntityReference

def test_contact_call_is_queryable() -> None:
    crm = CRM.memory()

    contact = crm.contacts.create(
        display_name="Ada Lovelace",
    )
    ref = EntityReference(
        kind="contact",
        id=contact.id,
    )

    activity = crm.activities.log(
        type="call",
        subject="Commercial follow-up",
        participants=(
            ActivityParticipant(
                reference=ref,
                is_primary=True,
            ),
        ),
    )

    page = crm.activities.list(
        ActivityQuery(
            participant=ref,
        ),
    )

    assert page.items == (activity,)
~~~

Repository-contract and PostgreSQL tests then prove the same semantics against
persistent adapters.

## What you learned

You can now explain and use:

- Activity and ActivityId;
- ActivityType;
- ActivityDirection;
- occurred_at vs created_at;
- historical interaction import;
- timezone-aware timestamp rules;
- subject/description normalization;
- duration validation;
- ActivityParticipant;
- participant roles and primary semantics;
- participants vs generic references;
- source/external_id/metadata;
- ActivityUpdate and UNSET/None semantics;
- ActivityQuery;
- participant/reference/type/direction/source/external-id filters;
- half-open time-window queries;
- reverse-chronological deterministic ordering;
- pagination;
- Activity events/audit;
- ActivityRepository and Unit of Work boundaries.

## Next

The next chapter is **08 - Tasks**.

Activities answer:

~~~text
What happened?
~~~

Tasks answer:

~~~text
What needs to happen?
~~~

Chapter 08 introduces Task lifecycle transitions such as create, start,
complete, reopen and cancel, together with due dates, priorities, assignees and
CRM references.
