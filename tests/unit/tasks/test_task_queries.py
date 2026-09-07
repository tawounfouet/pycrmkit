"""Task query normalization and interval validation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from pycrmkit.exceptions import ValidationError
from pycrmkit.tasks import TaskPriority, TaskQuery, TaskStatus

NOW = datetime(2026, 9, 7, 10, 0, tzinfo=UTC)


def test_task_query_normalizes_enum_and_text_filters() -> None:
    query = TaskQuery(
        status="in_progress",
        priority="urgent",
        owner_id=" owner-1 ",
        assignee_id=" seller-2 ",
        source=" Manual Import ",
    )

    assert query.status is TaskStatus.IN_PROGRESS
    assert query.priority is TaskPriority.URGENT
    assert query.owner_id == "owner-1"
    assert query.assignee_id == "seller-2"
    assert query.source == "manual import"


def test_task_query_rejects_empty_due_window() -> None:
    with pytest.raises(ValidationError, match="due_until"):
        TaskQuery(due_from=NOW, due_until=NOW)


def test_task_query_accepts_half_open_due_window() -> None:
    query = TaskQuery(due_from=NOW, due_until=NOW + timedelta(days=1))

    assert query.due_from == NOW
    assert query.due_until == NOW + timedelta(days=1)
