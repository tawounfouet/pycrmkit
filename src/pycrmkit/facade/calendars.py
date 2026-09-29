"""Business Calendars facade namespace."""

from __future__ import annotations

from datetime import date, datetime, time

from pycrmkit.calendars import (
    BusinessCalendar,
    BusinessCalendarRegistry,
    BusinessCalendarService,
)
from pycrmkit.core.time import Clock


class CalendarsAPI:
    """Runtime/configuration facade for deterministic business-day scheduling."""

    def __init__(
        self,
        registry: BusinessCalendarRegistry,
        *,
        clock: Clock,
    ) -> None:
        self._registry = registry
        self._clock = clock

    def register(self, calendar: BusinessCalendar) -> BusinessCalendar:
        return self._registry.register(calendar)

    def get(self, key: str) -> BusinessCalendar:
        return self._registry.get(key)

    def list(self) -> tuple[BusinessCalendar, ...]:
        return self._registry.list()

    def due_in_business_days(
        self,
        key: str,
        *,
        days: int,
        local_time: time | None = None,
        from_date: date | None = None,
    ) -> datetime:
        return BusinessCalendarService(
            self._registry,
            clock=self._clock,
        ).due_in_business_days(
            key,
            days=days,
            local_time=local_time,
            from_date=from_date,
        )


__all__ = ["CalendarsAPI"]
