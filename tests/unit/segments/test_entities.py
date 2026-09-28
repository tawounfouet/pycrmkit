from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from pycrmkit.exceptions import InvalidStateError, ValidationError
from pycrmkit.segments import (
    Predicate,
    QueryOperator,
    Segment,
    SegmentId,
    SegmentMode,
    SegmentStatus,
)

NOW = datetime(2026, 9, 28, 12, tzinfo=UTC)


def _segment(
    *,
    mode: SegmentMode,
    query: Predicate | None = None,
) -> Segment:
    return Segment(
        id=SegmentId(UUID("00000000-0000-0000-0000-000000000001")),
        created_at=NOW,
        updated_at=NOW,
        key="qualified-leads",
        name="Qualified Leads",
        entity_kind="lead",
        mode=mode,
        query=query,
    )


def test_dynamic_segment_requires_query() -> None:
    with pytest.raises(ValidationError) as exc_info:
        _segment(mode=SegmentMode.DYNAMIC)

    assert exc_info.value.code == "segment.query.required"


def test_static_segment_rejects_dynamic_query() -> None:
    with pytest.raises(ValidationError) as exc_info:
        _segment(
            mode=SegmentMode.STATIC,
            query=Predicate("status", QueryOperator.EQ, "qualified"),
        )

    assert exc_info.value.code == "segment.query.not_allowed"


def test_archive_is_idempotent() -> None:
    segment = _segment(mode=SegmentMode.STATIC)
    archived_at = datetime(2026, 9, 29, 8, tzinfo=UTC)

    segment.archive(archived_at)
    segment.archive(archived_at)

    assert segment.status is SegmentStatus.ARCHIVED
    assert segment.archived_at == archived_at
    assert segment.revision == 2


def test_dynamic_membership_is_not_writable() -> None:
    segment = _segment(
        mode=SegmentMode.DYNAMIC,
        query=Predicate("status", QueryOperator.EQ, "qualified"),
    )

    with pytest.raises(InvalidStateError) as exc_info:
        segment.ensure_membership_writable()

    assert exc_info.value.code == "segment.membership.not_writable"
