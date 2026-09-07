"""Persistence contract for Task aggregates."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.tasks.entities import Task, TaskId
from pycrmkit.tasks.queries import TaskQuery


@runtime_checkable
class TaskRepository(Protocol):
    """Backend-neutral repository contract for CRM tasks.

    Listing uses ``due_at ASC (undated last), created_at DESC, id ASC``.
    """

    def get(self, task_id: TaskId) -> Task:
        """Return a task or raise NotFoundError."""

    def find(self, task_id: TaskId) -> Task | None:
        """Return a task or None."""

    def save(self, task: Task) -> None:
        """Persist current task state without committing an outer transaction."""

    def list(
        self,
        query: TaskQuery,
        page: OffsetPageRequest,
    ) -> Page[Task]:
        """List tasks with deterministic due-date ordering."""
