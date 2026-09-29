from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from pycrmkit import CRM
from pycrmkit.core import FixedClock
from pycrmkit.exceptions import ValidationError
from pycrmkit.tasks import TaskStatus, TaskType

NOW = datetime(2026, 9, 29, 5, 30, tzinfo=UTC)


def test_task_type_defaults_to_general_and_supports_sales_actions() -> None:
    crm = CRM.memory(clock=FixedClock(NOW), webhook_auto_delivery=False)

    general = crm.tasks.create(title="Review account")
    call = crm.tasks.create(title="Call prospect", type=TaskType.CALL)
    email = crm.tasks.create(title="Send proposal", type="email")

    assert general.type is TaskType.GENERAL
    assert call.type is TaskType.CALL
    assert email.type is TaskType.EMAIL

    with pytest.raises(ValidationError) as exc_info:
        crm.tasks.create(title="Unknown", type="meeting")

    assert exc_info.value.code == "task.type.invalid"


def test_today_uses_local_timezone_half_open_day_bounds() -> None:
    crm = CRM.memory(clock=FixedClock(NOW), webhook_auto_delivery=False)

    before = crm.tasks.create(
        title="Before local day",
        due_at=datetime(2026, 9, 28, 21, 59, 59, tzinfo=UTC),
    )
    at_start = crm.tasks.create(
        title="At local start",
        due_at=datetime(2026, 9, 28, 22, 0, tzinfo=UTC),
    )
    during = crm.tasks.create(
        title="During local day",
        due_at=datetime(2026, 9, 29, 10, 0, tzinfo=UTC),
    )
    at_end = crm.tasks.create(
        title="At next local start",
        due_at=datetime(2026, 9, 29, 22, 0, tzinfo=UTC),
    )
    terminal = crm.tasks.create(
        title="Completed today",
        due_at=datetime(2026, 9, 29, 8, 0, tzinfo=UTC),
    )
    crm.tasks.complete(terminal.id)

    today = crm.tasks.today(timezone="Europe/Paris")

    assert before not in today.items
    assert at_start in today.items
    assert during in today.items
    assert at_end not in today.items
    assert all(item.status in {TaskStatus.OPEN, TaskStatus.IN_PROGRESS} for item in today.items)


def test_overdue_preserves_strict_v1_boundary() -> None:
    crm = CRM.memory(clock=FixedClock(NOW), webhook_auto_delivery=False)

    overdue = crm.tasks.create(title="Past", due_at=NOW - timedelta(seconds=1))
    exact = crm.tasks.create(title="Exact", due_at=NOW)
    future = crm.tasks.create(title="Future", due_at=NOW + timedelta(seconds=1))
    terminal = crm.tasks.create(title="Completed", due_at=NOW - timedelta(days=1))
    crm.tasks.complete(terminal.id)

    result = crm.tasks.overdue()

    assert result.items == (overdue,)
    assert exact not in result.items
    assert future not in result.items
    assert terminal not in result.items


def test_upcoming_and_unscheduled_exclude_terminal_tasks() -> None:
    crm = CRM.memory(clock=FixedClock(NOW), webhook_auto_delivery=False)

    future = crm.tasks.create(
        title="Tomorrow",
        type=TaskType.CALL,
        due_at=datetime(2026, 9, 30, 8, 0, tzinfo=UTC),
    )
    outside = crm.tasks.create(
        title="Outside horizon",
        due_at=datetime(2026, 10, 10, 8, 0, tzinfo=UTC),
    )
    unscheduled = crm.tasks.create(title="No date", type=TaskType.CALL)
    terminal_unscheduled = crm.tasks.create(title="Completed no date")
    crm.tasks.complete(terminal_unscheduled.id)

    upcoming = crm.tasks.upcoming(
        timezone="Europe/Paris",
        days=7,
        type=TaskType.CALL,
    )
    without_date = crm.tasks.unscheduled(type=TaskType.CALL)

    assert upcoming.items == (future,)
    assert outside not in upcoming.items
    assert without_date.items == (unscheduled,)


def test_work_queue_rejects_unknown_timezone() -> None:
    crm = CRM.memory(clock=FixedClock(NOW), webhook_auto_delivery=False)

    with pytest.raises(ValidationError) as exc_info:
        crm.tasks.today(timezone="Not/AZone")

    assert exc_info.value.code == "task.schedule.timezone.invalid"
