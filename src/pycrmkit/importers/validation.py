"""Structured row validation for imports."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from pycrmkit.exceptions import ValidationError
from pycrmkit.importers.base import ImportRow, ImportValidator, ValidationIssue

Predicate = Callable[[object], bool]


@dataclass(frozen=True, slots=True)
class RequiredFieldsValidator:
    """Require fields to be present and non-blank."""

    fields: tuple[str, ...]

    def __post_init__(self) -> None:
        cleaned = tuple(field.strip() for field in self.fields)
        if any(not field for field in cleaned):
            raise ValidationError(
                "required import field names cannot be empty",
                code="import.validation.field.empty",
            )
        object.__setattr__(self, "fields", cleaned)

    def validate(self, row: ImportRow) -> tuple[ValidationIssue, ...]:
        issues: list[ValidationIssue] = []
        for field in self.fields:
            value = row.values.get(field)
            if value is None or (isinstance(value, str) and not value.strip()):
                issues.append(
                    ValidationIssue(
                        code="import.required.missing",
                        message=f"required field {field!r} is missing",
                        field=field,
                    )
                )
        return tuple(issues)


@dataclass(frozen=True, slots=True)
class PredicateValidator:
    """Validate one field with an application-supplied predicate."""

    field: str
    predicate: Predicate
    code: str
    message: str
    allow_missing: bool = True

    def __post_init__(self) -> None:
        normalized = self.field.strip()
        if not normalized:
            raise ValidationError(
                "predicate validation field cannot be empty",
                code="import.validation.field.empty",
            )
        object.__setattr__(self, "field", normalized)

    def validate(self, row: ImportRow) -> tuple[ValidationIssue, ...]:
        if self.field not in row.values:
            return () if self.allow_missing else (
                ValidationIssue(
                    code=self.code,
                    message=self.message,
                    field=self.field,
                ),
            )

        value = row.values[self.field]
        if self.predicate(value):
            return ()
        return (
            ValidationIssue(
                code=self.code,
                message=self.message,
                field=self.field,
            ),
        )


@dataclass(frozen=True, slots=True)
class CompositeValidator:
    """Run validators in declaration order and concatenate their issues."""

    validators: tuple[ImportValidator, ...]

    def validate(self, row: ImportRow) -> tuple[ValidationIssue, ...]:
        issues: list[ValidationIssue] = []
        for validator in self.validators:
            issues.extend(validator.validate(row))
        return tuple(issues)


__all__ = [
    "CompositeValidator",
    "Predicate",
    "PredicateValidator",
    "RequiredFieldsValidator",
    "ValidationIssue",
]
