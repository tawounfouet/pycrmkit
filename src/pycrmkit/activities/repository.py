"""Persistence contract for Activity aggregates."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pycrmkit.activities.entities import Activity, ActivityId
from pycrmkit.activities.queries import ActivityQuery
from pycrmkit.core.pagination import OffsetPageRequest, Page


@runtime_checkable
class ActivityRepository(Protocol):
    """Backend-neutral repository contract for CRM activities.

    ``get`` raises ``NotFoundError`` for missing records; ``find`` is nullable.
    Listing uses ``occurred_at DESC, id ASC`` ordering with exact pagination.
    """

    def get(self, activity_id: ActivityId) -> Activity:
        """Return an activity or raise NotFoundError."""

    def find(self, activity_id: ActivityId) -> Activity | None:
        """Return an activity or None."""

    def save(self, activity: Activity) -> None:
        """Persist current activity state without committing an outer transaction."""

    def list(
        self,
        query: ActivityQuery,
        page: OffsetPageRequest,
    ) -> Page[Activity]:
        """List activities using deterministic reverse-chronological ordering."""
