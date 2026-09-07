"""Activity query invariants."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from pycrmkit.activities import ActivityDirection, ActivityQuery, ActivityType
from pycrmkit.exceptions import ValidationError


def test_activity_query_normalizes_enum_and_source() -> None:
    query = ActivityQuery(type="email", direction="inbound", source="  IMPORT ")

    assert query.type is ActivityType.EMAIL
    assert query.direction is ActivityDirection.INBOUND
    assert query.source == "import"


def test_activity_query_uses_half_open_interval() -> None:
    start = datetime(2026, 9, 1, tzinfo=UTC)
    end = datetime(2026, 9, 2, tzinfo=UTC)

    query = ActivityQuery(occurred_from=start, occurred_until=end)

    assert query.occurred_from == start
    assert query.occurred_until == end


def test_activity_query_rejects_empty_or_reversed_interval() -> None:
    instant = datetime(2026, 9, 1, tzinfo=UTC)

    with pytest.raises(ValidationError):
        ActivityQuery(occurred_from=instant, occurred_until=instant)
