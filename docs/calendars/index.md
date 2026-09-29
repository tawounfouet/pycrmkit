# Business Calendars

> Introduced in PyCRMKit **1.1.0a3**.

Business Calendars are scheduling policy, not Task state.

~~~text
BusinessCalendar
    ↓
business-day calculation
    ↓
absolute due_at
    ↓
Task
~~~

## Model

A calendar defines:

~~~text
key
IANA timezone
working weekdays
optional working windows
holidays
exceptional working days
exceptional non-working days
default due time
revision
metadata
~~~

PyCRMKit does not ship an authoritative global holiday database. Applications
supply the dates or a provider outside the core.

## Business-day arithmetic

~~~python
from datetime import date

from pycrmkit.calendars import BusinessCalendar

calendar = BusinessCalendar(
    key="fr-sales",
    timezone="Europe/Paris",
)

calendar.add_business_days(
    date(2026, 9, 25),
    days=3,
)
# 2026-09-30
~~~

Policy precedence is:

~~~text
explicit working/non-working override
    >
holiday
    >
weekly schedule
~~~

## Runtime registry

The first implementation is runtime/application configuration:

~~~python
from pycrmkit import CRM
from pycrmkit.calendars import BusinessCalendar

crm = CRM.memory()

crm.calendars.register(
    BusinessCalendar(
        key="sales",
        timezone="Europe/Paris",
    )
)
~~~

A newer revision may replace the current revision for the same key.
Re-registering the same or an older revision fails explicitly.

## Resolve a Task due date

~~~python
from datetime import time

due_at = crm.calendars.due_in_business_days(
    "sales",
    days=3,
    local_time=time(9, 0),
)

task = crm.tasks.create(
    title="Call prospect",
    type="call",
    due_at=due_at,
)
~~~

`due_in_business_days()` resolves the local policy into the canonical UTC
instant stored by the Task aggregate.

Revising a calendar never moves existing Task due dates.

## Timezones and DST

Calendar timezones use Python `zoneinfo` / IANA identifiers such as:

~~~text
Europe/Paris
Africa/Douala
America/New_York
~~~

Nonexistent local wall-clock times during a DST jump are rejected rather than
silently shifted.

## Boundary

Business Calendar supports Task scheduling. It is not:

~~~text
an employee scheduling system
an appointment calendar
a holiday authority
a generic workflow scheduler
a Cadence engine
~~~

Full Cadence execution remains deferred.
