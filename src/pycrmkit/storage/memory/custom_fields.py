"""In-memory CustomFieldRepository implementation."""

from __future__ import annotations

from copy import deepcopy

from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.core.references import EntityReference, normalize_entity_kind
from pycrmkit.custom_fields.entities import (
    CustomFieldDefinition,
    CustomFieldDefinitionId,
    CustomFieldValue,
)
from pycrmkit.custom_fields.queries import CustomFieldDefinitionQuery
from pycrmkit.custom_fields.value_objects import normalize_custom_field_key
from pycrmkit.exceptions import ConflictError, DuplicateError, NotFoundError
from pycrmkit.storage.memory._state import _MemoryState


class MemoryCustomFieldRepository:
    """Copy-isolated repository for versioned field definitions and current values."""

    def __init__(self, state: _MemoryState | None = None) -> None:
        self._state = state or _MemoryState()

    def get_definition(
        self,
        definition_id: CustomFieldDefinitionId,
        version: int | None = None,
    ) -> CustomFieldDefinition:
        versions = self._state.custom_field_definitions.get(definition_id, [])
        if not versions:
            raise NotFoundError(
                "Custom field definition not found",
                code="custom_field.not_found",
                context={"definition_id": str(definition_id)},
            )
        if version is None:
            return deepcopy(versions[-1])
        for definition in versions:
            if definition.schema_version == version:
                return deepcopy(definition)
        raise NotFoundError(
            "Custom field definition revision not found",
            code="custom_field.version.not_found",
            context={"definition_id": str(definition_id), "schema_version": version},
        )

    def find_definition_by_key(self, key: str) -> CustomFieldDefinition | None:
        normalized = normalize_custom_field_key(key)
        for versions in self._state.custom_field_definitions.values():
            if versions[-1].key == normalized:
                return deepcopy(versions[-1])
        return None

    def save_definition(self, definition: CustomFieldDefinition) -> None:
        existing_by_key = self.find_definition_by_key(definition.key)
        if existing_by_key is not None and existing_by_key.id != definition.id:
            raise DuplicateError(
                "Custom field key already exists",
                code="custom_field.key.duplicate",
                context={"key": definition.key},
            )
        versions = self._state.custom_field_definitions.setdefault(definition.id, [])
        expected = 1 if not versions else versions[-1].schema_version + 1
        if definition.schema_version != expected:
            raise ConflictError(
                "Custom field revisions must be appended sequentially",
                code="custom_field.schema_version.conflict",
                context={"expected": expected, "actual": definition.schema_version},
            )
        if versions and definition.key != versions[-1].key:
            raise ConflictError(
                "Custom field key is immutable",
                code="custom_field.key.immutable",
            )
        if versions and definition.field_type != versions[-1].field_type:
            raise ConflictError(
                "Custom field type is immutable",
                code="custom_field.type.immutable",
            )
        versions.append(deepcopy(definition))

    def list_definition_versions(
        self,
        definition_id: CustomFieldDefinitionId,
    ) -> tuple[CustomFieldDefinition, ...]:
        versions = self._state.custom_field_definitions.get(definition_id, [])
        return tuple(deepcopy(versions))

    def search_definitions(
        self,
        query: CustomFieldDefinitionQuery,
        page: OffsetPageRequest,
    ) -> Page[CustomFieldDefinition]:
        definitions = [
            versions[-1] for versions in self._state.custom_field_definitions.values()
        ]
        if query.key is not None:
            key = normalize_custom_field_key(query.key)
            definitions = [item for item in definitions if item.key == key]
        if query.field_type is not None:
            definitions = [item for item in definitions if item.field_type is query.field_type]
        if query.entity_kind is not None:
            entity_kind = normalize_entity_kind(query.entity_kind)
            definitions = [item for item in definitions if entity_kind in item.applies_to]
        if not query.include_inactive:
            definitions = [item for item in definitions if item.active]
        definitions.sort(key=lambda item: (item.key, str(item.id)))
        total = len(definitions)
        selected = definitions[page.offset : page.offset + page.limit]
        return Page(
            items=tuple(deepcopy(selected)),
            limit=page.limit,
            offset=page.offset,
            total=total,
        )

    def get_value(
        self,
        definition_id: CustomFieldDefinitionId,
        entity: EntityReference,
    ) -> CustomFieldValue:
        value = self.find_value(definition_id, entity)
        if value is None:
            raise NotFoundError(
                "Custom field value not found",
                code="custom_field.value.not_found",
                context={
                    "definition_id": str(definition_id),
                    "entity_kind": entity.kind,
                    "entity_id": str(entity.id),
                },
            )
        return value

    def find_value(
        self,
        definition_id: CustomFieldDefinitionId,
        entity: EntityReference,
    ) -> CustomFieldValue | None:
        value = self._state.custom_field_values.get((definition_id, entity))
        return deepcopy(value) if value is not None else None

    def save_value(self, value: CustomFieldValue) -> None:
        self._state.custom_field_values[(value.definition_id, value.entity)] = deepcopy(value)

    def remove_value(
        self,
        definition_id: CustomFieldDefinitionId,
        entity: EntityReference,
    ) -> bool:
        return self._state.custom_field_values.pop((definition_id, entity), None) is not None

    def list_values(
        self,
        entity: EntityReference,
        page: OffsetPageRequest,
    ) -> Page[CustomFieldValue]:
        values = [
            value for value in self._state.custom_field_values.values() if value.entity == entity
        ]
        values.sort(key=lambda value: (value.created_at, str(value.id)))
        total = len(values)
        selected = values[page.offset : page.offset + page.limit]
        return Page(
            items=tuple(deepcopy(selected)),
            limit=page.limit,
            offset=page.offset,
            total=total,
        )
