"""Timezone-aware scheduling helpers for Task projections."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pycrmkit.core.time import as_utc
from pycrmkit.exceptions import ValidationError


def _zone(timezone: str) -> ZoneInfo:
    try:
        return ZoneInfo(timezone)
    except ZoneInfoNotFoundError as exc:
        raise ValidationError(
            "task work queue timezone must be a valid IANA identifier",
            code="task.schedule.timezone.invalid",
            context={"timezone": timezone},
        ) from exc


def _local_midnight(value: date, zone: ZoneInfo) -> datetime:
    local = datetime.combine(value, time.min, tzinfo=zone)
    return local.astimezone(UTC)


def local_day_bounds(at: datetime, *, timezone: str) -> tuple[datetime, datetime]:
    """Return UTC [start, end) bounds for the local calendar date containing at."""

    instant = as_utc(at)
    zone = _zone(timezone)
    local_date = instant.astimezone(zone).date()
    return (
        _local_midnight(local_date, zone),
        _local_midnight(local_date + timedelta(days=1), zone),
    )


def upcoming_bounds(
    at: datetime,
    *,
    timezone: str,
    days: int | None = None,
) -> tuple[datetime, datetime | None]:
    """Return UTC bounds beginning at the next local day boundary."""

    instant = as_utc(at)
    zone = _zone(timezone)
    local_date = instant.astimezone(zone).date()
    start_date = local_date + timedelta(days=1)
    start = _local_midnight(start_date, zone)
    if days is None:
        return start, None
    if type(days) is not int or days < 1:
        raise ValidationError(
            "upcoming days must be a positive integer",
            code="task.schedule.invalid_upcoming_days",
            context={"days": days},
        )
    return start, _local_midnight(start_date + timedelta(days=days), zone)


__all__ = ["local_day_bounds", "upcoming_bounds"]
