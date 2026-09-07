"""Reusable TaskRepository behavioral contract suite."""

from __future__ import annotations

import pytest

from pycrmkit.core import OffsetPageRequest
from pycrmkit.exceptions import NotFoundError
from pycrmkit.tasks import Task, TaskPriority, TaskQuery, TaskRepository, TaskStatus


class TaskRepositoryContract:
    """Assertions every TaskRepository adapter must satisfy."""

    def test_save_and_get(self, repository: TaskRepository, task: Task) -> None:
        repository.save(task)
        assert repository.get(task.id) == task

    def test_missing_get_raises_and_find_returns_none(
        self,
        repository: TaskRepository,
        missing_task_id,
    ) -> None:
        with pytest.raises(NotFoundError):
            repository.get(missing_task_id)
        assert repository.find(missing_task_id) is None

    def test_save_replaces_current_state(
        self,
        repository: TaskRepository,
        task: Task,
    ) -> None:
        repository.save(task)
        task.source = "updated"
        repository.save(task)

        assert repository.get(task.id).source == "updated"

    def test_list_is_due_ordered_and_exactly_paginated(
        self,
        repository: TaskRepository,
        task: Task,
        second_task: Task,
        undated_task: Task,
    ) -> None:
        repository.save(undated_task)
        repository.save(second_task)
        repository.save(task)

        first = repository.list(TaskQuery(), OffsetPageRequest(limit=1, offset=0))
        second = repository.list(TaskQuery(), OffsetPageRequest(limit=1, offset=1))
        third = repository.list(TaskQuery(), OffsetPageRequest(limit=1, offset=2))

        assert first.items == (task,)
        assert second.items == (second_task,)
        assert third.items == (undated_task,)
        assert first.total == 3
        assert first.has_next is True
        assert third.has_previous is True

    def test_list_filters_status_priority_and_assignee(
        self,
        repository: TaskRepository,
        task: Task,
        completed_task: Task,
    ) -> None:
        repository.save(task)
        repository.save(completed_task)

        page = repository.list(
            TaskQuery(
                status=TaskStatus.OPEN,
                priority=TaskPriority.HIGH,
                assignee_id="seller-1",
            ),
            OffsetPageRequest(),
        )

        assert page.items == (task,)

    def test_list_filters_reference_due_window_and_overdue(
        self,
        repository: TaskRepository,
        task: Task,
        second_task: Task,
        related_reference,
        now,
    ) -> None:
        repository.save(task)
        repository.save(second_task)

        by_reference = repository.list(
            TaskQuery(reference=related_reference),
            OffsetPageRequest(),
        )
        overdue = repository.list(
            TaskQuery(overdue_at=now),
            OffsetPageRequest(),
        )

        assert by_reference.items == (task,)
        assert overdue.items == (task,)
