from datetime import UTC, datetime
from uuid import UUID

import pytest

from pycrmkit.core.ids import EntityId
from pycrmkit.core.references import EntityReference
from pycrmkit.core.time import FixedClock
from pycrmkit.custom_fields.dto import CustomFieldDefinitionRevision
from pycrmkit.custom_fields.services import CustomFieldService
from pycrmkit.custom_fields.value_objects import CustomFieldOption, CustomFieldType
from pycrmkit.exceptions import InvalidStateError, ValidationError
from tests.contracts.test_custom_fields_repository_reference import ReferenceCustomFieldRepository


class SequentialFactory:
    def __init__(self) -> None:
        self.counter = 1000

    def new(self, id_type):  # type: ignore[no-untyped-def]
        value = UUID(int=self.counter)
        self.counter += 1
        return id_type(value)


def service() -> CustomFieldService:
    return CustomFieldService(
        repository=ReferenceCustomFieldRepository(),
        id_factory=SequentialFactory(),
        clock=FixedClock(datetime(2026, 9, 6, 16, 0, tzinfo=UTC)),
    )


def test_define_revise_and_preserve_schema_history() -> None:
    current = service()
    definition = current.define(
        key="customer_tier",
        label="Customer Tier",
        field_type=CustomFieldType.ENUM,
        applies_to=("contact", "organization"),
        options=(CustomFieldOption("gold", "Gold"),),
    )
    revised = current.revise(
        definition.id,
        CustomFieldDefinitionRevision(
            options=(
                CustomFieldOption("gold", "Gold"),
                CustomFieldOption("silver", "Silver"),
            )
        ),
    )
    assert revised.id == definition.id
    assert revised.schema_version == 2
    assert current.repository.get_definition(definition.id, 1).schema_version == 1
    assert current.repository.get_definition(definition.id).schema_version == 2


def test_set_value_uses_latest_schema_version_and_reuses_value_identity() -> None:
    current = service()
    definition = current.define(
        key="nickname",
        label="Nickname",
        field_type=CustomFieldType.STRING,
        applies_to=("contact",),
    )
    entity = EntityReference("contact", EntityId(UUID(int=7)))
    first = current.set_value(definition.id, entity, "  Tom  ")
    assert first.value == "Tom"
    assert first.schema_version == 1

    revised = current.revise(
        definition.id,
        CustomFieldDefinitionRevision(label="Preferred Name"),
    )
    second = current.set_value(revised.id, entity, "Thomas")
    assert second.id == first.id
    assert second.schema_version == 2
    assert second.value == "Thomas"


def test_custom_field_rejects_wrong_entity_kind() -> None:
    current = service()
    definition = current.define(
        key="contact_only",
        label="Contact only",
        field_type=CustomFieldType.STRING,
        applies_to=("contact",),
    )
    with pytest.raises(ValidationError):
        current.set_value(
            definition.id,
            EntityReference("organization", EntityId(UUID(int=8))),
            "value",
        )


def test_inactive_definition_rejects_new_values() -> None:
    current = service()
    definition = current.define(
        key="legacy",
        label="Legacy",
        field_type=CustomFieldType.STRING,
        applies_to=("contact",),
    )
    inactive = current.revise(
        definition.id,
        CustomFieldDefinitionRevision(active=False),
    )
    with pytest.raises(InvalidStateError):
        current.set_value(
            inactive.id,
            EntityReference("contact", EntityId(UUID(int=9))),
            "x",
        )


def test_remove_value_is_idempotent() -> None:
    current = service()
    definition = current.define(
        key="score",
        label="Score",
        field_type=CustomFieldType.INTEGER,
        applies_to=("contact",),
    )
    entity = EntityReference("contact", EntityId(UUID(int=10)))
    current.set_value(definition.id, entity, 10)
    assert current.remove_value(definition.id, entity) is True
    assert current.remove_value(definition.id, entity) is False
