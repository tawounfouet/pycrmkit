"""Execute Custom Field contracts against a test-only reference repository."""

from __future__ import annotations

from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.core.references import EntityReference
from pycrmkit.custom_fields.entities import (
    CustomFieldDefinition,
    CustomFieldDefinitionId,
    CustomFieldValue,
)
from pycrmkit.custom_fields.queries import CustomFieldDefinitionQuery
from pycrmkit.custom_fields.value_objects import normalize_custom_field_key
from pycrmkit.exceptions import ConflictError, DuplicateError, NotFoundError
from tests.contracts.custom_fields_repository import assert_custom_field_repository_contract


class ReferenceCustomFieldRepository:
    """Minimal test-only implementation; not the future Memory adapter."""

    def __init__(self) -> None:
        self.definitions: dict[CustomFieldDefinitionId, list[CustomFieldDefinition]] = {}
        self.values: dict[tuple[CustomFieldDefinitionId, EntityReference], CustomFieldValue] = {}

    def get_definition(
        self,
        definition_id: CustomFieldDefinitionId,
        version: int | None = None,
    ) -> CustomFieldDefinition:
        versions = self.definitions.get(definition_id, [])
        if not versions:
            raise NotFoundError("custom field definition not found", code="custom_field.not_found")
        if version is None:
            return versions[-1]
        for definition in versions:
            if definition.schema_version == version:
                return definition
        raise NotFoundError("custom field revision not found", code="custom_field.version.not_found")

    def find_definition_by_key(self, key: str) -> CustomFieldDefinition | None:
        normalized = normalize_custom_field_key(key)
        for versions in self.definitions.values():
            if versions[-1].key == normalized:
                return versions[-1]
        return None

    def save_definition(self, definition: CustomFieldDefinition) -> None:
        by_key = self.find_definition_by_key(definition.key)
        if by_key is not None and by_key.id != definition.id:
            raise DuplicateError("duplicate custom field key", code="custom_field.key.duplicate")
        versions = self.definitions.setdefault(definition.id, [])
        expected = 1 if not versions else versions[-1].schema_version + 1
        if definition.schema_version != expected:
            raise ConflictError(
                "custom field revisions must be appended sequentially",
                code="custom_field.schema_version.conflict",
            )
        if versions and definition.key != versions[-1].key:
            raise ConflictError("custom field key is immutable", code="custom_field.key.immutable")
        if versions and definition.field_type != versions[-1].field_type:
            raise ConflictError("custom field type is immutable", code="custom_field.type.immutable")
        versions.append(definition)

    def list_definition_versions(
        self,
        definition_id: CustomFieldDefinitionId,
    ) -> tuple[CustomFieldDefinition, ...]:
        if definition_id not in self.definitions:
            return ()
        return tuple(self.definitions[definition_id])

    def search_definitions(
        self,
        query: CustomFieldDefinitionQuery,
        page: OffsetPageRequest,
    ) -> Page[CustomFieldDefinition]:
        items = [versions[-1] for versions in self.definitions.values()]
        if query.key is not None:
            normalized = normalize_custom_field_key(query.key)
            items = [item for item in items if item.key == normalized]
        if query.field_type is not None:
            items = [item for item in items if item.field_type is query.field_type]
        if query.entity_kind is not None:
            items = [item for item in items if query.entity_kind in item.applies_to]
        if not query.include_inactive:
            items = [item for item in items if item.active]
        items.sort(key=lambda item: (item.key, str(item.id)))
        total = len(items)
        selected = tuple(items[page.offset : page.offset + page.limit])
        return Page(items=selected, limit=page.limit, offset=page.offset, total=total)

    def get_value(
        self,
        definition_id: CustomFieldDefinitionId,
        entity: EntityReference,
    ) -> CustomFieldValue:
        found = self.find_value(definition_id, entity)
        if found is None:
            raise NotFoundError("custom field value not found", code="custom_field.value.not_found")
        return found

    def find_value(
        self,
        definition_id: CustomFieldDefinitionId,
        entity: EntityReference,
    ) -> CustomFieldValue | None:
        return self.values.get((definition_id, entity))

    def save_value(self, value: CustomFieldValue) -> None:
        self.values[(value.definition_id, value.entity)] = value

    def remove_value(
        self,
        definition_id: CustomFieldDefinitionId,
        entity: EntityReference,
    ) -> bool:
        return self.values.pop((definition_id, entity), None) is not None

    def list_values(
        self,
        entity: EntityReference,
        page: OffsetPageRequest,
    ) -> Page[CustomFieldValue]:
        items = [value for value in self.values.values() if value.entity == entity]
        items.sort(key=lambda value: (value.created_at, str(value.id)))
        total = len(items)
        selected = tuple(items[page.offset : page.offset + page.limit])
        return Page(items=selected, limit=page.limit, offset=page.offset, total=total)


def test_reference_repository_passes_contract() -> None:
    assert_custom_field_repository_contract(ReferenceCustomFieldRepository())
