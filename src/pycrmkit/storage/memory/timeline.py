"""Official in-memory Timeline repository."""

from __future__ import annotations

from datetime import datetime

from pycrmkit.core.events import EventType
from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.core.references import EntityReference
from pycrmkit.core.time import as_utc
from pycrmkit.exceptions import DuplicateError, NotFoundError, ValidationError
from pycrmkit.storage.memory._state import _MemoryState
from pycrmkit.timeline import TimelineEntry, TimelineEntryId, TimelineEntryKind
from pycrmkit.timeline.repository import TimelineRepository


class MemoryTimelineRepository(TimelineRepository):
    """Immutable, idempotent timeline projection store over one memory snapshot."""

    def __init__(self, state: _MemoryState | None = None) -> None:
        self._state = state or _MemoryState()

    def get(self, entry_id: TimelineEntryId) -> TimelineEntry:
        entry = self.find(entry_id)
        if entry is None:
            raise NotFoundError(
                "timeline entry not found",
                code="timeline.not_found",
                context={"timeline_entry_id": str(entry_id)},
            )
        return entry

    def find(self, entry_id: TimelineEntryId) -> TimelineEntry | None:
        return self._state.timeline_entries.get(entry_id)

    def append(self, entry: TimelineEntry) -> None:
        existing = self._state.timeline_entries.get(entry.id)
        if existing is None:
            self._state.timeline_entries[entry.id] = entry
            return
        if existing != entry:
            raise DuplicateError(
                "timeline entry id already contains different projected content",
                code="timeline.projection.conflict",
                context={"timeline_entry_id": str(entry.id)},
            )

    def list_for_reference(
        self,
        reference: EntityReference,
        page: OffsetPageRequest,
        *,
        kind: TimelineEntryKind | None = None,
        event_type: EventType | str | None = None,
        occurred_from: datetime | None = None,
        occurred_until: datetime | None = None,
    ) -> Page[TimelineEntry]:
        entries = [
            item
            for item in self._state.timeline_entries.values()
            if reference in item.references
        ]
        if kind is not None:
            parsed_kind = TimelineEntryKind(kind)
            entries = [item for item in entries if item.kind is parsed_kind]
        if event_type is not None:
            parsed_event = EventType.parse(event_type)
            entries = [item for item in entries if item.event_type == parsed_event]
        if occurred_from is not None:
            lower = as_utc(occurred_from)
            entries = [item for item in entries if item.occurred_at >= lower]
        if occurred_until is not None:
            upper = as_utc(occurred_until)
            entries = [item for item in entries if item.occurred_at < upper]
        if (
            occurred_from is not None
            and occurred_until is not None
            and as_utc(occurred_until) <= as_utc(occurred_from)
        ):
            raise ValidationError(
                "occurred_until must be later than occurred_from",
                code="timeline.query.invalid_interval",
            )

        entries.sort(key=lambda item: item.id)
        entries.sort(key=lambda item: item.kind.value)
        entries.sort(key=lambda item: item.occurred_at, reverse=True)
        total = len(entries)
        selected = entries[page.offset : page.offset + page.limit]
        return Page(
            items=tuple(selected),
            limit=page.limit,
            offset=page.offset,
            total=total,
        )
