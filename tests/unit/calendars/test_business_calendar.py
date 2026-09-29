from __future__ import annotations

from datetime import UTC, date, datetime, time

import pytest

from pycrmkit import CRM
from pycrmkit.calendars import BusinessCalendar
from pycrmkit.core import FixedClock
from pycrmkit.exceptions import ConflictError, ValidationError

NOW = datetime(2026, 9, 25, 14, 0, tzinfo=UTC)


def test_business_day_arithmetic_skips_weekend_and_holiday() -> None:
    calendar = BusinessCalendar(
        key="fr-sales",
        timezone="Europe/Paris",
        holidays=frozenset({date(2026, 9, 28)}),
    )

    assert calendar.add_business_days(date(2026, 9, 25), days=1) == date(
        2026, 9, 29
    )
    assert calendar.add_business_days(date(2026, 9, 25), days=3) == date(
        2026, 10, 1
    )


def test_exceptional_working_day_overrides_weekly_schedule_and_holiday() -> None:
    saturday = date(2026, 9, 26)
    calendar = BusinessCalendar(
        key="special",
        timezone="Europe/Paris",
        holidays=frozenset({saturday}),
        exceptional_working_days=frozenset({saturday}),
    )

    assert calendar.is_business_day(saturday) is True
    assert calendar.add_business_days(date(2026, 9, 25), days=1) == saturday


def test_resolve_due_at_uses_iana_timezone_and_rejects_nonexistent_dst_time() -> None:
    calendar = BusinessCalendar(
        key="paris",
        timezone="Europe/Paris",
        default_due_time=time(9, 0),
    )

    assert calendar.resolve_due_at(date(2026, 9, 29)) == datetime(
        2026, 9, 29, 7, 0, tzinfo=UTC
    )

    with pytest.raises(ValidationError) as exc_info:
        calendar.resolve_due_at(
            date(2026, 3, 29),
            local_time=time(2, 30),
        )

    assert exc_info.value.code == "task.schedule.invalid_local_time"


def test_calendar_revision_does_not_mutate_existing_task_due_at() -> None:
    crm = CRM.memory(clock=FixedClock(NOW), webhook_auto_delivery=False)
    v1 = BusinessCalendar(
        key="sales",
        timezone="Europe/Paris",
        revision=1,
    )
    crm.calendars.register(v1)
    due_at = crm.calendars.due_in_business_days("sales", days=1)
    task = crm.tasks.create(title="Call prospect", due_at=due_at)

    v2 = BusinessCalendar(
        key="sales",
        timezone="Europe/Paris",
        revision=2,
        holidays=frozenset({date(2026, 9, 28)}),
    )
    crm.calendars.register(v2)

    assert crm.tasks.get(task.id).due_at == due_at
    assert crm.calendars.due_in_business_days("sales", days=1) != due_at


def test_calendar_registry_rejects_non_increasing_revision() -> None:
    crm = CRM.memory(webhook_auto_delivery=False)
    crm.calendars.register(
        BusinessCalendar(key="sales", timezone="Europe/Paris", revision=2)
    )

    with pytest.raises(ConflictError) as exc_info:
        crm.calendars.register(
            BusinessCalendar(key="sales", timezone="Europe/Paris", revision=2)
        )

    assert exc_info.value.code == "business_calendar.revision.conflict"
