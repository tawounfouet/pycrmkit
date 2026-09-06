"""Custom Fields facade namespace."""

from __future__ import annotations

from collections.abc import Mapping

from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.core.references import EntityReference
from pycrmkit.custom_fields import (
    CustomFieldDefinition,
    CustomFieldDefinitionId,
    CustomFieldDefinitionQuery,
    CustomFieldDefinitionRevision,
    CustomFieldOption,
    CustomFieldService,
    CustomFieldType,
    CustomFieldValue,
)
from pycrmkit.facade._runtime import CRMRuntime, revision_fields


class CustomFieldsAPI:
    """Transactional facade namespace for versioned Custom Fields."""

    def __init__(self, runtime: CRMRuntime) -> None:
        self._runtime = runtime

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
        with self._runtime.uow_factory() as uow:
            definition = CustomFieldService(
                uow.custom_fields,
                id_factory=self._runtime.id_factory,
                clock=self._runtime.clock,
            ).define(
                key=key,
                label=label,
                field_type=field_type,
                applies_to=applies_to,
                required=required,
                description=description,
                options=options,
                reference_kinds=reference_kinds,
                active=active,
                metadata=metadata,
            )
            self._runtime.record_change(
                uow,
                event_type="custom_field.defined",
                aggregate_type="custom_field_definition",
                aggregate_id=definition.id,
                changes={"fields": ["key", "label", "field_type", "applies_to"]},
            )
            uow.commit()
            return definition

    def get_definition(
        self,
        definition_id: CustomFieldDefinitionId,
        version: int | None = None,
    ) -> CustomFieldDefinition:
        with self._runtime.uow_factory() as uow:
            return uow.custom_fields.get_definition(definition_id, version)

    def revise(
        self,
        definition_id: CustomFieldDefinitionId,
        changes: CustomFieldDefinitionRevision,
    ) -> CustomFieldDefinition:
        with self._runtime.uow_factory() as uow:
            definition = CustomFieldService(
                uow.custom_fields,
                id_factory=self._runtime.id_factory,
                clock=self._runtime.clock,
            ).revise(definition_id, changes)
            self._runtime.record_change(
                uow,
                event_type="custom_field.revised",
                aggregate_type="custom_field_definition",
                aggregate_id=definition.id,
                changes={"fields": revision_fields(changes)},
            )
            uow.commit()
            return definition

    def search_definitions(
        self,
        query: CustomFieldDefinitionQuery | None = None,
        page: OffsetPageRequest | None = None,
    ) -> Page[CustomFieldDefinition]:
        with self._runtime.uow_factory() as uow:
            return CustomFieldService(uow.custom_fields).search_definitions(query, page)

    def set_value(
        self,
        definition_id: CustomFieldDefinitionId,
        entity: EntityReference,
        value: object,
    ) -> CustomFieldValue:
        with self._runtime.uow_factory() as uow:
            current = CustomFieldService(
                uow.custom_fields,
                id_factory=self._runtime.id_factory,
                clock=self._runtime.clock,
            ).set_value(definition_id, entity, value)
            self._runtime.record_change(
                uow,
                event_type="custom_field.value_set",
                aggregate_type=entity.kind,
                aggregate_id=entity.id,
                changes={"fields": ["custom_fields"]},
                payload={"definition_id": str(definition_id)},
            )
            uow.commit()
            return current

    def get_value(
        self,
        definition_id: CustomFieldDefinitionId,
        entity: EntityReference,
    ) -> CustomFieldValue:
        with self._runtime.uow_factory() as uow:
            return uow.custom_fields.get_value(definition_id, entity)

    def remove_value(
        self,
        definition_id: CustomFieldDefinitionId,
        entity: EntityReference,
    ) -> bool:
        with self._runtime.uow_factory() as uow:
            removed = CustomFieldService(
                uow.custom_fields,
                id_factory=self._runtime.id_factory,
                clock=self._runtime.clock,
            ).remove_value(definition_id, entity)
            if removed:
                self._runtime.record_change(
                    uow,
                    event_type="custom_field.value_removed",
                    aggregate_type=entity.kind,
                    aggregate_id=entity.id,
                    changes={"fields": ["custom_fields"]},
                    payload={"definition_id": str(definition_id)},
                )
            uow.commit()
            return removed

    def list_values(
        self,
        entity: EntityReference,
        page: OffsetPageRequest | None = None,
    ) -> Page[CustomFieldValue]:
        with self._runtime.uow_factory() as uow:
            return CustomFieldService(uow.custom_fields).list_values(entity, page)
