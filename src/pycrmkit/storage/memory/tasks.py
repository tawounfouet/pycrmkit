"""Official in-memory Task repository."""

from __future__ import annotations

from copy import deepcopy
from datetime import MAXYEAR, UTC, datetime

from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.exceptions import NotFoundError
from pycrmkit.storage.memory._state import _MemoryState
from pycrmkit.tasks import Task, TaskId, TaskQuery, TaskRepository


class MemoryTaskRepository(TaskRepository):
    """Copy-isolated Task repository backed by one memory state snapshot."""

    def __init__(self, state: _MemoryState | None = None) -> None:
        self._state = state or _MemoryState()

    def get(self, task_id: TaskId) -> Task:
        task = self._state.tasks.get(task_id)
        if task is None:
            raise NotFoundError(
                "task not found",
                code="task.not_found",
                context={"task_id": str(task_id)},
            )
        return deepcopy(task)

    def find(self, task_id: TaskId) -> Task | None:
        task = self._state.tasks.get(task_id)
        return deepcopy(task) if task is not None else None

    def save(self, task: Task) -> None:
        self._state.tasks[task.id] = deepcopy(task)

    def list(
        self,
        query: TaskQuery,
        page: OffsetPageRequest,
    ) -> Page[Task]:
        tasks = list(self._state.tasks.values())
        if query.status is not None:
            tasks = [item for item in tasks if item.status is query.status]
        if query.priority is not None:
            tasks = [item for item in tasks if item.priority is query.priority]
        if query.owner_id is not None:
            tasks = [item for item in tasks if item.owner_id == query.owner_id]
        if query.assignee_id is not None:
            tasks = [item for item in tasks if item.assignee_id == query.assignee_id]
        if query.reference is not None:
            tasks = [item for item in tasks if query.reference in item.references]
        if query.source is not None:
            tasks = [
                item
                for item in tasks
                if item.source is not None and item.source.casefold() == query.source
            ]
        if query.external_id is not None:
            tasks = [item for item in tasks if item.external_id == query.external_id]
        if query.due_from is not None:
            tasks = [
                item
                for item in tasks
                if item.due_at is not None and item.due_at >= query.due_from
            ]
        if query.due_until is not None:
            tasks = [
                item
                for item in tasks
                if item.due_at is not None and item.due_at < query.due_until
            ]
        if query.overdue_at is not None:
            tasks = [item for item in tasks if item.is_overdue(query.overdue_at)]

        undated = datetime(MAXYEAR, 12, 31, 23, 59, 59, 999999, tzinfo=UTC)
        tasks.sort(key=lambda item: item.id)
        tasks.sort(key=lambda item: item.created_at, reverse=True)
        tasks.sort(key=lambda item: item.due_at or undated)
        total = len(tasks)
        selected = tasks[page.offset : page.offset + page.limit]
        return Page(
            items=tuple(deepcopy(selected)),
            limit=page.limit,
            offset=page.offset,
            total=total,
        )
