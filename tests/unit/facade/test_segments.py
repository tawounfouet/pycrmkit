from __future__ import annotations

from datetime import UTC, datetime

import pytest

from pycrmkit import CRM
from pycrmkit.contacts import ContactId
from pycrmkit.core import FixedClock
from pycrmkit.core.references import EntityReference
from pycrmkit.exceptions import InvalidStateError
from pycrmkit.segments import Predicate, QueryOperator, SegmentMode

NOW = datetime(2026, 9, 28, 12, tzinfo=UTC)


def test_memory_crm_exposes_static_and_dynamic_segments() -> None:
    crm = CRM.memory(clock=FixedClock(NOW), webhook_auto_delivery=False)
    contact = crm.contacts.create(display_name="Ada", source="LinkedIn")

    static = crm.segments.create_static(
        key="named-contacts",
        name="Named Contacts",
        entity_kind="contact",
    )
    crm.segments.add_member(
        static.id,
        EntityReference("contact", contact.id),
    )

    dynamic = crm.segments.create_dynamic(
        key="linkedin",
        name="LinkedIn Contacts",
        entity_kind="contact",
        query=Predicate("source", QueryOperator.EQ, "linkedin"),
    )

    assert static.mode is SegmentMode.STATIC
    assert dynamic.mode is SegmentMode.DYNAMIC
    assert crm.segments.count(static.id) == 1
    assert crm.segments.count(dynamic.id) == 1
    assert crm.segments.evaluate(dynamic.id).items == (
        EntityReference("contact", ContactId.parse(contact.id)),
    )


def test_segment_mutations_emit_domain_events() -> None:
    crm = CRM.memory(clock=FixedClock(NOW), webhook_auto_delivery=False)
    emitted: list[str] = []
    for event_type in (
        "segment.created",
        "segment.member_added",
        "segment.member_removed",
        "segment.archived",
    ):
        crm.events.subscribe(
            event_type,
            lambda event, emitted=emitted: emitted.append(str(event.type)),
        )

    contact = crm.contacts.create(display_name="Ada")
    segment = crm.segments.create_static(
        key="test",
        name="Test",
        entity_kind="contact",
    )
    reference = EntityReference("contact", contact.id)
    crm.segments.add_member(segment.id, reference)
    crm.segments.remove_member(segment.id, reference)
    crm.segments.archive(segment.id)

    assert emitted == [
        "segment.created",
        "segment.member_added",
        "segment.member_removed",
        "segment.archived",
    ]


def test_snapshot_freezes_dynamic_population_and_is_immutable() -> None:
    crm = CRM.memory(clock=FixedClock(NOW), webhook_auto_delivery=False)
    ada = crm.contacts.create(display_name="Ada", source="LinkedIn")
    dynamic = crm.segments.create_dynamic(
        key="live-linkedin",
        name="Live LinkedIn",
        entity_kind="contact",
        query=Predicate("source", QueryOperator.EQ, "linkedin"),
    )

    snapshot = crm.segments.snapshot(
        dynamic.id,
        key="linkedin-snapshot",
        name="LinkedIn Snapshot",
    )
    later = crm.contacts.create(display_name="Later", source="LinkedIn")

    assert snapshot.mode is SegmentMode.SNAPSHOT
    assert crm.segments.evaluate(snapshot.id).items == (
        EntityReference("contact", ada.id),
    )
    assert set(crm.segments.evaluate(dynamic.id).items) == {
        EntityReference("contact", ada.id),
        EntityReference("contact", later.id),
    }

    with pytest.raises(InvalidStateError) as error:
        crm.segments.add_member(
            snapshot.id,
            EntityReference("contact", later.id),
        )

    assert error.value.code == "segment.snapshot.immutable"


def test_static_segment_bulk_membership_is_atomic_and_bounded() -> None:
    crm = CRM.memory(clock=FixedClock(NOW), webhook_auto_delivery=False)
    contacts = tuple(
        crm.contacts.create(display_name=f"Contact {index}")
        for index in range(3)
    )
    references = tuple(
        EntityReference("contact", contact.id)
        for contact in contacts
    )
    segment = crm.segments.create_static(
        key="bulk",
        name="Bulk",
        entity_kind="contact",
    )

    added = crm.segments.add_members(segment.id, references)

    assert tuple(member.entity for member in added) == references
    assert crm.segments.count(segment.id) == 3
    assert crm.segments.remove_members(segment.id, references[:2]) == 2
    assert crm.segments.evaluate(segment.id).items == (references[2],)
