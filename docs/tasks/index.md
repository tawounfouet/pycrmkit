# Tasks

`0.2.0a2` introduces first-class CRM action items on top of the stable `0.1` core and the `0.2.0a1` Activities domain.

A Task represents work to perform, not an activity that already happened. Activities and Tasks therefore remain separate aggregates even when a completed task later produces an activity record.

## Lifecycle

```text
open
 ├── start ───────────────► in_progress
 ├── complete ────────────► completed
 └── cancel ──────────────► cancelled

in_progress
 ├── complete ────────────► completed
 └── cancel ──────────────► cancelled

completed ── reopen ──────► open
cancelled ── reopen ──────► open
```

Status is deliberately excluded from `TaskUpdate`. Applications must use explicit transition methods so adapters and future HTTP APIs cannot bypass lifecycle invariants.

## Model

```text
TaskId
title
status
priority
description
due_at
owner_id
assignee_id
references
source
external_id
metadata
started_at
completed_at
cancelled_at
created_at
updated_at
```

Priorities are ordered:

```text
low < normal < high < urgent
```

`due_at` may be in the past. This supports importing already-overdue work without rewriting history.

## Facade

```python
from datetime import timedelta

from pycrmkit import CRM
from pycrmkit.core.references import EntityReference

crm = CRM.memory()
contact = crm.contacts.create(first_name="Ada")
contact_ref = EntityReference("contact", contact.id)

item = crm.tasks.create(
    title="Prepare renewal proposal",
    priority="high",
    assignee_id="seller-7",
    references=(contact_ref,),
)

item = crm.tasks.start(item.id)
item = crm.tasks.complete(item.id)
```

Available facade operations:

```text
create
get
update
start
complete
cancel
reopen
list
```

## Queries

`TaskQuery` supports status, priority, owner, assignee, related entity, source/external ID, due-date windows and overdue-at filtering.

Due windows use a half-open interval:

```text
due_from <= due_at < due_until
```

Repository ordering is deterministic:

```text
due_at ASC
undated tasks last
created_at DESC
id ASC
```

An overdue task is an `open` or `in_progress` task whose `due_at` is strictly before the requested instant. Completed and cancelled tasks are never considered overdue.

## Events and audit

Facade mutations emit after commit:

```text
task.created
task.updated
task.started
task.completed
task.cancelled
task.reopened
```

Audit entries are committed atomically with task state. The facade records changed field names rather than copying task titles/descriptions into audit metadata by default.
