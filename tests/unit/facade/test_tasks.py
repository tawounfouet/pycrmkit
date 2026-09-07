"""Tasks facade transaction/event/audit behavior."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from pycrmkit import CRM
from pycrmkit.core.time import FixedClock
from pycrmkit.events import DomainEvent
from pycrmkit.exceptions import InvalidStateError
from pycrmkit.tasks import TaskPriority, TaskStatus, TaskUpdate

NOW = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)


def test_task_facade_creates_and_emits_post_commit_event_and_audit() -> None:
    crm = CRM.memory(clock=FixedClock(NOW)).with_context(
        actor_id="sales-user",
        correlation_id="corr-task",
    )
    events: list[DomainEvent] = []
    crm.events.subscribe("task.created", events.append)

    task = crm.tasks.create(
        title="Prepare renewal",
        priority="high",
        assignee_id="seller-1",
    )

    assert crm.tasks.get(task.id) == task
    assert task.priority is TaskPriority.HIGH
    assert len(events) == 1
    assert events[0].aggregate_id == str(task.id)
    assert events[0].payload["status"] == "open"
    assert events[0].actor_id == "sales-user"
    assert events[0].correlation_id == "corr-task"

    audit = crm.audit.by_correlation("corr-task")
    assert audit.total == 1
    assert audit.items[0].action == "task.created"
    assert "Prepare renewal" not in repr(audit.items[0].changes)


def test_task_facade_transitions_emit_distinct_events() -> None:
    clock = FixedClock(NOW)
    crm = CRM.memory(clock=clock).with_context(correlation_id="corr-transitions")
    events: list[DomainEvent] = []
    for event_type in ("task.started", "task.completed", "task.reopened", "task.cancelled"):
        crm.events.subscribe(event_type, events.append)

    task = crm.tasks.create(title="Follow up")
    clock.advance(timedelta(minutes=1))
    task = crm.tasks.start(task.id)
    clock.advance(timedelta(minutes=1))
    task = crm.tasks.complete(task.id)
    clock.advance(timedelta(minutes=1))
    task = crm.tasks.reopen(task.id)
    clock.advance(timedelta(minutes=1))
    task = crm.tasks.cancel(task.id)

    assert task.status is TaskStatus.CANCELLED
    assert [str(event.type) for event in events] == [
        "task.started",
        "task.completed",
        "task.reopened",
        "task.cancelled",
    ]
    actions = {entry.action for entry in crm.audit.by_correlation("corr-transitions").items}
    assert actions == {
        "task.created",
        "task.started",
        "task.completed",
        "task.reopened",
        "task.cancelled",
    }


def test_task_status_cannot_be_patched_around_transition_rules() -> None:
    crm = CRM.memory(clock=FixedClock(NOW))
    task = crm.tasks.create(title="Protected lifecycle")
    task = crm.tasks.complete(task.id)

    with pytest.raises(InvalidStateError):
        crm.tasks.complete(task.id)

    updated = crm.tasks.update(task.id, TaskUpdate(title="Still completed"))
    assert updated.status is TaskStatus.COMPLETED
