from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from pycrmkit import CRM
from pycrmkit.core import FixedClock
from pycrmkit.core.references import EntityReference
from pycrmkit.core.unit_of_work import UnitOfWork
from pycrmkit.custom_fields import CustomFieldType
from pycrmkit.events import InProcessEventBus
from pycrmkit.saved_queries import SavedQueryRevision
from pycrmkit.segments import (
    And,
    Predicate,
    QueryOperator,
    RelativeTimeUnit,
    RelativeTimeValue,
    SortDirection,
    SortExpression,
)
from pycrmkit.storage.sqlalchemy import Base, SQLAlchemyUnitOfWork

NOW = datetime(2026, 9, 29, 12, tzinfo=UTC)


def _crm(clock: FixedClock) -> tuple[CRM, object]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
    bus = InProcessEventBus()

    def uow_factory() -> UnitOfWork:
        return SQLAlchemyUnitOfWork(factory, event_publisher=bus)

    crm = CRM(
        uow_factory=uow_factory,
        event_bus=bus,
        clock=clock,
        webhook_auto_delivery=False,
    )
    return crm, engine


def test_sqlalchemy_facade_executes_tag_custom_field_and_saved_query() -> None:
    crm, engine = _crm(FixedClock(NOW))
    try:
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
        segment = crm.segments.create_dynamic_from_saved_query(
            key="vip-segment",
            name="VIP Segment",
            saved_query_id=saved.id,
        )

        assert crm.saved_queries.execute(saved.id).items == (
            EntityReference("contact", ada.id),
        )
        assert crm.segments.evaluate(segment.id).items == (
            EntityReference("contact", ada.id),
        )
    finally:
        engine.dispose()


def test_sqlalchemy_relative_time_ordering_and_saved_query_revision_binding() -> None:
    clock = FixedClock(NOW - timedelta(days=45))
    crm, engine = _crm(clock)
    try:
        old = crm.contacts.create(display_name="Old", source="Legacy")
        clock.set(NOW - timedelta(days=10))
        beta = crm.contacts.create(display_name="Beta", source="LinkedIn")
        clock.set(NOW - timedelta(days=5))
        alpha = crm.contacts.create(display_name="Alpha", source="LinkedIn")
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
        segment = crm.segments.create_dynamic_from_saved_query(
            key="recent-segment",
            name="Recent Segment",
            saved_query_id=saved.id,
        )

        revised = crm.saved_queries.update(
            saved.id,
            SavedQueryRevision(
                expression=Predicate(
                    "source",
                    QueryOperator.EQ,
                    "linkedin",
                )
            ),
            expected_revision=1,
        )

        original = crm.saved_queries.execute(saved.id, revision=1)
        latest = crm.saved_queries.execute(revised.id)

        assert EntityReference("contact", old.id) not in original.items
        assert original.items == (
            EntityReference("contact", alpha.id),
            EntityReference("contact", beta.id),
        )
        assert latest.items == (
            EntityReference("contact", beta.id),
            EntityReference("contact", alpha.id),
        )
        assert segment.saved_query_revision == 1
        assert crm.segments.evaluate(segment.id).items == original.items
    finally:
        engine.dispose()
