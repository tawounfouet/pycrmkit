from datetime import UTC, datetime
from uuid import uuid4

import pytest

from pycrmkit.contacts import ContactId
from pycrmkit.core.events import EventId, EventType
from pycrmkit.core.references import EntityReference
from pycrmkit.exceptions import ValidationError
from pycrmkit.timeline import TimelineEntry, TimelineEntryId, TimelineEntryKind


def _entry() -> TimelineEntry:
    event_id = EventId(uuid4())
    contact = EntityReference("contact", ContactId(uuid4()))
    return TimelineEntry(
        id=TimelineEntryId(event_id.value),
        kind=TimelineEntryKind.ACTIVITY,
        event_type=EventType("activity.created"),
        source_event_id=event_id,
        entity=EntityReference("activity", ContactId(uuid4())),
        occurred_at=datetime(2026, 9, 7, 10, tzinfo=UTC),
        title="  Customer   meeting ",
        summary="  Discussed renewal  ",
        references=(contact, contact),
        metadata={"channel": "office"},
    )


def test_timeline_entry_normalizes_and_deduplicates_references() -> None:
    entry = _entry()
    assert entry.title == "Customer meeting"
    assert entry.summary == "Discussed renewal"
    assert len(entry.references) == 1
    assert entry.to_dict()["kind"] == "activity"


def test_timeline_entry_id_must_match_source_event() -> None:
    event_id = EventId(uuid4())
    with pytest.raises(ValidationError, match="must match source event id"):
        TimelineEntry(
            id=TimelineEntryId(uuid4()),
            kind=TimelineEntryKind.TASK,
            event_type=EventType("task.created"),
            source_event_id=event_id,
            entity=EntityReference("task", ContactId(uuid4())),
            occurred_at=datetime(2026, 9, 7, 10, tzinfo=UTC),
            title="Task created",
        )
