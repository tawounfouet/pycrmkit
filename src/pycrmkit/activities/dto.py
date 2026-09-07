"""Typed Activity service input DTOs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Final

from pycrmkit.activities.entities import ActivityDirection, ActivityType
from pycrmkit.activities.participants import ActivityParticipant
from pycrmkit.core.references import EntityReference


class UnsetType:
    """Sentinel type distinguishing an omitted update from an explicit None."""

    __slots__ = ()

    def __repr__(self) -> str:
        return "UNSET"


UNSET: Final = UnsetType()


@dataclass(frozen=True, slots=True)
class ActivityUpdate:
    """Partial Activity update preserving explicit clearing semantics."""

    type: ActivityType | UnsetType = UNSET
    occurred_at: datetime | UnsetType = UNSET
    subject: str | None | UnsetType = UNSET
    description: str | None | UnsetType = UNSET
    direction: ActivityDirection | None | UnsetType = UNSET
    duration_seconds: int | None | UnsetType = UNSET
    participants: tuple[ActivityParticipant, ...] | UnsetType = UNSET
    references: tuple[EntityReference, ...] | UnsetType = UNSET
    source: str | None | UnsetType = UNSET
    external_id: str | None | UnsetType = UNSET
    metadata: dict[str, object] | UnsetType = UNSET
