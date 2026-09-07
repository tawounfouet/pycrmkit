"""Task entity lifecycle and validation invariants."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from pycrmkit.contacts import ContactId
from pycrmkit.core.references import EntityReference
from pycrmkit.exceptions import InvalidStateError, ValidationError
from pycrmkit.tasks import Task, TaskId, TaskPriority, TaskStatus

NOW = datetime(2026, 9, 7, 9, 30, tzinfo=UTC)


def contact_ref(value: int = 1) -> EntityReference:
    return EntityReference(
        "contact",
        ContactId(UUID(f"00000000-0000-4000-8000-{value:012d}")),
    )


def task(**changes) -> Task:
    values = {
        "id": TaskId(UUID("00000000-0000-4000-8000-000000001001")),
        "created_at": NOW,
        "updated_at": NOW,
        "title": "Prepare renewal proposal",
    }
    values.update(changes)
    return Task(**values)


def test_task_statuses_match_phase_scope() -> None:
    assert {item.value for item in TaskStatus} == {
        "open",
        "in_progress",
        "completed",
        "cancelled",
    }


def test_task_priorities_have_stable_ordering() -> None:
    assert [item.name for item in TaskPriority] == ["LOW", "NORMAL", "HIGH", "URGENT"]
    assert TaskPriority.URGENT > TaskPriority.HIGH > TaskPriority.NORMAL > TaskPriority.LOW


def test_task_normalizes_title_and_identity_fields() -> None:
    item = task(
        title="  Prepare   renewal proposal ",
        priority="high",
        owner_id=" owner-42 ",
        assignee_id=" sales-1 ",
        source=" manual ",
        external_id=" ext-1 ",
    )

    assert item.title == "Prepare renewal proposal"
    assert item.priority is TaskPriority.HIGH
    assert item.owner_id == "owner-42"
    assert item.assignee_id == "sales-1"
    assert item.source == "manual"
    assert item.external_id == "ext-1"


def test_task_due_date_may_be_historical_or_already_overdue() -> None:
    due = NOW - timedelta(days=10)
    item = task(due_at=due)

    assert item.due_at == due
    assert item.is_overdue(NOW) is True


def test_completed_and_cancelled_tasks_are_not_overdue() -> None:
    item = task(due_at=NOW - timedelta(days=1))
    item.complete(NOW)

    assert item.is_overdue(NOW + timedelta(days=1)) is False


def test_task_rejects_blank_title_and_duplicate_references() -> None:
    with pytest.raises(ValidationError, match="title"):
        task(title="   ")
    with pytest.raises(ValidationError, match="unique"):
        task(references=(contact_ref(), contact_ref()))


def test_start_complete_and_reopen_manage_lifecycle_timestamps() -> None:
    item = task()
    started_at = NOW + timedelta(minutes=5)
    completed_at = NOW + timedelta(minutes=10)
    reopened_at = NOW + timedelta(minutes=15)

    item.start(started_at)
    assert item.status is TaskStatus.IN_PROGRESS
    assert item.started_at == started_at

    item.complete(completed_at)
    assert item.status is TaskStatus.COMPLETED
    assert item.completed_at == completed_at
    assert item.started_at == started_at

    item.reopen(reopened_at)
    assert item.status is TaskStatus.OPEN
    assert item.started_at is None
    assert item.completed_at is None
    assert item.cancelled_at is None


def test_cancel_and_reopen_manage_cancelled_timestamp() -> None:
    item = task()
    item.cancel(NOW + timedelta(minutes=1))

    assert item.status is TaskStatus.CANCELLED
    assert item.cancelled_at == NOW + timedelta(minutes=1)

    item.reopen(NOW + timedelta(minutes=2))
    assert item.status is TaskStatus.OPEN
    assert item.cancelled_at is None


def test_invalid_transitions_raise_typed_state_error() -> None:
    item = task()
    with pytest.raises(InvalidStateError, match="open to open"):
        item.reopen(NOW + timedelta(minutes=1))

    item.complete(NOW + timedelta(minutes=2))
    with pytest.raises(InvalidStateError, match="completed to in_progress"):
        item.start(NOW + timedelta(minutes=3))


def test_transition_time_cannot_precede_creation() -> None:
    item = task()
    with pytest.raises(ValidationError, match="earlier than created_at"):
        item.start(NOW - timedelta(seconds=1))
