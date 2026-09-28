from __future__ import annotations

from datetime import UTC, datetime

from pycrmkit import CRM
from pycrmkit.contacts import ContactId
from pycrmkit.core import FixedClock
from pycrmkit.core.references import EntityReference
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
