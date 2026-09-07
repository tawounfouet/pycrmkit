"""Typed Task service input DTOs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Final

from pycrmkit.core.references import EntityReference
from pycrmkit.tasks.entities import TaskPriority


class UnsetType:
    """Sentinel type distinguishing omission from explicit clearing."""

    __slots__ = ()

    def __repr__(self) -> str:
        return "UNSET"


UNSET: Final = UnsetType()


@dataclass(frozen=True, slots=True)
class TaskUpdate:
    """Editable Task fields; lifecycle status changes use explicit transitions."""

    title: str | UnsetType = UNSET
    description: str | None | UnsetType = UNSET
    priority: TaskPriority | str | int | UnsetType = UNSET
    due_at: datetime | None | UnsetType = UNSET
    owner_id: str | None | UnsetType = UNSET
    assignee_id: str | None | UnsetType = UNSET
    references: tuple[EntityReference, ...] | UnsetType = UNSET
    source: str | None | UnsetType = UNSET
    external_id: str | None | UnsetType = UNSET
    metadata: dict[str, object] | UnsetType = UNSET
