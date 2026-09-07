"""Application service for Task lifecycle operations."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import TypeVar

from pycrmkit.core.ids import IDFactory, UUID4Factory
from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.core.references import EntityReference
from pycrmkit.core.time import Clock, SystemClock
from pycrmkit.tasks.dto import TaskUpdate, UnsetType
from pycrmkit.tasks.entities import Task, TaskId, TaskPriority, parse_priority
from pycrmkit.tasks.queries import TaskQuery
from pycrmkit.tasks.repository import TaskRepository

T = TypeVar("T")


@dataclass(slots=True)
class TaskService:
    """Framework-agnostic service enforcing Task lifecycle semantics."""

    repository: TaskRepository
    id_factory: IDFactory = field(default_factory=UUID4Factory)
    clock: Clock = field(default_factory=SystemClock)

    def create(
        self,
        *,
        title: str,
        description: str | None = None,
        priority: TaskPriority | str | int = TaskPriority.NORMAL,
        due_at: datetime | None = None,
        owner_id: str | None = None,
        assignee_id: str | None = None,
        references: Sequence[EntityReference] = (),
        source: str | None = None,
        external_id: str | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> Task:
        now = self.clock.now()
        task = Task(
            id=self.id_factory.new(TaskId),
            created_at=now,
            updated_at=now,
            title=title,
            priority=parse_priority(priority),
            description=description,
            due_at=due_at,
            owner_id=owner_id,
            assignee_id=assignee_id,
            references=tuple(references),
            source=source,
            external_id=external_id,
            metadata=dict(metadata or {}),
        )
        self.repository.save(task)
        return task

    def get(self, task_id: TaskId) -> Task:
        return self.repository.get(task_id)

    def update(self, task_id: TaskId, changes: TaskUpdate) -> Task:
        current = self.repository.get(task_id)
        candidate = Task(
            id=current.id,
            created_at=current.created_at,
            updated_at=self.clock.now(),
            title=self._value(changes.title, current.title),
            status=current.status,
            priority=parse_priority(self._value(changes.priority, current.priority)),
            description=self._value(changes.description, current.description),
            due_at=self._value(changes.due_at, current.due_at),
            owner_id=self._value(changes.owner_id, current.owner_id),
            assignee_id=self._value(changes.assignee_id, current.assignee_id),
            references=self._value(changes.references, current.references),
            source=self._value(changes.source, current.source),
            external_id=self._value(changes.external_id, current.external_id),
            metadata=self._value(changes.metadata, current.metadata),
            started_at=current.started_at,
            completed_at=current.completed_at,
            cancelled_at=current.cancelled_at,
        )
        self.repository.save(candidate)
        return candidate

    def start(self, task_id: TaskId) -> Task:
        task = self.repository.get(task_id)
        task.start(self.clock.now())
        self.repository.save(task)
        return task

    def complete(self, task_id: TaskId) -> Task:
        task = self.repository.get(task_id)
        task.complete(self.clock.now())
        self.repository.save(task)
        return task

    def cancel(self, task_id: TaskId) -> Task:
        task = self.repository.get(task_id)
        task.cancel(self.clock.now())
        self.repository.save(task)
        return task

    def reopen(self, task_id: TaskId) -> Task:
        task = self.repository.get(task_id)
        task.reopen(self.clock.now())
        self.repository.save(task)
        return task

    def list(
        self,
        query: TaskQuery | None = None,
        page: OffsetPageRequest | None = None,
    ) -> Page[Task]:
        return self.repository.list(
            query or TaskQuery(),
            page or OffsetPageRequest(),
        )

    @staticmethod
    def _value(value: T | UnsetType, current: T) -> T:
        return current if isinstance(value, UnsetType) else value
