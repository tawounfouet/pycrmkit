"""Persistence contract for customer-facing timeline projections."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from pycrmkit.core.events import EventType
from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.core.references import EntityReference
from pycrmkit.timeline.entries import TimelineEntry, TimelineEntryId, TimelineEntryKind


@runtime_checkable
class TimelineRepository(Protocol):
    """Backend-neutral repository for immutable timeline projections.

    Implementations must make ``append`` idempotent for an identical entry ID and
    reject conflicting content for that ID. Listing is deterministic using
    ``occurred_at DESC, kind ASC, id ASC`` ordering.
    """

    def get(self, entry_id: TimelineEntryId) -> TimelineEntry:
        """Return one timeline entry or raise NotFoundError."""

    def find(self, entry_id: TimelineEntryId) -> TimelineEntry | None:
        """Return one timeline entry or None."""

    def append(self, entry: TimelineEntry) -> None:
        """Append one immutable projection idempotently."""

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
        """Return reverse-chronological history related to one CRM entity."""
