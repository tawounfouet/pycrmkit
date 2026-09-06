"""Versioned custom-field definitions and entity values."""

from __future__ import annotations

from dataclasses import dataclass, field

from pycrmkit.core.entities import TimestampedEntity
from pycrmkit.core.ids import UUIDId
from pycrmkit.core.references import EntityReference
from pycrmkit.custom_fields.policies import (
    normalize_entity_kinds,
    normalize_label,
    normalize_optional_text,
    validate_definition_shape,
)
from pycrmkit.custom_fields.value_objects import (
    CustomFieldOption,
    CustomFieldType,
    normalize_custom_field_key,
)
from pycrmkit.exceptions import ValidationError


class CustomFieldDefinitionId(UUIDId):
    """Stable identity shared by all revisions of a custom-field definition."""


class CustomFieldValueId(UUIDId):
    """Strongly typed identity for one entity custom-field value."""


@dataclass(eq=False, slots=True)
class CustomFieldDefinition(TimestampedEntity[CustomFieldDefinitionId]):
    """One immutable-in-history schema revision for a business-defined field."""

    key: str
    label: str
    field_type: CustomFieldType
    schema_version: int
    applies_to: tuple[str, ...]
    required: bool = False
    description: str | None = None
    options: tuple[CustomFieldOption, ...] = ()
    reference_kinds: tuple[str, ...] = ()
    active: bool = True
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        TimestampedEntity.__post_init__(self)
        self.key = normalize_custom_field_key(self.key)
        self.label = normalize_label(self.label)
        self.description = normalize_optional_text(self.description)
        if self.schema_version < 1:
            raise ValidationError(
                "custom field schema_version must be >= 1",
                code="custom_field.schema_version.invalid",
            )
        self.applies_to = normalize_entity_kinds(tuple(self.applies_to))
        self.options, self.reference_kinds = validate_definition_shape(
            field_type=self.field_type,
            options=tuple(self.options),
            reference_kinds=tuple(self.reference_kinds),
        )
        self.metadata = dict(self.metadata)


@dataclass(eq=False, slots=True)
class CustomFieldValue(TimestampedEntity[CustomFieldValueId]):
    """Current value for one definition/entity pair with validating schema revision."""

    definition_id: CustomFieldDefinitionId
    entity: EntityReference
    schema_version: int
    value: object

    def __post_init__(self) -> None:
        TimestampedEntity.__post_init__(self)
        if self.schema_version < 1:
            raise ValidationError(
                "custom field value schema_version must be >= 1",
                code="custom_field.value.schema_version.invalid",
            )
