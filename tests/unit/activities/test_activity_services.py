"""Activity service behavior."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from pycrmkit.activities import (
    ActivityDirection,
    ActivityQuery,
    ActivityService,
    ActivityType,
    ActivityUpdate,
)
from pycrmkit.core.time import FixedClock
from pycrmkit.storage.memory import MemoryActivityRepository

NOW = datetime(2026, 9, 7, 8, 0, tzinfo=UTC)


class FixedIDFactory:
    def new(self, id_type):
        return id_type(UUID("00000000-0000-4000-8000-000000000201"))


def test_log_defaults_occurred_at_to_clock() -> None:
    repository = MemoryActivityRepository()
    service = ActivityService(
        repository,
        id_factory=FixedIDFactory(),
        clock=FixedClock(NOW),
    )

    logged = service.log(
        type="call",
        subject="Follow-up",
        direction="outbound",
        duration_seconds=480,
    )

    assert logged.type is ActivityType.CALL
    assert logged.direction is ActivityDirection.OUTBOUND
    assert logged.occurred_at == NOW
    assert repository.get(logged.id) == logged


def test_update_preserves_identity_and_creation_time() -> None:
    clock = FixedClock(NOW)
    service = ActivityService(
        MemoryActivityRepository(),
        id_factory=FixedIDFactory(),
        clock=clock,
    )
    logged = service.log(type="note", description="Initial note")
    clock.advance(timedelta(minutes=5))

    updated = service.update(
        logged.id,
        ActivityUpdate(
            description="Corrected note",
            source="manual",
        ),
    )

    assert updated.id == logged.id
    assert updated.created_at == logged.created_at
    assert updated.updated_at == NOW + timedelta(minutes=5)
    assert updated.description == "Corrected note"
    assert updated.source == "manual"


def test_list_delegates_portable_query() -> None:
    service = ActivityService(
        MemoryActivityRepository(),
        id_factory=FixedIDFactory(),
        clock=FixedClock(NOW),
    )
    service.log(type="meeting", subject="Discovery")

    result = service.list(ActivityQuery(type=ActivityType.MEETING))

    assert result.total == 1
    assert result.items[0].subject == "Discovery"
