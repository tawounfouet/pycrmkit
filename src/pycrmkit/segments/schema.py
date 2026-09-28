"""Typed field schemas for portable Segmentation expressions."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import NoReturn
from uuid import UUID

from pycrmkit.core.ids import UUIDId
from pycrmkit.core.time import as_utc
from pycrmkit.core.value_objects import ValueObject
from pycrmkit.custom_fields import CustomFieldDefinition, CustomFieldType
from pycrmkit.exceptions import NotFoundError, ValidationError
from pycrmkit.segments.enums import QueryFieldType, QueryOperator
from pycrmkit.segments.expressions import (
    And,
    Not,
    Or,
    Predicate,
    QueryExpression,
    RelativeTimeValue,
    normalize_query_field_key,
    validate_expression_complexity,
)

_EQUALITY = frozenset(
    {
        QueryOperator.EQ,
        QueryOperator.NE,
        QueryOperator.IN,
        QueryOperator.NOT_IN,
    }
)
_ORDERED = frozenset(
    {
        QueryOperator.EQ,
        QueryOperator.NE,
        QueryOperator.LT,
        QueryOperator.LTE,
        QueryOperator.GT,
        QueryOperator.GTE,
        QueryOperator.IN,
        QueryOperator.NOT_IN,
    }
)
_STRING = frozenset(
    {
        *_ORDERED,
        QueryOperator.CONTAINS,
        QueryOperator.STARTS_WITH,
        QueryOperator.ENDS_WITH,
    }
)
_NULL = frozenset({QueryOperator.IS_NULL, QueryOperator.IS_NOT_NULL})


def _normalize_text(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).strip().split()).casefold()


@dataclass(frozen=True, slots=True)
class QueryField(ValueObject):
    """One allow-listed field and its portable comparison semantics."""

    key: str
    type: QueryFieldType
    nullable: bool = False
    enum_values: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "key", normalize_query_field_key(self.key))
        object.__setattr__(self, "type", QueryFieldType(self.type))
        values = tuple(_normalize_text(value) for value in self.enum_values)
        object.__setattr__(self, "enum_values", values)
        if self.type is not QueryFieldType.ENUM and values:
            raise ValidationError(
                "enum_values are only valid for enum query fields",
                code="segment.query.schema.invalid",
                context={"field": self.key},
            )

    @property
    def supported_operators(self) -> frozenset[QueryOperator]:
        if self.type is QueryFieldType.STRING:
            base = _STRING
        elif self.type in {
            QueryFieldType.INTEGER,
            QueryFieldType.DECIMAL,
            QueryFieldType.DATE,
            QueryFieldType.DATETIME,
        }:
            base = _ORDERED
        else:
            base = _EQUALITY
        return base | _NULL if self.nullable else base

    def normalize_value(self, value: object) -> object:
        """Validate and normalize one value for this field."""

        if value is None:
            if self.nullable:
                return None
            self._invalid_value(value)

        if self.type is QueryFieldType.STRING:
            if not isinstance(value, str):
                self._invalid_value(value)
            return _normalize_text(value)

        if self.type is QueryFieldType.INTEGER:
            if type(value) is not int:
                self._invalid_value(value)
            return value

        if self.type is QueryFieldType.DECIMAL:
            if type(value) is not Decimal or not value.is_finite():
                self._invalid_value(value)
            return value

        if self.type is QueryFieldType.BOOLEAN:
            if type(value) is not bool:
                self._invalid_value(value)
            return value

        if self.type is QueryFieldType.DATE:
            if type(value) is not date:
                self._invalid_value(value)
            return value

        if self.type is QueryFieldType.DATETIME:
            if not isinstance(value, datetime):
                self._invalid_value(value)
            return as_utc(value)

        if self.type is QueryFieldType.ENUM:
            raw = value.value if isinstance(value, StrEnum) else value
            if not isinstance(raw, str):
                self._invalid_value(value)
            normalized = _normalize_text(raw)
            if self.enum_values and normalized not in self.enum_values:
                self._invalid_value(value)
            return normalized

        if self.type is QueryFieldType.ID:
            raw = str(value) if isinstance(value, UUIDId | UUID) else value
            if not isinstance(raw, str):
                self._invalid_value(value)
            try:
                return str(UUID(raw))
            except ValueError as exc:
                raise ValidationError(
                    "query id value must be a UUID",
                    code="segment.query.invalid_value",
                    context={"field": self.key},
                ) from exc

        raise AssertionError(f"unsupported query field type: {self.type}")

    def validate_predicate(self, predicate: Predicate) -> None:
        if predicate.operator not in self.supported_operators:
            raise ValidationError(
                "operator is not supported for query field",
                code="segment.query.invalid_operator",
                context={
                    "field": self.key,
                    "operator": predicate.operator.value,
                    "field_type": self.type.value,
                },
            )
        if predicate.operator in {QueryOperator.IS_NULL, QueryOperator.IS_NOT_NULL}:
            return
        value = predicate.value
        if isinstance(value, RelativeTimeValue):
            if self.type not in {QueryFieldType.DATE, QueryFieldType.DATETIME}:
                raise ValidationError(
                    "relative time requires a date or datetime field",
                    code="segment.query.relative_time.invalid_field",
                    context={"field": self.key, "field_type": self.type.value},
                )
            if predicate.operator in {QueryOperator.IN, QueryOperator.NOT_IN}:
                raise ValidationError(
                    "relative time cannot be used inside in/not_in",
                    code="segment.query.relative_time.invalid_operator",
                    context={"field": self.key, "operator": predicate.operator.value},
                )
            return
        if predicate.operator in {QueryOperator.IN, QueryOperator.NOT_IN}:
            assert isinstance(value, tuple)
            for item in value:
                self.normalize_value(item)
            return
        assert value is not None
        self.normalize_value(value)

    def _invalid_value(self, value: object) -> NoReturn:
        raise ValidationError(
            "query value is incompatible with field type",
            code="segment.query.invalid_value",
            context={
                "field": self.key,
                "field_type": self.type.value,
                "value_type": type(value).__name__,
            },
        )


@dataclass(frozen=True, slots=True)
class QuerySchema(ValueObject):
    """Allow-listed query fields for one segmentable entity kind."""

    entity_kind: str
    fields: tuple[QueryField, ...]
    version: int = 1

    def __post_init__(self) -> None:
        kind = self.entity_kind.strip().casefold()
        if kind not in {"contact", "organization", "lead", "opportunity"}:
            raise ValidationError(
                "unsupported segment entity kind",
                code="segment.entity_kind.unsupported",
                context={"entity_kind": kind},
            )
        fields = tuple(self.fields)
        keys = [field.key for field in fields]
        if not fields or len(keys) != len(set(keys)) or self.version < 1:
            raise ValidationError(
                "query schema must contain unique fields and a positive version",
                code="segment.query.schema.invalid",
                context={"entity_kind": kind},
            )
        object.__setattr__(self, "entity_kind", kind)
        object.__setattr__(self, "fields", fields)

    def field(self, key: str) -> QueryField:
        normalized = normalize_query_field_key(key)
        for field in self.fields:
            if field.key == normalized:
                return field
        raise ValidationError(
            "query field is not available for entity kind",
            code="segment.query.invalid_field",
            context={"entity_kind": self.entity_kind, "field": normalized},
        )

    def validate(self, expression: QueryExpression) -> None:
        validate_expression_complexity(expression)
        for predicate in iter_predicates(expression):
            self.field(predicate.field).validate_predicate(predicate)


class QuerySchemaRegistry:
    """Registry of portable segment query schemas."""

    def __init__(self, schemas: tuple[QuerySchema, ...]) -> None:
        self._schemas = {schema.entity_kind: schema for schema in schemas}
        if len(self._schemas) != len(schemas):
            raise ValidationError(
                "query schema entity kinds must be unique",
                code="segment.query.schema.invalid",
            )

    def get(self, entity_kind: str) -> QuerySchema:
        key = entity_kind.strip().casefold()
        schema = self._schemas.get(key)
        if schema is None:
            raise NotFoundError(
                "query schema is not registered",
                code="segment.query.schema.not_found",
                context={"entity_kind": key},
            )
        return schema

    def supports(self, entity_kind: str) -> bool:
        return entity_kind.strip().casefold() in self._schemas

    def schemas(self) -> tuple[QuerySchema, ...]:
        return tuple(self._schemas[key] for key in sorted(self._schemas))


def iter_predicates(expression: QueryExpression) -> tuple[Predicate, ...]:
    """Return predicates in deterministic depth-first order."""

    if isinstance(expression, Predicate):
        return (expression,)
    if isinstance(expression, Not):
        return iter_predicates(expression.expression)
    if isinstance(expression, And | Or):
        return tuple(
            predicate
            for child in expression.expressions
            for predicate in iter_predicates(child)
        )
    raise ValidationError(
        "unsupported query-expression node",
        code="segment.query.invalid_expression",
    )


def query_field_from_custom_definition(
    definition: CustomFieldDefinition,
) -> QueryField | None:
    """Map supported scalar Custom Fields into portable query fields."""

    mapping = {
        CustomFieldType.STRING: QueryFieldType.STRING,
        CustomFieldType.TEXT: QueryFieldType.STRING,
        CustomFieldType.INTEGER: QueryFieldType.INTEGER,
        CustomFieldType.DECIMAL: QueryFieldType.DECIMAL,
        CustomFieldType.BOOLEAN: QueryFieldType.BOOLEAN,
        CustomFieldType.DATE: QueryFieldType.DATE,
        CustomFieldType.DATETIME: QueryFieldType.DATETIME,
        CustomFieldType.EMAIL: QueryFieldType.STRING,
        CustomFieldType.PHONE: QueryFieldType.STRING,
        CustomFieldType.URL: QueryFieldType.STRING,
        CustomFieldType.ENUM: QueryFieldType.ENUM,
    }
    field_type = mapping.get(definition.field_type)
    if field_type is None or not definition.active:
        return None
    enum_values = (
        tuple(option.code for option in definition.options)
        if definition.field_type is CustomFieldType.ENUM
        else ()
    )
    return QueryField(
        key=f"custom.{definition.key}",
        type=field_type,
        nullable=True,
        enum_values=enum_values,
    )


def _field(
    key: str,
    type: QueryFieldType,
    *,
    nullable: bool = False,
    enum_values: tuple[str, ...] = (),
) -> QueryField:
    return QueryField(key=key, type=type, nullable=nullable, enum_values=enum_values)


def default_query_schemas() -> QuerySchemaRegistry:
    """Build initial schemas for Contact, Organization, Lead and Opportunity."""

    common = (
        _field("id", QueryFieldType.ID),
        _field("created_at", QueryFieldType.DATETIME),
        _field("updated_at", QueryFieldType.DATETIME),
        _field("tag", QueryFieldType.STRING, nullable=True),
    )
    contact = QuerySchema(
        "contact",
        (
            *common,
            _field(
                "status",
                QueryFieldType.ENUM,
                enum_values=("active", "inactive", "archived"),
            ),
            _field("source", QueryFieldType.STRING, nullable=True),
            _field("owner_id", QueryFieldType.ID, nullable=True),
            _field("first_name", QueryFieldType.STRING, nullable=True),
            _field("last_name", QueryFieldType.STRING, nullable=True),
            _field("display_name", QueryFieldType.STRING, nullable=True),
        ),
    )
    organization = QuerySchema(
        "organization",
        (
            *common,
            _field(
                "status",
                QueryFieldType.ENUM,
                enum_values=("active", "inactive", "archived"),
            ),
            _field("source", QueryFieldType.STRING, nullable=True),
            _field("owner_id", QueryFieldType.ID, nullable=True),
            _field("legal_name", QueryFieldType.STRING),
            _field("trading_name", QueryFieldType.STRING, nullable=True),
            _field("display_name", QueryFieldType.STRING, nullable=True),
            _field("registration_number", QueryFieldType.STRING, nullable=True),
        ),
    )
    lead = QuerySchema(
        "lead",
        (
            *common,
            _field(
                "status",
                QueryFieldType.ENUM,
                enum_values=(
                    "new",
                    "open",
                    "contacted",
                    "qualified",
                    "disqualified",
                    "converted",
                ),
            ),
            _field("contact_id", QueryFieldType.ID),
            _field("organization_id", QueryFieldType.ID, nullable=True),
            _field("source", QueryFieldType.STRING, nullable=True),
        ),
    )
    opportunity = QuerySchema(
        "opportunity",
        (
            *common,
            _field("name", QueryFieldType.STRING),
            _field(
                "status",
                QueryFieldType.ENUM,
                enum_values=("open", "won", "lost", "cancelled"),
            ),
            _field("contact_id", QueryFieldType.ID),
            _field("organization_id", QueryFieldType.ID, nullable=True),
            _field("pipeline_id", QueryFieldType.STRING, nullable=True),
            _field("stage_id", QueryFieldType.STRING, nullable=True),
            _field("stage_entered_at", QueryFieldType.DATETIME, nullable=True),
            _field("estimated_value", QueryFieldType.DECIMAL, nullable=True),
            _field("currency", QueryFieldType.STRING, nullable=True),
            _field("probability", QueryFieldType.DECIMAL, nullable=True),
            _field("expected_close_date", QueryFieldType.DATE, nullable=True),
            _field("owner_id", QueryFieldType.STRING, nullable=True),
        ),
    )
    return QuerySchemaRegistry((contact, organization, lead, opportunity))


__all__ = [
    "QueryField",
    "QuerySchema",
    "QuerySchemaRegistry",
    "default_query_schemas",
    "iter_predicates",
    "query_field_from_custom_definition",
]
