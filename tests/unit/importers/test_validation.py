"""Import validation behavior."""

from __future__ import annotations

from pycrmkit.importers import (
    CompositeValidator,
    ImportRow,
    PredicateValidator,
    RequiredFieldsValidator,
)


def _looks_like_email(value: object) -> bool:
    return isinstance(value, str) and "@" in value


def test_required_and_predicate_validators_return_structured_issues() -> None:
    validator = CompositeValidator(
        (
            RequiredFieldsValidator(("email", "display_name")),
            PredicateValidator(
                field="email",
                predicate=_looks_like_email,
                code="import.email.invalid",
                message="email must contain @",
            ),
        )
    )

    issues = validator.validate(
        ImportRow(1, {"email": "not-an-email", "display_name": " "})
    )

    assert [(issue.code, issue.field) for issue in issues] == [
        ("import.required.missing", "display_name"),
        ("import.email.invalid", "email"),
    ]


def test_predicate_validator_can_ignore_missing_optional_fields() -> None:
    validator = PredicateValidator(
        field="phone",
        predicate=lambda value: isinstance(value, str),
        code="import.phone.invalid",
        message="phone must be text",
    )

    assert validator.validate(ImportRow(1, {"email": "ada@example.com"})) == ()
