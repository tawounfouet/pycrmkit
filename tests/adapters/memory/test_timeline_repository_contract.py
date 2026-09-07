"""Run Timeline repository contracts against the official Memory adapter."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from pycrmkit.contacts import ContactId
from pycrmkit.core.events import EventId, EventType
from pycrmkit.core.references import EntityReference
from pycrmkit.storage.memory import MemoryTimelineRepository
from pycrmkit.timeline import (
    TimelineEntry,
    TimelineEntryId,
    TimelineEntryKind,
    TimelineRepository,
)

from ...contracts.timeline_repository import TimelineRepositoryContract

NOW = datetime(2026, 9, 7, 11, 0, tzinfo=UTC)


@pytest.fixture
def related_reference() -> EntityReference:
    return EntityReference(
        "contact",
        ContactId(UUID("00000000-0000-4000-8000-000000001301")),
    )


@pytest.fixture
def repository() -> TimelineRepository:
    repository = MemoryTimelineRepository()
    assert isinstance(repository, TimelineRepository)
    return repository


def _entry(
    *,
    event_uuid: str,
    entity_uuid: str,
    kind: TimelineEntryKind,
    event_type: str,
    occurred_at: datetime,
    reference: EntityReference,
    title: str,
) -> TimelineEntry:
    event_id = EventId(UUID(event_uuid))
    return TimelineEntry(
        id=TimelineEntryId(event_id.value),
        kind=kind,
        event_type=EventType(event_type),
        source_event_id=event_id,
        entity=EntityReference(
            kind.value,
            ContactId(UUID(entity_uuid)),
        ),
        occurred_at=occurred_at,
        title=title,
        references=(reference,),
    )


@pytest.fixture
def timeline_entry(related_reference: EntityReference) -> TimelineEntry:
    return _entry(
        event_uuid="00000000-0000-4000-8000-000000001311",
        entity_uuid="00000000-0000-4000-8000-000000001321",
        kind=TimelineEntryKind.ACTIVITY,
        event_type="activity.created",
        occurred_at=NOW,
        reference=related_reference,
        title="Meeting",
    )


@pytest.fixture
def newer_timeline_entry(related_reference: EntityReference) -> TimelineEntry:
    return _entry(
        event_uuid="00000000-0000-4000-8000-000000001312",
        entity_uuid="00000000-0000-4000-8000-000000001322",
        kind=TimelineEntryKind.TASK,
        event_type="task.completed",
        occurred_at=NOW + timedelta(hours=1),
        reference=related_reference,
        title="Task completed",
    )


@pytest.fixture
def conflicting_timeline_entry(timeline_entry: TimelineEntry) -> TimelineEntry:
    return TimelineEntry(
        id=timeline_entry.id,
        kind=timeline_entry.kind,
        event_type=timeline_entry.event_type,
        source_event_id=timeline_entry.source_event_id,
        entity=timeline_entry.entity,
        occurred_at=timeline_entry.occurred_at,
        title="Conflicting replay",
        references=timeline_entry.references,
    )


@pytest.fixture
def missing_timeline_entry_id() -> TimelineEntryId:
    return TimelineEntryId(UUID("00000000-0000-4000-8000-000000009998"))


class TestMemoryTimelineRepository(TimelineRepositoryContract):
    """Official Memory adapter must satisfy the reusable Timeline contract."""
