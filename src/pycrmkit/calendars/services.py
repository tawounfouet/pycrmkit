"""Application helpers for business-day task scheduling."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time

from pycrmkit.calendars.entities import BusinessCalendar
from pycrmkit.calendars.registry import BusinessCalendarRegistry
from pycrmkit.core.time import Clock, SystemClock


@dataclass(slots=True)
class BusinessCalendarService:
    """Resolve relative business-day requests into canonical due instants."""

    registry: BusinessCalendarRegistry
    clock: Clock = field(default_factory=SystemClock)

    def due_in_business_days(
        self,
        key: str,
        *,
        days: int,
        local_time: time | None = None,
        from_date: date | None = None,
    ) -> datetime:
        calendar = self.registry.get(key)
        start = from_date or self.clock.now().astimezone(calendar.zone).date()
        target = calendar.add_business_days(start, days=days)
        return calendar.resolve_due_at(target, local_time=local_time)


__all__ = ["BusinessCalendarService"]
