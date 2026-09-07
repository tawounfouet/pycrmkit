"""Application service for Activity lifecycle operations."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import TypeVar

from pycrmkit.activities.dto import ActivityUpdate, UnsetType
from pycrmkit.activities.entities import Activity, ActivityDirection, ActivityId, ActivityType
from pycrmkit.activities.participants import ActivityParticipant
from pycrmkit.activities.queries import ActivityQuery
from pycrmkit.activities.repository import ActivityRepository
from pycrmkit.core.ids import IDFactory, UUID4Factory
from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.core.references import EntityReference
from pycrmkit.core.time import Clock, SystemClock

T = TypeVar("T")


@dataclass(slots=True)
class ActivityService:
    """Framework-agnostic service for interaction history."""

    repository: ActivityRepository
    id_factory: IDFactory = field(default_factory=UUID4Factory)
    clock: Clock = field(default_factory=SystemClock)

    def log(
        self,
        *,
        type: ActivityType | str,
        occurred_at: datetime | None = None,
        subject: str | None = None,
        description: str | None = None,
        direction: ActivityDirection | str | None = None,
        duration_seconds: int | None = None,
        participants: Sequence[ActivityParticipant] = (),
        references: Sequence[EntityReference] = (),
        source: str | None = None,
        external_id: str | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> Activity:
        """Log one CRM interaction and persist it through the repository contract."""

        now = self.clock.now()
        activity = Activity(
            id=self.id_factory.new(ActivityId),
            created_at=now,
            updated_at=now,
            type=ActivityType(type),
            occurred_at=occurred_at or now,
            subject=subject,
            description=description,
            direction=ActivityDirection(direction) if direction is not None else None,
            duration_seconds=duration_seconds,
            participants=tuple(participants),
            references=tuple(references),
            source=source,
            external_id=external_id,
            metadata=dict(metadata or {}),
        )
        self.repository.save(activity)
        return activity

    def get(self, activity_id: ActivityId) -> Activity:
        """Return an activity under the repository's not-found contract."""

        return self.repository.get(activity_id)

    def update(self, activity_id: ActivityId, changes: ActivityUpdate) -> Activity:
        """Apply a typed partial update while retaining immutable identity/creation time."""

        current = self.repository.get(activity_id)
        now = self.clock.now()
        candidate = Activity(
            id=current.id,
            created_at=current.created_at,
            updated_at=now,
            type=self._value(changes.type, current.type),
            occurred_at=self._value(changes.occurred_at, current.occurred_at),
            subject=self._value(changes.subject, current.subject),
            description=self._value(changes.description, current.description),
            direction=self._value(changes.direction, current.direction),
            duration_seconds=self._value(changes.duration_seconds, current.duration_seconds),
            participants=self._value(changes.participants, current.participants),
            references=self._value(changes.references, current.references),
            source=self._value(changes.source, current.source),
            external_id=self._value(changes.external_id, current.external_id),
            metadata=self._value(changes.metadata, current.metadata),
        )
        self.repository.save(candidate)
        return candidate

    def list(
        self,
        query: ActivityQuery | None = None,
        page: OffsetPageRequest | None = None,
    ) -> Page[Activity]:
        """List activities using portable query and pagination objects."""

        return self.repository.list(
            query or ActivityQuery(),
            page or OffsetPageRequest(),
        )

    @staticmethod
    def _value(value: T | UnsetType, current: T) -> T:
        return current if isinstance(value, UnsetType) else value
