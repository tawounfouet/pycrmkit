"""Runtime registry for BusinessCalendar configuration."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pycrmkit.calendars.entities import BusinessCalendar, normalize_calendar_key
from pycrmkit.exceptions import ConflictError, NotFoundError


@runtime_checkable
class BusinessCalendarRegistry(Protocol):
    """Resolve application/tenant-scoped business calendars."""

    def get(self, key: str) -> BusinessCalendar:
        """Return the current calendar revision."""

    def register(self, calendar: BusinessCalendar) -> BusinessCalendar:
        """Register a first or strictly newer calendar revision."""

    def list(self) -> tuple[BusinessCalendar, ...]:
        """Return current revisions ordered by key."""


class InMemoryBusinessCalendarRegistry:
    """Simple runtime registry suitable for embedded apps and tests."""

    def __init__(self, calendars: tuple[BusinessCalendar, ...] = ()) -> None:
        self._calendars: dict[str, BusinessCalendar] = {}
        for calendar in calendars:
            self.register(calendar)

    def get(self, key: str) -> BusinessCalendar:
        normalized = normalize_calendar_key(key)
        calendar = self._calendars.get(normalized)
        if calendar is None:
            raise NotFoundError(
                "business calendar not found",
                code="task.schedule.calendar_not_found",
                context={"key": normalized},
            )
        return calendar

    def register(self, calendar: BusinessCalendar) -> BusinessCalendar:
        current = self._calendars.get(calendar.key)
        if current is not None and calendar.revision <= current.revision:
            raise ConflictError(
                "business calendar revision must increase",
                code="business_calendar.revision.conflict",
                context={
                    "key": calendar.key,
                    "current_revision": current.revision,
                    "revision": calendar.revision,
                },
            )
        self._calendars[calendar.key] = calendar
        return calendar

    def list(self) -> tuple[BusinessCalendar, ...]:
        return tuple(self._calendars[key] for key in sorted(self._calendars))


__all__ = [
    "BusinessCalendarRegistry",
    "InMemoryBusinessCalendarRegistry",
]
