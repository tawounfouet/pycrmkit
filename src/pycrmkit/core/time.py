"""Clock abstractions and UTC timestamp normalization."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol, runtime_checkable


def as_utc(value: datetime) -> datetime:
    """Return an aware datetime normalized to UTC.

    Naive datetimes are rejected instead of being interpreted using a machine-local timezone.
    """

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("PyCRMKit timestamps must be timezone-aware")
    return value.astimezone(UTC)


@runtime_checkable
class Clock(Protocol):
    """Source of current time for domain and application services."""

    def now(self) -> datetime:
        """Return the current timezone-aware UTC timestamp."""


class SystemClock:
    """Production clock using the system wall clock in UTC."""

    def now(self) -> datetime:
        return datetime.now(UTC)


@dataclass(slots=True)
class FixedClock:
    """Deterministic mutable clock for tests and controlled simulations."""

    current: datetime

    def __post_init__(self) -> None:
        self.current = as_utc(self.current)

    def now(self) -> datetime:
        return self.current

    def set(self, value: datetime) -> datetime:
        """Set the clock to ``value`` after UTC normalization and return the new time."""

        self.current = as_utc(value)
        return self.current

    def advance(self, delta: timedelta) -> datetime:
        """Advance the clock by ``delta`` and return the resulting timestamp."""

        self.current = self.current + delta
        return self.current
