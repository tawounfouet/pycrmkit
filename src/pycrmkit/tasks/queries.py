"""Backend-independent Task query expressions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from datetime import datetime

from pycrmkit.core.references import EntityReference
from pycrmkit.core.time import as_utc
from pycrmkit.exceptions import ValidationError
from pycrmkit.tasks.entities import (
    TaskPriority,
    TaskStatus,
    TaskType,
    parse_priority,
    parse_task_type,
)


class TaskOrdering(StrEnum):
    """Deterministic ordering contracts for raw lists and sales work queues."""

    DEFAULT = "default"
    DUE_PRIORITY_CREATED = "due_priority_created"
    DUE_PRIORITY = "due_priority"
    PRIORITY_CREATED = "priority_created"


@dataclass(frozen=True, slots=True)
class TaskQuery:
    """Portable task filtering independent from ORM/query implementations."""

    status: TaskStatus | None = None
    priority: TaskPriority | str | int | None = None
    owner_id: str | None = None
    assignee_id: str | None = None
    reference: EntityReference | None = None
    source: str | None = None
    external_id: str | None = None
    due_from: datetime | None = None
    due_until: datetime | None = None
    overdue_at: datetime | None = None
    type: TaskType | str | None = None
    unresolved_only: bool = False
    unscheduled_only: bool = False
    ordering: TaskOrdering = TaskOrdering.DEFAULT

    def __post_init__(self) -> None:
        if self.status is not None:
            object.__setattr__(self, "status", TaskStatus(self.status))
        if self.type is not None:
            object.__setattr__(self, "type", parse_task_type(self.type))
        if self.priority is not None:
            object.__setattr__(self, "priority", parse_priority(self.priority))
        if self.owner_id is not None:
            object.__setattr__(
                self,
                "owner_id",
                " ".join(self.owner_id.strip().split()),
            )
        if self.assignee_id is not None:
            object.__setattr__(
                self,
                "assignee_id",
                " ".join(self.assignee_id.strip().split()),
            )
        if self.source is not None:
            object.__setattr__(
                self,
                "source",
                " ".join(self.source.strip().split()).casefold(),
            )
        if self.external_id is not None:
            object.__setattr__(
                self,
                "external_id",
                " ".join(self.external_id.strip().split()),
            )
        if self.due_from is not None:
            object.__setattr__(self, "due_from", as_utc(self.due_from))
        if self.due_until is not None:
            object.__setattr__(self, "due_until", as_utc(self.due_until))
        if self.overdue_at is not None:
            object.__setattr__(self, "overdue_at", as_utc(self.overdue_at))
        object.__setattr__(self, "ordering", TaskOrdering(self.ordering))
        if (
            self.due_from is not None
            and self.due_until is not None
            and self.due_until <= self.due_from
        ):
            raise ValidationError(
                "due_until must be later than due_from",
                code="task.query.invalid_due_interval",
            )


__all__ = ["TaskOrdering", "TaskQuery"]
