"""Run Task repository contracts against the official Memory adapter."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from pycrmkit.contacts import ContactId
from pycrmkit.core.references import EntityReference
from pycrmkit.storage.memory import MemoryTaskRepository
from pycrmkit.tasks import Task, TaskId, TaskPriority, TaskRepository, TaskStatus

from ...contracts.tasks_repository import TaskRepositoryContract

NOW = datetime(2026, 9, 7, 11, 0, tzinfo=UTC)


@pytest.fixture
def now() -> datetime:
    return NOW


@pytest.fixture
def related_reference() -> EntityReference:
    return EntityReference(
        "contact",
        ContactId(UUID("00000000-0000-4000-8000-000000001201")),
    )


@pytest.fixture
def repository() -> TaskRepository:
    repository = MemoryTaskRepository()
    assert isinstance(repository, TaskRepository)
    return repository


@pytest.fixture
def task(related_reference) -> Task:
    return Task(
        id=TaskId(UUID("00000000-0000-4000-8000-000000001211")),
        created_at=NOW,
        updated_at=NOW,
        title="Overdue renewal",
        priority=TaskPriority.HIGH,
        due_at=NOW - timedelta(days=1),
        assignee_id="seller-1",
        references=(related_reference,),
    )


@pytest.fixture
def second_task() -> Task:
    return Task(
        id=TaskId(UUID("00000000-0000-4000-8000-000000001212")),
        created_at=NOW,
        updated_at=NOW,
        title="Future follow-up",
        priority=TaskPriority.NORMAL,
        due_at=NOW + timedelta(days=1),
    )


@pytest.fixture
def undated_task() -> Task:
    return Task(
        id=TaskId(UUID("00000000-0000-4000-8000-000000001213")),
        created_at=NOW,
        updated_at=NOW,
        title="No due date",
    )


@pytest.fixture
def completed_task() -> Task:
    item = Task(
        id=TaskId(UUID("00000000-0000-4000-8000-000000001214")),
        created_at=NOW,
        updated_at=NOW,
        title="Completed task",
        due_at=NOW - timedelta(days=2),
        assignee_id="seller-1",
    )
    item.complete(NOW)
    return item


@pytest.fixture
def missing_task_id() -> TaskId:
    return TaskId(UUID("00000000-0000-4000-8000-000000009998"))


class TestMemoryTaskRepository(TaskRepositoryContract):
    """Official Memory adapter must satisfy the reusable Task contract."""


def test_task_repository_isolates_saved_and_loaded_mutations(task: Task) -> None:
    repository = MemoryTaskRepository()
    repository.save(task)

    task.title = "mutated-after-save"
    loaded = repository.get(task.id)
    assert loaded.title == "Overdue renewal"

    loaded.title = "mutated-after-read"
    assert repository.get(task.id).title == "Overdue renewal"
