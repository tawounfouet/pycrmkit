"""Task participation in MemoryUnitOfWork transactions."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from pycrmkit.exceptions import NotFoundError
from pycrmkit.storage.memory import MemoryStore, MemoryUnitOfWork
from pycrmkit.tasks import Task, TaskId

NOW = datetime(2026, 9, 7, 11, 30, tzinfo=UTC)


def _task() -> Task:
    return Task(
        id=TaskId(UUID("00000000-0000-4000-8000-000000001301")),
        created_at=NOW,
        updated_at=NOW,
        title="Transactional task",
    )


def test_task_commits_with_shared_memory_uow() -> None:
    store = MemoryStore()
    task = _task()

    with MemoryUnitOfWork(store) as uow:
        uow.tasks.save(task)
        uow.commit()

    with MemoryUnitOfWork(store) as uow:
        assert uow.tasks.get(task.id) == task


def test_task_rolls_back_without_commit() -> None:
    store = MemoryStore()
    task = _task()

    with MemoryUnitOfWork(store) as uow:
        uow.tasks.save(task)

    with MemoryUnitOfWork(store) as uow:
        with pytest.raises(NotFoundError):
            uow.tasks.get(task.id)
