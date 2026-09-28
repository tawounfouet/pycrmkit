from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from pycrmkit.exceptions import ValidationError
from pycrmkit.segments import (
    And,
    Not,
    Or,
    Predicate,
    QueryOperator,
    default_query_schemas,
    expression_from_dict,
    expression_to_dict,
)


def test_expression_serialization_round_trip_preserves_typed_literals() -> None:
    expression = And(
        (
            Predicate("status", QueryOperator.EQ, "open"),
            Or(
                (
                    Predicate(
                        "estimated_value",
                        QueryOperator.GTE,
                        Decimal("50000"),
                    ),
                    Predicate(
                        "created_at",
                        QueryOperator.GTE,
                        datetime(2026, 9, 1, tzinfo=UTC),
                    ),
                )
            ),
        )
    )

    assert expression_from_dict(expression_to_dict(expression)) == expression


def test_query_schema_rejects_unknown_field() -> None:
    schema = default_query_schemas().get("contact")

    with pytest.raises(ValidationError) as exc_info:
        schema.validate(
            Predicate("database_password", QueryOperator.EQ, "secret")
        )

    assert exc_info.value.code == "segment.query.invalid_field"


def test_query_schema_rejects_invalid_operator_for_type() -> None:
    schema = default_query_schemas().get("opportunity")

    with pytest.raises(ValidationError) as exc_info:
        schema.validate(
            Predicate(
                "estimated_value",
                QueryOperator.CONTAINS,
                Decimal("10"),
            )
        )

    assert exc_info.value.code == "segment.query.invalid_operator"


def test_null_comparison_requires_explicit_operator() -> None:
    with pytest.raises(ValidationError) as exc_info:
        Predicate("source", QueryOperator.EQ, None)

    assert exc_info.value.code == "segment.query.invalid_value"
    assert Predicate("source", QueryOperator.IS_NULL).value is None


def test_boolean_nodes_are_explicit_and_serializable() -> None:
    expression = Not(
        Or(
            (
                Predicate("status", QueryOperator.EQ, "archived"),
                Predicate("source", QueryOperator.EQ, "blocked"),
            )
        )
    )

    assert expression_from_dict(expression_to_dict(expression)) == expression
