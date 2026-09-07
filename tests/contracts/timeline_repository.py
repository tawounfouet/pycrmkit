"""Reusable TimelineRepository behavioral contract suite."""

from __future__ import annotations

import pytest

from pycrmkit.core.pagination import OffsetPageRequest
from pycrmkit.exceptions import DuplicateError, NotFoundError
from pycrmkit.timeline import TimelineEntry, TimelineEntryKind, TimelineRepository


class TimelineRepositoryContract:
    """Assertions every TimelineRepository adapter must satisfy."""

    def test_append_and_get(
        self,
        repository: TimelineRepository,
        timeline_entry: TimelineEntry,
    ) -> None:
        repository.append(timeline_entry)
        assert repository.get(timeline_entry.id) == timeline_entry

    def test_missing_get_raises_and_find_returns_none(
        self,
        repository: TimelineRepository,
        missing_timeline_entry_id,
    ) -> None:
        with pytest.raises(NotFoundError):
            repository.get(missing_timeline_entry_id)
        assert repository.find(missing_timeline_entry_id) is None

    def test_identical_replay_is_idempotent(
        self,
        repository: TimelineRepository,
        timeline_entry: TimelineEntry,
        related_reference,
    ) -> None:
        repository.append(timeline_entry)
        repository.append(timeline_entry)
        page = repository.list_for_reference(related_reference, OffsetPageRequest())
        assert page.items == (timeline_entry,)
        assert page.total == 1

    def test_conflicting_replay_is_rejected(
        self,
        repository: TimelineRepository,
        timeline_entry: TimelineEntry,
        conflicting_timeline_entry: TimelineEntry,
    ) -> None:
        repository.append(timeline_entry)
        with pytest.raises(DuplicateError):
            repository.append(conflicting_timeline_entry)

    def test_list_is_reverse_chronological_and_exactly_paginated(
        self,
        repository: TimelineRepository,
        timeline_entry: TimelineEntry,
        newer_timeline_entry: TimelineEntry,
        related_reference,
    ) -> None:
        repository.append(timeline_entry)
        repository.append(newer_timeline_entry)
        first = repository.list_for_reference(
            related_reference,
            OffsetPageRequest(limit=1, offset=0),
        )
        second = repository.list_for_reference(
            related_reference,
            OffsetPageRequest(limit=1, offset=1),
        )
        assert first.items == (newer_timeline_entry,)
        assert second.items == (timeline_entry,)
        assert first.total == 2
        assert first.has_next is True
        assert second.has_previous is True

    def test_list_filters_kind_event_and_window(
        self,
        repository: TimelineRepository,
        timeline_entry: TimelineEntry,
        newer_timeline_entry: TimelineEntry,
        related_reference,
    ) -> None:
        repository.append(timeline_entry)
        repository.append(newer_timeline_entry)
        page = repository.list_for_reference(
            related_reference,
            OffsetPageRequest(),
            kind=TimelineEntryKind.TASK,
            event_type="task.completed",
            occurred_from=newer_timeline_entry.occurred_at,
        )
        assert page.items == (newer_timeline_entry,)
