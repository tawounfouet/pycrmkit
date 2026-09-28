"""Portable and serializable query-expression AST."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID

from pycrmkit.core.ids import UUIDId
from pycrmkit.core.time import as_utc
from pycrmkit.exceptions import ValidationError
from pycrmkit.segments.enums import QueryOperator

_FIELD_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}(?:\.[a-z][a-z0-9_]{0,63})*$")
MAX_EXPRESSION_DEPTH = 12
MAX_PREDICATES = 100
MAX_IN_VALUES = 100
QUERY_EXPRESSION_SCHEMA_VERSION = 1


def normalize_query_field_key(value: str) -> str:
    """Normalize and validate one dotted query-field identifier."""

    normalized = unicodedata.normalize("NFKC", value).strip().casefold()
    if not _FIELD_PATTERN.fullmatch(normalized):
        raise ValidationError(
            "query field must be a stable dotted lowercase identifier",
            code="segment.query.invalid_field",
            context={"field": value},
        )
    return normalized


def _canonical_literal(value: object) -> object:
    if isinstance(value, UUIDId | UUID):
        return str(value)
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, datetime):
        return as_utc(value)
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValidationError(
                "query decimal values must be finite",
                code="segment.query.invalid_value",
            )
        return value
    if isinstance(value, tuple | list):
        return tuple(_canonical_literal(item) for item in value)
    if isinstance(value, float):
        raise ValidationError(
            "query expressions do not accept binary floating-point literals",
            code="segment.query.invalid_value",
        )
    if value is None or isinstance(value, str | int | bool | date):
        return value
    raise ValidationError(
        "query literal type is not portable",
        code="segment.query.invalid_value",
        context={"value_type": type(value).__name__},
    )


class QueryExpression:
    """Marker base for immutable query AST nodes."""

    __slots__ = ()


@dataclass(frozen=True, slots=True)
class Predicate(QueryExpression):
    """One field/operator/value condition."""

    field: str
    operator: QueryOperator
    value: object | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "field", normalize_query_field_key(self.field))
        try:
            operator = QueryOperator(self.operator)
        except ValueError as exc:
            raise ValidationError(
                "unsupported query operator",
                code="segment.query.invalid_operator",
                context={"operator": str(self.operator)},
            ) from exc
        object.__setattr__(self, "operator", operator)

        if operator in {QueryOperator.IS_NULL, QueryOperator.IS_NOT_NULL}:
            if self.value is not None:
                raise ValidationError(
                    "null-check operators do not accept a value",
                    code="segment.query.invalid_value",
                    context={"field": self.field, "operator": operator.value},
                )
            return
        if self.value is None:
            raise ValidationError(
                "null comparison requires is_null or is_not_null",
                code="segment.query.invalid_value",
                context={"field": self.field, "operator": operator.value},
            )

        canonical = _canonical_literal(self.value)
        if operator in {QueryOperator.IN, QueryOperator.NOT_IN}:
            if not isinstance(canonical, tuple) or not canonical:
                raise ValidationError(
                    "in/not_in requires a non-empty sequence",
                    code="segment.query.invalid_value",
                )
            if len(canonical) > MAX_IN_VALUES:
                raise ValidationError(
                    "in/not_in exceeds its value limit",
                    code="segment.query.too_complex",
                    context={"max_values": MAX_IN_VALUES},
                )
        elif isinstance(canonical, tuple):
            raise ValidationError(
                "only in/not_in accept sequence values",
                code="segment.query.invalid_value",
            )
        object.__setattr__(self, "value", canonical)


@dataclass(frozen=True, slots=True)
class And(QueryExpression):
    """Logical conjunction."""

    expressions: tuple[QueryExpression, ...]

    def __post_init__(self) -> None:
        values = tuple(self.expressions)
        if len(values) < 2:
            raise ValidationError(
                "and requires at least two child expressions",
                code="segment.query.invalid_expression",
            )
        object.__setattr__(self, "expressions", values)
        validate_expression_complexity(self)


@dataclass(frozen=True, slots=True)
class Or(QueryExpression):
    """Logical disjunction."""

    expressions: tuple[QueryExpression, ...]

    def __post_init__(self) -> None:
        values = tuple(self.expressions)
        if len(values) < 2:
            raise ValidationError(
                "or requires at least two child expressions",
                code="segment.query.invalid_expression",
            )
        object.__setattr__(self, "expressions", values)
        validate_expression_complexity(self)


@dataclass(frozen=True, slots=True)
class Not(QueryExpression):
    """Logical negation."""

    expression: QueryExpression

    def __post_init__(self) -> None:
        if not isinstance(self.expression, QueryExpression):
            raise ValidationError(
                "not requires a query expression",
                code="segment.query.invalid_expression",
            )
        validate_expression_complexity(self)


def _measure(expression: QueryExpression, depth: int = 1) -> tuple[int, int]:
    if isinstance(expression, Predicate):
        return depth, 1
    if isinstance(expression, Not):
        return _measure(expression.expression, depth + 1)
    if isinstance(expression, And | Or):
        metrics = [_measure(item, depth + 1) for item in expression.expressions]
        return max(item[0] for item in metrics), sum(item[1] for item in metrics)
    raise ValidationError(
        "unsupported query-expression node",
        code="segment.query.invalid_expression",
    )


def validate_expression_complexity(expression: QueryExpression) -> None:
    """Enforce bounded depth and predicate count."""

    depth, predicates = _measure(expression)
    if depth > MAX_EXPRESSION_DEPTH or predicates > MAX_PREDICATES:
        raise ValidationError(
            "query expression exceeds complexity limits",
            code="segment.query.too_complex",
            context={
                "depth": depth,
                "predicates": predicates,
                "max_depth": MAX_EXPRESSION_DEPTH,
                "max_predicates": MAX_PREDICATES,
            },
        )


def _encode_literal(value: object) -> dict[str, object]:
    if isinstance(value, Decimal):
        return {"type": "decimal", "value": str(value)}
    if isinstance(value, datetime):
        return {"type": "datetime", "value": as_utc(value).isoformat()}
    if isinstance(value, date):
        return {"type": "date", "value": value.isoformat()}
    if isinstance(value, tuple):
        return {"type": "sequence", "value": [_encode_literal(item) for item in value]}
    return {"type": "scalar", "value": value}


def _decode_literal(payload: object) -> object:
    if not isinstance(payload, dict):
        raise ValidationError(
            "invalid serialized query literal",
            code="segment.query.serialization.invalid",
        )
    kind = payload.get("type")
    value = payload.get("value")
    if kind == "decimal":
        return Decimal(str(value))
    if kind == "datetime":
        return as_utc(datetime.fromisoformat(str(value)))
    if kind == "date":
        return date.fromisoformat(str(value))
    if kind == "sequence":
        if not isinstance(value, list):
            raise ValidationError(
                "invalid serialized query sequence",
                code="segment.query.serialization.invalid",
            )
        return tuple(_decode_literal(item) for item in value)
    if kind == "scalar":
        return value
    raise ValidationError(
        "unknown serialized query literal type",
        code="segment.query.serialization.invalid",
    )


def expression_to_dict(expression: QueryExpression) -> dict[str, Any]:
    """Serialize an expression to a versioned provider-neutral mapping."""

    if isinstance(expression, Predicate):
        return {
            "schema_version": QUERY_EXPRESSION_SCHEMA_VERSION,
            "node": "predicate",
            "field": expression.field,
            "operator": expression.operator.value,
            "value": (
                None if expression.value is None else _encode_literal(expression.value)
            ),
        }
    if isinstance(expression, And | Or):
        return {
            "schema_version": QUERY_EXPRESSION_SCHEMA_VERSION,
            "node": "and" if isinstance(expression, And) else "or",
            "expressions": [expression_to_dict(item) for item in expression.expressions],
        }
    if isinstance(expression, Not):
        return {
            "schema_version": QUERY_EXPRESSION_SCHEMA_VERSION,
            "node": "not",
            "expression": expression_to_dict(expression.expression),
        }
    raise ValidationError(
        "unsupported query-expression node",
        code="segment.query.serialization.invalid",
    )


def expression_from_dict(payload: dict[str, Any]) -> QueryExpression:
    """Deserialize one validated expression mapping."""

    if payload.get("schema_version") != QUERY_EXPRESSION_SCHEMA_VERSION:
        raise ValidationError(
            "unsupported query-expression schema version",
            code="segment.query.serialization.version_unsupported",
        )
    node = payload.get("node")
    if node == "predicate":
        raw_value = payload.get("value")
        value = None if raw_value is None else _decode_literal(raw_value)
        return Predicate(
            str(payload.get("field", "")),
            QueryOperator(str(payload.get("operator", ""))),
            value,
        )
    if node in {"and", "or"}:
        children = payload.get("expressions")
        if not isinstance(children, list):
            raise ValidationError(
                "serialized boolean expression requires children",
                code="segment.query.serialization.invalid",
            )
        values = tuple(expression_from_dict(item) for item in children)
        return And(values) if node == "and" else Or(values)
    if node == "not":
        child = payload.get("expression")
        if not isinstance(child, dict):
            raise ValidationError(
                "serialized not expression requires a child",
                code="segment.query.serialization.invalid",
            )
        return Not(expression_from_dict(child))
    raise ValidationError(
        "unknown serialized query-expression node",
        code="segment.query.serialization.invalid",
        context={"node": node},
    )


__all__ = [
    "MAX_EXPRESSION_DEPTH",
    "MAX_IN_VALUES",
    "MAX_PREDICATES",
    "QUERY_EXPRESSION_SCHEMA_VERSION",
    "And",
    "Not",
    "Or",
    "Predicate",
    "QueryExpression",
    "expression_from_dict",
    "expression_to_dict",
    "normalize_query_field_key",
    "validate_expression_complexity",
]
