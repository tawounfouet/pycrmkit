from __future__ import annotations

from datetime import UTC, datetime

import pytest

from pycrmkit.contacts import Contact, ContactId
from pycrmkit.core.pagination import OffsetPageRequest
from pycrmkit.core.references import EntityReference
from pycrmkit.exceptions import DuplicateError
from pycrmkit.segments import (
    Predicate,
    QueryOperator,
    Segment,
    SegmentId,
    SegmentMember,
    SegmentMode,
)
from pycrmkit.storage.memory._state import _MemoryState
from pycrmkit.storage.memory.segments import (
    MemorySegmentMembershipRepository,
    MemorySegmentQueryExecutor,
    MemorySegmentRepository,
)

NOW = datetime(2026, 9, 28, 12, tzinfo=UTC)


def test_segment_key_is_unique() -> None:
    state = _MemoryState()
    repository = MemorySegmentRepository(state)
    first = Segment(
        id=SegmentId.parse("00000000-0000-0000-0000-000000000001"),
        created_at=NOW,
        updated_at=NOW,
        key="enterprise",
        name="Enterprise",
        entity_kind="contact",
        mode=SegmentMode.STATIC,
    )
    second = Segment(
        id=SegmentId.parse("00000000-0000-0000-0000-000000000002"),
        created_at=NOW,
        updated_at=NOW,
        key="enterprise",
        name="Duplicate",
        entity_kind="contact",
        mode=SegmentMode.STATIC,
    )

    repository.save(first)
    with pytest.raises(DuplicateError) as exc_info:
        repository.save(second)

    assert exc_info.value.code == "segment.key.duplicate"


def test_static_membership_is_unique_and_paginated() -> None:
    state = _MemoryState()
    repository = MemorySegmentMembershipRepository(state)
    segment_id = SegmentId.parse("00000000-0000-0000-0000-000000000010")
    entity = EntityReference(
        "contact",
        ContactId.parse("00000000-0000-0000-0000-000000000011"),
    )
    member = SegmentMember(segment_id, entity, NOW)

    repository.add(member)

    with pytest.raises(DuplicateError):
        repository.add(member)

    page = repository.list(segment_id, OffsetPageRequest(limit=10))
    assert page.items == (member,)
    assert page.total == 1


def test_dynamic_query_evaluates_canonical_contact_state() -> None:
    state = _MemoryState()
    linkedin = Contact(
        id=ContactId.parse("00000000-0000-0000-0000-000000000001"),
        created_at=NOW,
        updated_at=NOW,
        display_name="Ada",
        source="LinkedIn",
    )
    newsletter = Contact(
        id=ContactId.parse("00000000-0000-0000-0000-000000000002"),
        created_at=NOW,
        updated_at=NOW,
        display_name="Grace",
        source="Newsletter",
    )
    state.contacts = {linkedin.id: linkedin, newsletter.id: newsletter}
    executor = MemorySegmentQueryExecutor(state)

    page = executor.execute(
        "contact",
        Predicate("source", QueryOperator.EQ, "linkedin"),
        OffsetPageRequest(),
        at=NOW,
    )

    assert page.items == (EntityReference("contact", linkedin.id),)
    assert page.total == 1
