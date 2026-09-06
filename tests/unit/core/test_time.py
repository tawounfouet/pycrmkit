from datetime import UTC, datetime, timedelta, timezone

import pytest

from pycrmkit.core import Clock, FixedClock, SystemClock, as_utc


def test_system_clock_returns_aware_utc_time() -> None:
    clock = SystemClock()

    current = clock.now()

    assert isinstance(clock, Clock)
    assert current.tzinfo is UTC


def test_as_utc_normalizes_aware_datetime() -> None:
    paris_like = timezone(timedelta(hours=2))
    value = datetime(2026, 9, 6, 12, 30, tzinfo=paris_like)

    normalized = as_utc(value)

    assert normalized == datetime(2026, 9, 6, 10, 30, tzinfo=UTC)
    assert normalized.tzinfo is UTC


def test_as_utc_rejects_naive_datetime() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        as_utc(datetime(2026, 9, 6, 10, 30))


def test_fixed_clock_can_be_advanced_and_reset() -> None:
    clock = FixedClock(datetime(2026, 9, 6, 10, 0, tzinfo=UTC))

    assert clock.advance(timedelta(minutes=30)) == datetime(2026, 9, 6, 10, 30, tzinfo=UTC)
    assert clock.set(datetime(2026, 9, 6, 9, 0, tzinfo=UTC)) == datetime(
        2026, 9, 6, 9, 0, tzinfo=UTC
    )
    assert clock.now() == datetime(2026, 9, 6, 9, 0, tzinfo=UTC)
