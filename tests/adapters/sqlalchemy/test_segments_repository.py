from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from pycrmkit.contacts import Contact, ContactId
from pycrmkit.core.pagination import OffsetPageRequest
from pycrmkit.core.references import EntityReference
from pycrmkit.exceptions import DuplicateError
from pycrmkit.segments import (
    And,
    Predicate,
    QueryOperator,
    Segment,
    SegmentId,
    SegmentMember,
    SegmentMode,
)
from pycrmkit.storage.sqlalchemy.models import (
    CustomFieldDefinitionModel,
    CustomFieldValueModel,
    TagAssignmentModel,
    TagModel,
)
from pycrmkit.storage.sqlalchemy.repositories import (
    SQLAlchemyContactRepository,
    SQLAlchemySegmentMembershipRepository,
    SQLAlchemySegmentQueryExecutor,
    SQLAlchemySegmentRepository,
)

NOW = datetime(2026, 9, 29, 12, tzinfo=UTC)


def test_sqlalchemy_segment_key_and_static_membership_are_unique(
    session: Session,
) -> None:
    segments = SQLAlchemySegmentRepository(session)
    memberships = SQLAlchemySegmentMembershipRepository(session)
    first = Segment(
        id=SegmentId.parse("00000000-0000-0000-0000-000000000101"),
        created_at=NOW,
        updated_at=NOW,
        key="enterprise",
        name="Enterprise",
        entity_kind="contact",
        mode=SegmentMode.STATIC,
    )
    duplicate = Segment(
        id=SegmentId.parse("00000000-0000-0000-0000-000000000102"),
        created_at=NOW,
        updated_at=NOW,
        key="enterprise",
        name="Duplicate",
        entity_kind="contact",
        mode=SegmentMode.STATIC,
    )
    segments.save(first)

    with pytest.raises(DuplicateError) as key_error:
        segments.save(duplicate)
    assert key_error.value.code == "segment.key.duplicate"

    entity = EntityReference(
        "contact",
        ContactId.parse("00000000-0000-0000-0000-000000000111"),
    )
    member = SegmentMember(first.id, entity, NOW)
    memberships.add(member)

    with pytest.raises(DuplicateError) as member_error:
        memberships.add(member)
    assert member_error.value.code == "segment.member.duplicate"

    page = memberships.list(first.id, OffsetPageRequest())
    assert page.items == (member,)
    assert memberships.count(first.id) == 1


def test_sqlalchemy_query_executor_filters_canonical_contact_state(
    session: Session,
) -> None:
    contacts = SQLAlchemyContactRepository(session)
    linkedin = Contact(
        id=ContactId.parse("00000000-0000-0000-0000-000000000121"),
        created_at=NOW,
        updated_at=NOW,
        display_name="Ada",
        source="LinkedIn",
    )
    newsletter = Contact(
        id=ContactId.parse("00000000-0000-0000-0000-000000000122"),
        created_at=NOW,
        updated_at=NOW,
        display_name="Grace",
        source="Newsletter",
    )
    contacts.save(linkedin)
    contacts.save(newsletter)
    session.flush()

    result = SQLAlchemySegmentQueryExecutor(session).execute(
        "contact",
        Predicate("source", QueryOperator.EQ, "linkedin"),
        OffsetPageRequest(),
        at=NOW,
    )

    assert result.items == (EntityReference("contact", linkedin.id),)
    assert result.total == 1


def test_sqlalchemy_query_executor_compiles_tag_and_custom_field_predicates(
    session: Session,
) -> None:
    contacts = SQLAlchemyContactRepository(session)
    ada = Contact(
        id=ContactId.parse("00000000-0000-0000-0000-000000000131"),
        created_at=NOW,
        updated_at=NOW,
        display_name="Ada",
    )
    grace = Contact(
        id=ContactId.parse("00000000-0000-0000-0000-000000000132"),
        created_at=NOW,
        updated_at=NOW,
        display_name="Grace",
    )
    contacts.save(ada)
    contacts.save(grace)

    definition_id = "00000000-0000-0000-0000-000000000141"
    session.add(
        CustomFieldDefinitionModel(
            id=definition_id,
            schema_version=1,
            key="annual_budget",
            label="Annual Budget",
            field_type="decimal",
            applies_to_json=["contact"],
            required=False,
            description=None,
            options_json=[],
            reference_kinds_json=[],
            active=True,
            metadata_json={},
            created_at=NOW,
            updated_at=NOW,
        )
    )
    session.add_all(
        [
            CustomFieldValueModel(
                id="00000000-0000-0000-0000-000000000151",
                definition_id=definition_id,
                entity_kind="contact",
                entity_id=str(ada.id),
                schema_version=1,
                value_json={"type": "decimal", "value": "150000"},
                created_at=NOW,
                updated_at=NOW,
            ),
            CustomFieldValueModel(
                id="00000000-0000-0000-0000-000000000152",
                definition_id=definition_id,
                entity_kind="contact",
                entity_id=str(grace.id),
                schema_version=1,
                value_json={"type": "decimal", "value": "50000"},
                created_at=NOW,
                updated_at=NOW,
            ),
        ]
    )

    tag_id = "00000000-0000-0000-0000-000000000161"
    session.add(
        TagModel(
            id=tag_id,
            name="VIP",
            normalized_name="vip",
            metadata_json={},
            created_at=NOW,
            updated_at=NOW,
        )
    )
    session.add(
        TagAssignmentModel(
            id="00000000-0000-0000-0000-000000000162",
            tag_id=tag_id,
            entity_kind="contact",
            entity_id=str(ada.id),
            created_at=NOW,
            updated_at=NOW,
        )
    )
    session.flush()

    result = SQLAlchemySegmentQueryExecutor(session).execute(
        "contact",
        And(
            (
                Predicate(
                    "custom.annual_budget",
                    QueryOperator.GTE,
                    Decimal("100000"),
                ),
                Predicate("tag", QueryOperator.EQ, "vip"),
            )
        ),
        OffsetPageRequest(),
        at=NOW,
    )

    assert result.items == (EntityReference("contact", ada.id),)
    assert result.total == 1
