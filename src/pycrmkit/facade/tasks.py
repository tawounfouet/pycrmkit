"""Tasks facade namespace."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime

from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.core.references import EntityReference
from pycrmkit.facade._runtime import CRMRuntime, present_fields, revision_fields
from pycrmkit.tasks import (
    Task,
    TaskId,
    TaskPriority,
    TaskQuery,
    TaskService,
    TaskUpdate,
)


class TasksAPI:
    """Transactional facade namespace for CRM action items."""

    def __init__(self, runtime: CRMRuntime) -> None:
        self._runtime = runtime

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
        with self._runtime.uow_factory() as uow:
            task = TaskService(
                uow.tasks,
                id_factory=self._runtime.id_factory,
                clock=self._runtime.clock,
            ).create(
                title=title,
                description=description,
                priority=priority,
                due_at=due_at,
                owner_id=owner_id,
                assignee_id=assignee_id,
                references=references,
                source=source,
                external_id=external_id,
                metadata=metadata,
            )
            self._runtime.record_change(
                uow,
                event_type="task.created",
                aggregate_type="task",
                aggregate_id=task.id,
                changes={
                    "fields": present_fields(
                        {
                            "title": title,
                            "description": description,
                            "priority": priority,
                            "due_at": due_at,
                            "owner_id": owner_id,
                            "assignee_id": assignee_id,
                            "references": tuple(references),
                            "source": source,
                            "external_id": external_id,
                            "metadata": metadata or {},
                        }
                    )
                },
                payload={
                    "status": task.status.value,
                    "priority": task.priority.name.lower(),
                },
            )
            uow.commit()
            return task

    def get(self, task_id: TaskId) -> Task:
        with self._runtime.uow_factory() as uow:
            return uow.tasks.get(task_id)

    def update(self, task_id: TaskId, changes: TaskUpdate) -> Task:
        with self._runtime.uow_factory() as uow:
            task = TaskService(
                uow.tasks,
                id_factory=self._runtime.id_factory,
                clock=self._runtime.clock,
            ).update(task_id, changes)
            self._runtime.record_change(
                uow,
                event_type="task.updated",
                aggregate_type="task",
                aggregate_id=task.id,
                changes={"fields": revision_fields(changes)},
                payload={
                    "status": task.status.value,
                    "priority": task.priority.name.lower(),
                },
            )
            uow.commit()
            return task

    def start(self, task_id: TaskId) -> Task:
        return self._transition(task_id, "started")

    def complete(self, task_id: TaskId) -> Task:
        return self._transition(task_id, "completed")

    def cancel(self, task_id: TaskId) -> Task:
        return self._transition(task_id, "cancelled")

    def reopen(self, task_id: TaskId) -> Task:
        return self._transition(task_id, "reopened")

    def list(
        self,
        query: TaskQuery | None = None,
        page: OffsetPageRequest | None = None,
    ) -> Page[Task]:
        with self._runtime.uow_factory() as uow:
            return TaskService(uow.tasks).list(query, page)

    def _transition(self, task_id: TaskId, action: str) -> Task:
        with self._runtime.uow_factory() as uow:
            service = TaskService(
                uow.tasks,
                id_factory=self._runtime.id_factory,
                clock=self._runtime.clock,
            )
            if action == "started":
                task = service.start(task_id)
            elif action == "completed":
                task = service.complete(task_id)
            elif action == "cancelled":
                task = service.cancel(task_id)
            elif action == "reopened":
                task = service.reopen(task_id)
            else:  # pragma: no cover - private exhaustive guard
                raise AssertionError(f"unsupported task transition: {action}")
            self._runtime.record_change(
                uow,
                event_type=f"task.{action}",
                aggregate_type="task",
                aggregate_id=task.id,
                changes={"fields": ["status"]},
                payload={
                    "status": task.status.value,
                    "priority": task.priority.name.lower(),
                },
            )
            uow.commit()
            return task
