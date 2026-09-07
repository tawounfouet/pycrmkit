"""Activity participation in MemoryUnitOfWork transactions."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from pycrmkit.activities import Activity, ActivityId, ActivityType
from pycrmkit.exceptions import NotFoundError
from pycrmkit.storage.memory import MemoryStore, MemoryUnitOfWork

NOW = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)


def _activity() -> Activity:
    return Activity(
        id=ActivityId(UUID("00000000-0000-4000-8000-000000000401")),
        created_at=NOW,
        updated_at=NOW,
        type=ActivityType.NOTE,
        occurred_at=NOW,
        description="Transaction note",
    )


def test_activity_commits_with_the_shared_memory_uow() -> None:
    store = MemoryStore()
    activity = _activity()

    with MemoryUnitOfWork(store) as uow:
        uow.activities.save(activity)
        uow.commit()

    with MemoryUnitOfWork(store) as uow:
        assert uow.activities.get(activity.id) == activity


def test_activity_rolls_back_without_commit() -> None:
    store = MemoryStore()
    activity = _activity()

    with MemoryUnitOfWork(store) as uow:
        uow.activities.save(activity)

    with MemoryUnitOfWork(store) as uow:
        with pytest.raises(NotFoundError):
            uow.activities.get(activity.id)
