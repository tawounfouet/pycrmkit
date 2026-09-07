"""Task aggregate root and lifecycle transitions."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum, StrEnum

from pycrmkit.core.entities import TimestampedEntity
from pycrmkit.core.ids import UUIDId
from pycrmkit.core.references import EntityReference
from pycrmkit.core.time import as_utc
from pycrmkit.exceptions import InvalidStateError, ValidationError


class TaskId(UUIDId):
    """Strongly typed identifier for a CRM Task."""


class TaskStatus(StrEnum):
    """Current lifecycle state for a CRM task."""

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TaskPriority(IntEnum):
    """Portable task priority where larger values represent greater urgency."""

    LOW = 10
    NORMAL = 20
    HIGH = 30
    URGENT = 40


_PRIORITY_ALIASES = {
    "low": TaskPriority.LOW,
    "normal": TaskPriority.NORMAL,
    "high": TaskPriority.HIGH,
    "urgent": TaskPriority.URGENT,
}


def parse_priority(value: TaskPriority | str | int) -> TaskPriority:
    """Parse stable priority names or enum values."""

    if isinstance(value, TaskPriority):
        return value
    if isinstance(value, str):
        try:
            return _PRIORITY_ALIASES[value.strip().casefold()]
        except KeyError as exc:
            raise ValidationError(
                "unknown task priority",
                code="task.priority.invalid",
                context={"priority": value},
            ) from exc
    if type(value) is int:
        try:
            return TaskPriority(value)
        except ValueError as exc:
            raise ValidationError(
                "unknown task priority",
                code="task.priority.invalid",
                context={"priority": value},
            ) from exc
    raise ValidationError(
        "unknown task priority",
        code="task.priority.invalid",
        context={"priority": value},
    )


def _normalize_required_text(value: str, *, field_name: str, max_length: int) -> str:
    normalized = " ".join(unicodedata.normalize("NFKC", value).strip().split())
    if not normalized:
        raise ValidationError(
            f"{field_name} is required",
            code=f"task.{field_name}.required",
        )
    if len(normalized) > max_length:
        raise ValidationError(
            f"{field_name} must be at most {max_length} characters",
            code=f"task.{field_name}.too_long",
        )
    return normalized


def _normalize_optional_text(
    value: str | None,
    *,
    field_name: str,
    max_length: int,
) -> str | None:
    if value is None:
        return None
    normalized = " ".join(unicodedata.normalize("NFKC", value).strip().split())
    if not normalized:
        return None
    if len(normalized) > max_length:
        raise ValidationError(
            f"{field_name} must be at most {max_length} characters",
            code=f"task.{field_name}.too_long",
        )
    return normalized


def _normalize_description(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = unicodedata.normalize("NFKC", value).strip()
    if not normalized:
        return None
    if len(normalized) > 20_000:
        raise ValidationError(
            "description must be at most 20000 characters",
            code="task.description.too_long",
        )
    return normalized


def _validate_references(references: tuple[EntityReference, ...]) -> None:
    if len(set(references)) != len(references):
        raise ValidationError(
            "task references must be unique",
            code="task.reference.duplicate",
        )


@dataclass(eq=False, slots=True)
class Task(TimestampedEntity[TaskId]):
    """Action item linked to CRM actors and domain entities."""

    title: str
    status: TaskStatus = TaskStatus.OPEN
    priority: TaskPriority = TaskPriority.NORMAL
    description: str | None = None
    due_at: datetime | None = None
    owner_id: str | None = None
    assignee_id: str | None = None
    references: tuple[EntityReference, ...] = ()
    source: str | None = None
    external_id: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    cancelled_at: datetime | None = None

    def __post_init__(self) -> None:
        TimestampedEntity.__post_init__(self)
        self.title = _normalize_required_text(
            self.title,
            field_name="title",
            max_length=300,
        )
        self.status = TaskStatus(self.status)
        self.priority = parse_priority(self.priority)
        self.description = _normalize_description(self.description)
        self.due_at = as_utc(self.due_at) if self.due_at is not None else None
        self.owner_id = _normalize_optional_text(
            self.owner_id,
            field_name="owner_id",
            max_length=255,
        )
        self.assignee_id = _normalize_optional_text(
            self.assignee_id,
            field_name="assignee_id",
            max_length=255,
        )
        self.references = tuple(self.references)
        self.source = _normalize_optional_text(
            self.source,
            field_name="source",
            max_length=120,
        )
        self.external_id = _normalize_optional_text(
            self.external_id,
            field_name="external_id",
            max_length=255,
        )
        self.metadata = dict(self.metadata)
        self.started_at = as_utc(self.started_at) if self.started_at is not None else None
        self.completed_at = (
            as_utc(self.completed_at) if self.completed_at is not None else None
        )
        self.cancelled_at = (
            as_utc(self.cancelled_at) if self.cancelled_at is not None else None
        )
        _validate_references(self.references)
        self._validate_lifecycle_timestamps()

    @property
    def is_terminal(self) -> bool:
        return self.status in {TaskStatus.COMPLETED, TaskStatus.CANCELLED}

    def is_overdue(self, at: datetime) -> bool:
        """Return whether the unresolved task is strictly past its due timestamp."""

        instant = as_utc(at)
        return (
            self.status in {TaskStatus.OPEN, TaskStatus.IN_PROGRESS}
            and self.due_at is not None
            and self.due_at < instant
        )

    def start(self, at: datetime) -> None:
        """Move an open task into progress."""

        instant = self._transition_instant(at)
        if self.status is not TaskStatus.OPEN:
            self._invalid_transition(TaskStatus.IN_PROGRESS)
        self.status = TaskStatus.IN_PROGRESS
        self.started_at = instant
        self.completed_at = None
        self.cancelled_at = None
        self.updated_at = instant

    def complete(self, at: datetime) -> None:
        """Complete an open or in-progress task."""

        instant = self._transition_instant(at)
        if self.status not in {TaskStatus.OPEN, TaskStatus.IN_PROGRESS}:
            self._invalid_transition(TaskStatus.COMPLETED)
        self.status = TaskStatus.COMPLETED
        self.completed_at = instant
        self.cancelled_at = None
        self.updated_at = instant

    def cancel(self, at: datetime) -> None:
        """Cancel an open or in-progress task."""

        instant = self._transition_instant(at)
        if self.status not in {TaskStatus.OPEN, TaskStatus.IN_PROGRESS}:
            self._invalid_transition(TaskStatus.CANCELLED)
        self.status = TaskStatus.CANCELLED
        self.cancelled_at = instant
        self.completed_at = None
        self.updated_at = instant

    def reopen(self, at: datetime) -> None:
        """Reopen a completed or cancelled task as a fresh open work cycle."""

        instant = self._transition_instant(at)
        if self.status not in {TaskStatus.COMPLETED, TaskStatus.CANCELLED}:
            self._invalid_transition(TaskStatus.OPEN)
        self.status = TaskStatus.OPEN
        self.started_at = None
        self.completed_at = None
        self.cancelled_at = None
        self.updated_at = instant

    def _validate_lifecycle_timestamps(self) -> None:
        if self.status is TaskStatus.OPEN:
            if any((self.started_at, self.completed_at, self.cancelled_at)):
                raise ValidationError(
                    "open tasks cannot carry lifecycle completion timestamps",
                    code="task.lifecycle.open_timestamp_conflict",
                )
        elif self.status is TaskStatus.IN_PROGRESS:
            if self.started_at is None:
                raise ValidationError(
                    "in-progress tasks require started_at",
                    code="task.lifecycle.started_at_required",
                )
            if self.completed_at is not None or self.cancelled_at is not None:
                raise ValidationError(
                    "in-progress tasks cannot be completed or cancelled",
                    code="task.lifecycle.in_progress_timestamp_conflict",
                )
        elif self.status is TaskStatus.COMPLETED:
            if self.completed_at is None:
                raise ValidationError(
                    "completed tasks require completed_at",
                    code="task.lifecycle.completed_at_required",
                )
            if self.cancelled_at is not None:
                raise ValidationError(
                    "completed tasks cannot carry cancelled_at",
                    code="task.lifecycle.completed_timestamp_conflict",
                )
        elif self.status is TaskStatus.CANCELLED:
            if self.cancelled_at is None:
                raise ValidationError(
                    "cancelled tasks require cancelled_at",
                    code="task.lifecycle.cancelled_at_required",
                )
            if self.completed_at is not None:
                raise ValidationError(
                    "cancelled tasks cannot carry completed_at",
                    code="task.lifecycle.cancelled_timestamp_conflict",
                )

    def _transition_instant(self, at: datetime) -> datetime:
        instant = as_utc(at)
        if instant < self.created_at:
            raise ValidationError(
                "task transition time cannot be earlier than created_at",
                code="task.transition.before_creation",
            )
        return instant

    def _invalid_transition(self, target: TaskStatus) -> None:
        raise InvalidStateError(
            f"cannot transition task from {self.status.value} to {target.value}",
            code="task.transition.invalid",
            context={"from": self.status.value, "to": target.value},
        )
