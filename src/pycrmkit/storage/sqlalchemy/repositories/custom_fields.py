"""SQLAlchemy CustomFieldRepository implementation."""

from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.core.references import EntityReference, normalize_entity_kind
from pycrmkit.custom_fields import (
    CustomFieldDefinition,
    CustomFieldDefinitionId,
    CustomFieldDefinitionQuery,
    CustomFieldValue,
)
from pycrmkit.custom_fields.value_objects import normalize_custom_field_key
from pycrmkit.exceptions import ConflictError, DuplicateError, NotFoundError
from pycrmkit.storage.sqlalchemy.mappers import (
    custom_field_definition_from_model,
    custom_field_definition_to_model,
    custom_field_value_from_model,
    custom_field_value_to_model,
)
from pycrmkit.storage.sqlalchemy.models.custom_field import (
    CustomFieldDefinitionModel,
    CustomFieldValueModel,
)


class SQLAlchemyCustomFieldRepository:
    """Version-preserving SQLAlchemy adapter for Custom Field schemas and values."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_definition(
        self,
        definition_id: CustomFieldDefinitionId,
        version: int | None = None,
    ) -> CustomFieldDefinition:
        identifier = str(definition_id)
        if version is None:
            model = self.session.scalar(
                select(CustomFieldDefinitionModel)
                .where(CustomFieldDefinitionModel.id == identifier)
                .order_by(
                    CustomFieldDefinitionModel.schema_version.desc()
                )
                .limit(1)
            )
            if model is None:
                raise NotFoundError(
                    "Custom field definition not found",
                    code="custom_field.not_found",
                    context={"definition_id": identifier},
                )
            return custom_field_definition_from_model(model)

        model = self.session.get(
            CustomFieldDefinitionModel,
            (identifier, version),
        )
        if model is None:
            has_definition = self.session.scalar(
                select(func.count())
                .select_from(CustomFieldDefinitionModel)
                .where(CustomFieldDefinitionModel.id == identifier)
            )
            if not has_definition:
                raise NotFoundError(
                    "Custom field definition not found",
                    code="custom_field.not_found",
                    context={"definition_id": identifier},
                )
            raise NotFoundError(
                "Custom field definition revision not found",
                code="custom_field.version.not_found",
                context={
                    "definition_id": identifier,
                    "schema_version": version,
                },
            )
        return custom_field_definition_from_model(model)

    def find_definition_by_key(
        self,
        key: str,
    ) -> CustomFieldDefinition | None:
        normalized = normalize_custom_field_key(key)
        model = self.session.scalar(
            select(CustomFieldDefinitionModel)
            .where(CustomFieldDefinitionModel.key == normalized)
            .order_by(
                CustomFieldDefinitionModel.schema_version.desc()
            )
            .limit(1)
        )
        return (
            None
            if model is None
            else custom_field_definition_from_model(model)
        )

    def save_definition(
        self,
        definition: CustomFieldDefinition,
    ) -> None:
        with self.session.no_autoflush:
            existing_by_key = self.find_definition_by_key(
                definition.key
            )
        if (
            existing_by_key is not None
            and existing_by_key.id != definition.id
        ):
            raise DuplicateError(
                "Custom field key already exists",
                code="custom_field.key.duplicate",
                context={"key": definition.key},
            )
        identifier = str(definition.id)
        current = self.session.scalar(
            select(CustomFieldDefinitionModel)
            .where(CustomFieldDefinitionModel.id == identifier)
            .order_by(
                CustomFieldDefinitionModel.schema_version.desc()
            )
            .limit(1)
        )
        expected = (
            1
            if current is None
            else current.schema_version + 1
        )
        if definition.schema_version != expected:
            raise ConflictError(
                "Custom field revisions must be appended sequentially",
                code="custom_field.schema_version.conflict",
                context={
                    "expected": expected,
                    "actual": definition.schema_version,
                },
            )
        if current is not None and definition.key != current.key:
            raise ConflictError(
                "Custom field key is immutable",
                code="custom_field.key.immutable",
            )
        if (
            current is not None
            and definition.field_type.value != current.field_type
        ):
            raise ConflictError(
                "Custom field type is immutable",
                code="custom_field.type.immutable",
            )
        self.session.add(
            custom_field_definition_to_model(definition)
        )

    def list_definition_versions(
        self,
        definition_id: CustomFieldDefinitionId,
    ) -> tuple[CustomFieldDefinition, ...]:
        models = self.session.scalars(
            select(CustomFieldDefinitionModel)
            .where(
                CustomFieldDefinitionModel.id
                == str(definition_id)
            )
            .order_by(
                CustomFieldDefinitionModel.schema_version.asc()
            )
        ).all()
        return tuple(
            custom_field_definition_from_model(model)
            for model in models
        )

    def search_definitions(
        self,
        query: CustomFieldDefinitionQuery,
        page: OffsetPageRequest,
    ) -> Page[CustomFieldDefinition]:
        latest = (
            select(
                CustomFieldDefinitionModel.id.label(
                    "definition_id"
                ),
                func.max(
                    CustomFieldDefinitionModel.schema_version
                ).label("max_version"),
            )
            .group_by(CustomFieldDefinitionModel.id)
            .subquery()
        )
        models = self.session.scalars(
            select(CustomFieldDefinitionModel).join(
                latest,
                (
                    CustomFieldDefinitionModel.id
                    == latest.c.definition_id
                )
                & (
                    CustomFieldDefinitionModel.schema_version
                    == latest.c.max_version
                ),
            )
        ).all()
        definitions = [
            custom_field_definition_from_model(model)
            for model in models
        ]
        if query.key is not None:
            normalized = normalize_custom_field_key(query.key)
            definitions = [
                item
                for item in definitions
                if item.key == normalized
            ]
        if query.field_type is not None:
            definitions = [
                item
                for item in definitions
                if item.field_type is query.field_type
            ]
        if query.entity_kind is not None:
            entity_kind = normalize_entity_kind(
                query.entity_kind
            )
            definitions = [
                item
                for item in definitions
                if entity_kind in item.applies_to
            ]
        if not query.include_inactive:
            definitions = [
                item
                for item in definitions
                if item.active
            ]
        definitions.sort(
            key=lambda item: (item.key, str(item.id))
        )
        total = len(definitions)
        selected = definitions[
            page.offset : page.offset + page.limit
        ]
        return Page(
            items=tuple(selected),
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
        model = self.session.scalar(
            select(CustomFieldValueModel).where(
                CustomFieldValueModel.definition_id
                == str(definition_id),
                CustomFieldValueModel.entity_kind
                == entity.kind,
                CustomFieldValueModel.entity_id
                == str(entity.id),
            )
        )
        return (
            None
            if model is None
            else custom_field_value_from_model(model)
        )

    def save_value(self, value: CustomFieldValue) -> None:
        existing = self.session.scalar(
            select(CustomFieldValueModel).where(
                CustomFieldValueModel.definition_id
                == str(value.definition_id),
                CustomFieldValueModel.entity_kind
                == value.entity.kind,
                CustomFieldValueModel.entity_id
                == str(value.entity.id),
            )
        )
        by_id = self.session.get(
            CustomFieldValueModel,
            str(value.id),
        )
        if (
            existing is not None
            and existing.id != str(value.id)
        ):
            self.session.delete(existing)
            by_id = None
        target = custom_field_value_to_model(value, by_id)
        if by_id is None:
            self.session.add(target)

    def remove_value(
        self,
        definition_id: CustomFieldDefinitionId,
        entity: EntityReference,
    ) -> bool:
        result = self.session.execute(
            delete(CustomFieldValueModel).where(
                CustomFieldValueModel.definition_id
                == str(definition_id),
                CustomFieldValueModel.entity_kind
                == entity.kind,
                CustomFieldValueModel.entity_id
                == str(entity.id),
            )
        )
        return bool(result.rowcount)

    def list_values(
        self,
        entity: EntityReference,
        page: OffsetPageRequest,
    ) -> Page[CustomFieldValue]:
        statement = (
            select(CustomFieldValueModel)
            .where(
                CustomFieldValueModel.entity_kind
                == entity.kind,
                CustomFieldValueModel.entity_id
                == str(entity.id),
            )
            .order_by(
                CustomFieldValueModel.created_at.asc(),
                CustomFieldValueModel.id.asc(),
            )
        )
        count_statement = select(func.count()).select_from(
            statement.order_by(None).subquery()
        )
        total = int(
            self.session.scalar(count_statement) or 0
        )
        models = self.session.scalars(
            statement.offset(page.offset).limit(page.limit)
        ).all()
        return Page(
            items=tuple(
                custom_field_value_from_model(model)
                for model in models
            ),
            limit=page.limit,
            offset=page.offset,
            total=total,
        )
