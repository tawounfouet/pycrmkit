from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

import pytest

from pycrmkit import CRM
from pycrmkit.config import CRMConfig
from pycrmkit.core import FixedClock
from pycrmkit.core.references import EntityReference
from pycrmkit.core.unit_of_work import UnitOfWork
from pycrmkit.events import InProcessEventBus
from pycrmkit.exceptions import InvalidStateError, ValidationError
from pycrmkit.integrations.django.transactions import DjangoTransactionBridge
from pycrmkit.saved_queries import SavedQueryRevision
from pycrmkit.segments import Predicate, QueryOperator, SegmentMode

NOW = datetime(2026, 9, 29, 8, 45, tzinfo=UTC)


def _crm() -> CRM:
    bus = InProcessEventBus()

    def uow_factory() -> UnitOfWork:
        return cast(
            UnitOfWork,
            DjangoTransactionBridge(event_publisher=bus),
        )

    return CRM(
        uow_factory=uow_factory,
        event_bus=bus,
        clock=FixedClock(NOW),
        config=CRMConfig(
            events_enabled=True,
            audit_enabled=False,
        ),
        webhook_auto_delivery=False,
    )


def test_django_dynamic_segment_and_saved_query_execute_portably() -> None:
    crm = _crm()
    ada = crm.contacts.create(display_name="Ada", source="LinkedIn")
    crm.contacts.create(display_name="Grace", source="Newsletter")

    saved = crm.saved_queries.create(
        key="linkedin",
        name="LinkedIn",
        entity_kind="contact",
        expression=Predicate(
            "source",
            QueryOperator.EQ,
            "linkedin",
        ),
    )
    dynamic = crm.segments.create_dynamic_from_saved_query(
        key="linkedin-segment",
        name="LinkedIn Segment",
        saved_query_id=saved.id,
    )

    assert crm.saved_queries.execute(saved.id).items == (
        EntityReference("contact", ada.id),
    )
    assert crm.segments.evaluate(dynamic.id).items == (
        EntityReference("contact", ada.id),
    )

    revised = crm.saved_queries.update(
        saved.id,
        SavedQueryRevision(
            expression=Predicate(
                "source",
                QueryOperator.EQ,
                "newsletter",
            )
        ),
        expected_revision=1,
    )

    assert revised.revision == 2
    assert dynamic.saved_query_revision == 1
    assert crm.segments.evaluate(dynamic.id).items == (
        EntityReference("contact", ada.id),
    )


def test_django_snapshot_freezes_dynamic_membership() -> None:
    crm = _crm()
    ada = crm.contacts.create(display_name="Ada", source="LinkedIn")
    dynamic = crm.segments.create_dynamic(
        key="live-linkedin",
        name="Live LinkedIn",
        entity_kind="contact",
        query=Predicate(
            "source",
            QueryOperator.EQ,
            "linkedin",
        ),
    )

    snapshot = crm.segments.snapshot(
        dynamic.id,
        key="linkedin-2026-09-29",
        name="LinkedIn 2026-09-29",
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


def test_django_static_segment_supports_bulk_add_and_remove() -> None:
    crm = _crm()
    contacts = tuple(
        crm.contacts.create(display_name=f"Contact {index}")
        for index in range(4)
    )
    references = tuple(
        EntityReference("contact", contact.id)
        for contact in contacts
    )
    segment = crm.segments.create_static(
        key="call-list",
        name="Call List",
        entity_kind="contact",
    )

    added = crm.segments.add_members(
        segment.id,
        references,
        source="qualification",
    )

    assert len(added) == 4
    assert crm.segments.count(segment.id) == 4

    removed = crm.segments.remove_members(
        segment.id,
        references[:2],
    )

    assert removed == 2
    assert crm.segments.count(segment.id) == 2
    assert set(crm.segments.evaluate(segment.id).items) == set(
        references[2:]
    )


def test_django_query_executor_rejects_unowned_query_state() -> None:
    crm = _crm()
    crm.contacts.create(display_name="Ada")

    with pytest.raises(ValidationError) as error:
        crm.segments.create_dynamic(
            key="tagged",
            name="Tagged",
            entity_kind="contact",
            query=Predicate(
                "tag",
                QueryOperator.EQ,
                "vip",
            ),
        )

    assert error.value.code == "segment.query.django.unsupported_field"
