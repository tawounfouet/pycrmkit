"""Task service lifecycle behavior."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from pycrmkit.core.time import FixedClock
from pycrmkit.storage.memory import MemoryTaskRepository
from pycrmkit.tasks import TaskPriority, TaskQuery, TaskService, TaskStatus, TaskUpdate

NOW = datetime(2026, 9, 7, 10, 30, tzinfo=UTC)


class FixedIDFactory:
    def new(self, id_type):
        return id_type(UUID("00000000-0000-4000-8000-000000001101"))


def service(clock: FixedClock | None = None) -> TaskService:
    return TaskService(
        MemoryTaskRepository(),
        id_factory=FixedIDFactory(),
        clock=clock or FixedClock(NOW),
    )


def test_create_defaults_to_open_normal_priority() -> None:
    tasks = service()

    item = tasks.create(title="Call customer")

    assert item.status is TaskStatus.OPEN
    assert item.priority is TaskPriority.NORMAL
    assert item.created_at == NOW
    assert tasks.get(item.id) == item


def test_update_preserves_status_and_identity() -> None:
    clock = FixedClock(NOW)
    tasks = service(clock)
    item = tasks.create(title="Call customer")
    tasks.start(item.id)
    clock.advance(timedelta(minutes=5))

    updated = tasks.update(
        item.id,
        TaskUpdate(title="Call strategic customer", priority="urgent"),
    )

    assert updated.id == item.id
    assert updated.status is TaskStatus.IN_PROGRESS
    assert updated.started_at == NOW
    assert updated.priority is TaskPriority.URGENT
    assert updated.updated_at == NOW + timedelta(minutes=5)


def test_explicit_transitions_persist_state() -> None:
    clock = FixedClock(NOW)
    tasks = service(clock)
    item = tasks.create(title="Send proposal")

    started = tasks.start(item.id)
    assert started.status is TaskStatus.IN_PROGRESS

    clock.advance(timedelta(minutes=1))
    completed = tasks.complete(item.id)
    assert completed.status is TaskStatus.COMPLETED

    clock.advance(timedelta(minutes=1))
    reopened = tasks.reopen(item.id)
    assert reopened.status is TaskStatus.OPEN


def test_list_delegates_task_query() -> None:
    tasks = service()
    tasks.create(title="Low task", priority="low")

    page = tasks.list(TaskQuery(priority="low"))

    assert page.total == 1
    assert page.items[0].title == "Low task"
