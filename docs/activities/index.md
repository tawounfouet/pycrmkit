# Activities

`0.2.0a1` introduces the first CRM interaction-history domain.

An `Activity` records something that happened during a customer relationship without coupling the CRM core to an email, telephony, calendar, document-storage, or workflow provider.

Base types:

```text
email
call
meeting
note
message
document
event
custom
```

Example:

```python
from pycrmkit import CRM
from pycrmkit.activities import ActivityParticipant
from pycrmkit.core.references import EntityReference

crm = CRM.memory()
contact = crm.contacts.create(first_name="Ada", last_name="Lovelace")

contact_ref = EntityReference("contact", contact.id)

activity = crm.activities.log(
    type="call",
    subject="Commercial follow-up",
    direction="outbound",
    duration_seconds=480,
    participants=(
        ActivityParticipant(
            contact_ref,
            role="customer",
            is_primary=True,
        ),
    ),
)
```

## Model

An activity stores:

```text
ActivityId
type
occurred_at
subject
description
direction
duration_seconds
participants
references
source
external_id
metadata
created_at
updated_at
```

`occurred_at` is independent from `created_at`. A CRM may import an interaction from years earlier while preserving the time at which it actually occurred.

Participants use `ActivityParticipant(EntityReference(...))`. Additional CRM objects can be attached through `references` without loading or embedding those aggregates.

## Direction

Directional activities may use:

```text
inbound
outbound
internal
```

Direction is optional because activities such as notes and document references may not have a meaningful direction.

## Listing

```python
from pycrmkit.activities import ActivityQuery, ActivityType

page = crm.activities.list(
    ActivityQuery(
        participant=contact_ref,
        type=ActivityType.CALL,
    )
)
```

Repository ordering is deterministic:

```text
occurred_at DESC
id ASC
```

Time-window queries use a half-open interval:

```text
occurred_from <= occurred_at < occurred_until
```

## Events and audit

Facade mutations produce:

```text
activity.created
activity.updated
```

The events are dispatched only after commit. Audit history is committed atomically with the activity mutation and stores changed field names rather than raw interaction content by default.

## Scope boundary

`0.2.0a1` stores CRM interaction history. It does not send email, place calls, store document bytes, schedule meetings, or orchestrate workflows. Provider-specific communication behavior remains in later milestones.
