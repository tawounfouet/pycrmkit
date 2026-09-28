from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from pycrmkit import CRM
from pycrmkit.core import FixedClock
from pycrmkit.core.references import EntityReference
from pycrmkit.custom_fields import CustomFieldType
from pycrmkit.exceptions import ConflictError
from pycrmkit.saved_queries import (
    SavedQueryRevision,
    SavedQueryVisibility,
)
from pycrmkit.segments import (
    And,
    Predicate,
    QueryOperator,
    RelativeTimeUnit,
    RelativeTimeValue,
    SortDirection,
    SortExpression,
    expression_from_dict,
    expression_to_dict,
)

NOW = datetime(2026, 9, 29, 12, tzinfo=UTC)


def test_saved_query_executes_custom_field_and_tag_filters() -> None:
    crm = CRM.memory(clock=FixedClock(NOW), webhook_auto_delivery=False)
    ada = crm.contacts.create(display_name="Ada", source="LinkedIn")
    grace = crm.contacts.create(display_name="Grace", source="LinkedIn")

    budget = crm.custom_fields.define(
        key="annual_budget",
        label="Annual Budget",
        field_type=CustomFieldType.DECIMAL,
        applies_to=("contact",),
    )
    crm.custom_fields.set_value(
        budget.id,
        EntityReference("contact", ada.id),
        Decimal("150000"),
    )
    crm.custom_fields.set_value(
        budget.id,
        EntityReference("contact", grace.id),
        Decimal("50000"),
    )

    vip = crm.tags.create("VIP")
    crm.tags.assign(vip.id, EntityReference("contact", ada.id))

    saved = crm.saved_queries.create(
        key="vip-enterprise-budget",
        name="VIP Enterprise Budget",
        entity_kind="contact",
        expression=And(
            (
                Predicate(
                    "custom.annual_budget",
                    QueryOperator.GTE,
                    Decimal("100000"),
                ),
                Predicate("tag", QueryOperator.EQ, "vip"),
            )
        ),
    )

    result = crm.saved_queries.execute(saved.id)

    assert result.items == (EntityReference("contact", ada.id),)
    assert result.total == 1


def test_saved_query_relative_time_uses_injected_clock_and_ordering() -> None:
    clock = FixedClock(NOW - timedelta(days=45))
    crm = CRM.memory(clock=clock, webhook_auto_delivery=False)
    old = crm.contacts.create(display_name="Old")
    clock.set(NOW - timedelta(days=10))
    recent_b = crm.contacts.create(display_name="Beta")
    clock.set(NOW - timedelta(days=5))
    recent_a = crm.contacts.create(display_name="Alpha")
    clock.set(NOW)

    saved = crm.saved_queries.create(
        key="recent-contacts",
        name="Recent Contacts",
        entity_kind="contact",
        expression=Predicate(
            "created_at",
            QueryOperator.GTE,
            RelativeTimeValue(-30, RelativeTimeUnit.DAYS),
        ),
        ordering=(SortExpression("display_name", SortDirection.ASC),),
    )

    result = crm.saved_queries.execute(saved.id)

    assert EntityReference("contact", old.id) not in result.items
    assert result.items == (
        EntityReference("contact", recent_a.id),
        EntityReference("contact", recent_b.id),
    )


def test_relative_time_round_trips_in_expression_schema_v2() -> None:
    expression = Predicate(
        "created_at",
        QueryOperator.GTE,
        RelativeTimeValue(-4, RelativeTimeUnit.WEEKS),
    )

    restored = expression_from_dict(expression_to_dict(expression))

    assert restored == expression


def test_saved_query_revision_does_not_silently_change_bound_segment() -> None:
    crm = CRM.memory(clock=FixedClock(NOW), webhook_auto_delivery=False)
    linkedin = crm.contacts.create(display_name="Ada", source="LinkedIn")
    newsletter = crm.contacts.create(display_name="Grace", source="Newsletter")

    saved = crm.saved_queries.create(
        key="acquisition-source",
        name="LinkedIn",
        entity_kind="contact",
        expression=Predicate("source", QueryOperator.EQ, "linkedin"),
        visibility=SavedQueryVisibility.SHARED,
    )
    segment = crm.segments.create_dynamic_from_saved_query(
        key="linked-segment",
        name="Linked Segment",
        saved_query_id=saved.id,
    )

    revised = crm.saved_queries.update(
        saved.id,
        SavedQueryRevision(
            name="Newsletter",
            expression=Predicate("source", QueryOperator.EQ, "newsletter"),
        ),
        expected_revision=1,
    )

    assert revised.revision == 2
    assert segment.saved_query_id == saved.id
    assert segment.saved_query_revision == 1
    assert crm.segments.evaluate(segment.id).items == (
        EntityReference("contact", linkedin.id),
    )
    assert crm.saved_queries.execute(saved.id).items == (
        EntityReference("contact", newsletter.id),
    )


def test_saved_query_optimistic_revision_conflict_is_explicit() -> None:
    crm = CRM.memory(clock=FixedClock(NOW), webhook_auto_delivery=False)
    saved = crm.saved_queries.create(
        key="all-active",
        name="All Active",
        entity_kind="contact",
        expression=Predicate("status", QueryOperator.EQ, "active"),
    )

    crm.saved_queries.update(
        saved.id,
        SavedQueryRevision(name="Active Contacts"),
        expected_revision=1,
    )

    with pytest.raises(ConflictError) as exc_info:
        crm.saved_queries.update(
            saved.id,
            SavedQueryRevision(name="Stale Update"),
            expected_revision=1,
        )

    assert exc_info.value.code == "saved_query.revision.conflict"


def test_saved_query_lifecycle_events_are_emitted() -> None:
    crm = CRM.memory(clock=FixedClock(NOW), webhook_auto_delivery=False)
    emitted: list[str] = []
    for event_type in (
        "saved_query.created",
        "saved_query.updated",
        "saved_query.archived",
    ):
        crm.events.subscribe(
            event_type,
            lambda event, emitted=emitted: emitted.append(str(event.type)),
        )

    saved = crm.saved_queries.create(
        key="active",
        name="Active",
        entity_kind="contact",
        expression=Predicate("status", QueryOperator.EQ, "active"),
    )
    revised = crm.saved_queries.update(
        saved.id,
        SavedQueryRevision(name="Active Contacts"),
        expected_revision=1,
    )
    crm.saved_queries.archive(revised.id, expected_revision=2)

    assert emitted == [
        "saved_query.created",
        "saved_query.updated",
        "saved_query.archived",
    ]
