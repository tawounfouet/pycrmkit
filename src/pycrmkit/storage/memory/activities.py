"""Official in-memory Activity repository."""

from __future__ import annotations

from copy import deepcopy

from pycrmkit.activities import Activity, ActivityId, ActivityQuery, ActivityRepository
from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.exceptions import NotFoundError
from pycrmkit.storage.memory._state import _MemoryState


class MemoryActivityRepository(ActivityRepository):
    """Copy-isolated Activity repository backed by one memory state snapshot."""

    def __init__(self, state: _MemoryState | None = None) -> None:
        self._state = state or _MemoryState()

    def get(self, activity_id: ActivityId) -> Activity:
        activity = self._state.activities.get(activity_id)
        if activity is None:
            raise NotFoundError(
                "activity not found",
                code="activity.not_found",
                context={"activity_id": str(activity_id)},
            )
        return deepcopy(activity)

    def find(self, activity_id: ActivityId) -> Activity | None:
        activity = self._state.activities.get(activity_id)
        return deepcopy(activity) if activity is not None else None

    def save(self, activity: Activity) -> None:
        self._state.activities[activity.id] = deepcopy(activity)

    def list(
        self,
        query: ActivityQuery,
        page: OffsetPageRequest,
    ) -> Page[Activity]:
        activities = list(self._state.activities.values())
        if query.type is not None:
            activities = [item for item in activities if item.type is query.type]
        if query.participant is not None:
            activities = [
                item
                for item in activities
                if any(
                    participant.reference == query.participant
                    for participant in item.participants
                )
            ]
        if query.reference is not None:
            activities = [item for item in activities if query.reference in item.references]
        if query.direction is not None:
            activities = [item for item in activities if item.direction is query.direction]
        if query.source is not None:
            activities = [
                item
                for item in activities
                if item.source is not None and item.source.casefold() == query.source
            ]
        if query.external_id is not None:
            activities = [item for item in activities if item.external_id == query.external_id]
        if query.occurred_from is not None:
            activities = [
                item for item in activities if item.occurred_at >= query.occurred_from
            ]
        if query.occurred_until is not None:
            activities = [
                item for item in activities if item.occurred_at < query.occurred_until
            ]
        activities.sort(key=lambda item: item.id)
        activities.sort(key=lambda item: item.occurred_at, reverse=True)
        total = len(activities)
        selected = activities[page.offset : page.offset + page.limit]
        return Page(
            items=tuple(deepcopy(selected)),
            limit=page.limit,
            offset=page.offset,
            total=total,
        )
