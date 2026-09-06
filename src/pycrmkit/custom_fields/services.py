"""Application service for versioned Custom Field schemas and values."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TypeVar

from pycrmkit.core.ids import IDFactory, UUID4Factory
from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.core.references import EntityReference
from pycrmkit.core.time import Clock, SystemClock
from pycrmkit.custom_fields.dto import CustomFieldDefinitionRevision, UnsetType
from pycrmkit.custom_fields.entities import (
    CustomFieldDefinition,
    CustomFieldDefinitionId,
    CustomFieldValue,
    CustomFieldValueId,
)
from pycrmkit.custom_fields.policies import (
    validate_custom_field_value,
    validate_entity_target,
)
from pycrmkit.custom_fields.queries import CustomFieldDefinitionQuery
from pycrmkit.custom_fields.repository import CustomFieldRepository
from pycrmkit.custom_fields.value_objects import CustomFieldOption, CustomFieldType
from pycrmkit.exceptions import InvalidStateError

T = TypeVar("T")


@dataclass(slots=True)
class CustomFieldService:
    """Framework-agnostic custom-field schema and value service."""

    repository: CustomFieldRepository
    id_factory: IDFactory = field(default_factory=UUID4Factory)
    clock: Clock = field(default_factory=SystemClock)

    def define(
        self,
        *,
        key: str,
        label: str,
        field_type: CustomFieldType,
        applies_to: tuple[str, ...],
        required: bool = False,
        description: str | None = None,
        options: tuple[CustomFieldOption, ...] = (),
        reference_kinds: tuple[str, ...] = (),
        active: bool = True,
        metadata: Mapping[str, object] | None = None,
    ) -> CustomFieldDefinition:
        now = self.clock.now()
        definition = CustomFieldDefinition(
            id=self.id_factory.new(CustomFieldDefinitionId),
            created_at=now,
            updated_at=now,
            key=key,
            label=label,
            field_type=field_type,
            schema_version=1,
            applies_to=applies_to,
            required=required,
            description=description,
            options=options,
            reference_kinds=reference_kinds,
            active=active,
            metadata=dict(metadata or {}),
        )
        self.repository.save_definition(definition)
        return definition

    def get_definition(
        self,
        definition_id: CustomFieldDefinitionId,
        version: int | None = None,
    ) -> CustomFieldDefinition:
        return self.repository.get_definition(definition_id, version)

    def revise(
        self,
        definition_id: CustomFieldDefinitionId,
        changes: CustomFieldDefinitionRevision,
    ) -> CustomFieldDefinition:
        current = self.repository.get_definition(definition_id)
        revised = CustomFieldDefinition(
            id=current.id,
            created_at=current.created_at,
            updated_at=self.clock.now(),
            key=current.key,
            label=self._value(changes.label, current.label),
            field_type=current.field_type,
            schema_version=current.schema_version + 1,
            applies_to=self._value(changes.applies_to, current.applies_to),
            required=self._value(changes.required, current.required),
            description=self._value(changes.description, current.description),
            options=self._value(changes.options, current.options),
            reference_kinds=self._value(changes.reference_kinds, current.reference_kinds),
            active=self._value(changes.active, current.active),
            metadata=self._value(changes.metadata, current.metadata),
        )
        self.repository.save_definition(revised)
        return revised

    def search_definitions(
        self,
        query: CustomFieldDefinitionQuery | None = None,
        page: OffsetPageRequest | None = None,
    ) -> Page[CustomFieldDefinition]:
        return self.repository.search_definitions(
            query or CustomFieldDefinitionQuery(),
            page or OffsetPageRequest(),
        )

    def set_value(
        self,
        definition_id: CustomFieldDefinitionId,
        entity: EntityReference,
        value: object,
    ) -> CustomFieldValue:
        definition = self.repository.get_definition(definition_id)
        if not definition.active:
            raise InvalidStateError(
                "inactive custom fields cannot accept new values",
                code="custom_field.inactive",
                context={"definition_id": str(definition.id)},
            )
        validate_entity_target(entity, definition.applies_to)
        normalized_value = validate_custom_field_value(
            field_type=definition.field_type,
            value=value,
            required=definition.required,
            options=definition.options,
            reference_kinds=definition.reference_kinds,
        )
        now = self.clock.now()
        existing = self.repository.find_value(definition_id, entity)
        current = CustomFieldValue(
            id=existing.id if existing else self.id_factory.new(CustomFieldValueId),
            created_at=existing.created_at if existing else now,
            updated_at=now,
            definition_id=definition.id,
            entity=entity,
            schema_version=definition.schema_version,
            value=normalized_value,
        )
        self.repository.save_value(current)
        return current

    def get_value(
        self,
        definition_id: CustomFieldDefinitionId,
        entity: EntityReference,
    ) -> CustomFieldValue:
        return self.repository.get_value(definition_id, entity)

    def remove_value(
        self,
        definition_id: CustomFieldDefinitionId,
        entity: EntityReference,
    ) -> bool:
        return self.repository.remove_value(definition_id, entity)

    def list_values(
        self,
        entity: EntityReference,
        page: OffsetPageRequest | None = None,
    ) -> Page[CustomFieldValue]:
        return self.repository.list_values(entity, page or OffsetPageRequest())

    @staticmethod
    def _value(value: T | UnsetType, current: T) -> T:
        return current if isinstance(value, UnsetType) else value
