"""Business calendar policy for deterministic CRM task scheduling."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pycrmkit.exceptions import ValidationError

_KEY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,119}$")


def normalize_calendar_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).strip().casefold()
    if not _KEY_PATTERN.fullmatch(normalized):
        raise ValidationError(
            "business calendar key must be a lowercase slug-like identifier",
            code="business_calendar.key.invalid",
            context={"key": value},
        )
    return normalized


@dataclass(frozen=True, slots=True, order=True)
class WorkingWindow:
    """One local-time working interval."""

    start: time
    end: time

    def __post_init__(self) -> None:
        if self.start.tzinfo is not None or self.end.tzinfo is not None:
            raise ValidationError(
                "working windows use local wall-clock times without tzinfo",
                code="business_calendar.working_window.invalid",
            )
        if self.start >= self.end:
            raise ValidationError(
                "working window end must be later than start",
                code="business_calendar.working_window.invalid",
            )


@dataclass(frozen=True, slots=True)
class BusinessCalendar:
    """Versioned scheduling policy expressed in one IANA timezone."""

    key: str
    timezone: str
    working_weekdays: frozenset[int] = frozenset({0, 1, 2, 3, 4})
    working_windows: tuple[WorkingWindow, ...] = ()
    holidays: frozenset[date] = frozenset()
    exceptional_working_days: frozenset[date] = frozenset()
    exceptional_non_working_days: frozenset[date] = frozenset()
    default_due_time: time = time(9, 0)
    revision: int = 1
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "key", normalize_calendar_key(self.key))
        try:
            ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError as exc:
            raise ValidationError(
                "business calendar timezone must be a valid IANA identifier",
                code="business_calendar.timezone.invalid",
                context={"timezone": self.timezone},
            ) from exc

        weekdays = frozenset(self.working_weekdays)
        if not weekdays or any(type(day) is not int or day < 0 or day > 6 for day in weekdays):
            raise ValidationError(
                "working weekdays must contain integers from 0 to 6",
                code="business_calendar.working_weekdays.invalid",
            )
        object.__setattr__(self, "working_weekdays", weekdays)

        windows = tuple(sorted(self.working_windows))
        for previous, current in zip(windows, windows[1:]):
            if current.start < previous.end:
                raise ValidationError(
                    "working windows cannot overlap",
                    code="business_calendar.working_window.overlap",
                )
        object.__setattr__(self, "working_windows", windows)

        if self.default_due_time.tzinfo is not None:
            raise ValidationError(
                "default due time must be a local wall-clock time without tzinfo",
                code="business_calendar.default_due_time.invalid",
            )
        if self.revision < 1:
            raise ValidationError(
                "business calendar revision must be at least 1",
                code="business_calendar.revision.invalid",
            )

        working = frozenset(self.exceptional_working_days)
        non_working = frozenset(self.exceptional_non_working_days)
        overlap = working & non_working
        if overlap:
            raise ValidationError(
                "a date cannot be both explicitly working and non-working",
                code="business_calendar.exception.conflict",
                context={"dates": tuple(sorted(day.isoformat() for day in overlap))},
            )
        object.__setattr__(self, "holidays", frozenset(self.holidays))
        object.__setattr__(self, "exceptional_working_days", working)
        object.__setattr__(self, "exceptional_non_working_days", non_working)
        object.__setattr__(self, "metadata", dict(self.metadata))

    @property
    def zone(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    def is_business_day(self, value: date) -> bool:
        """Apply explicit override > holiday > weekly schedule."""

        if value in self.exceptional_working_days:
            return True
        if value in self.exceptional_non_working_days:
            return False
        if value in self.holidays:
            return False
        return value.weekday() in self.working_weekdays

    def add_business_days(self, value: date, *, days: int) -> date:
        """Move by a signed number of business days."""

        if type(days) is not int:
            raise ValidationError(
                "business-day offset must be an integer",
                code="task.schedule.invalid_business_days",
            )
        if days == 0:
            return value

        direction = 1 if days > 0 else -1
        remaining = abs(days)
        current = value
        while remaining:
            current += timedelta(days=direction)
            if self.is_business_day(current):
                remaining -= 1
        return current

    def resolve_due_at(
        self,
        value: date,
        *,
        local_time: time | None = None,
    ) -> datetime:
        """Resolve a local calendar date/time into the canonical UTC instant."""

        selected = local_time or self.default_due_time
        if selected.tzinfo is not None:
            raise ValidationError(
                "local due time must not carry tzinfo",
                code="task.schedule.invalid_local_time",
            )

        naive = datetime.combine(value, selected)
        local = naive.replace(tzinfo=self.zone, fold=0)
        instant = local.astimezone(UTC)

        # A nonexistent local wall-clock time is normalized by zoneinfo. Reject
        # it instead so scheduling never silently changes the requested time.
        round_trip = instant.astimezone(self.zone).replace(tzinfo=None)
        if round_trip != naive:
            raise ValidationError(
                "local due time does not exist in the calendar timezone",
                code="task.schedule.invalid_local_time",
                context={
                    "timezone": self.timezone,
                    "local": naive.isoformat(),
                },
            )
        return instant


__all__ = [
    "BusinessCalendar",
    "WorkingWindow",
    "normalize_calendar_key",
]
