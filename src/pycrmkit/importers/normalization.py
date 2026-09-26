"""Composable value normalization for import rows."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from pycrmkit.exceptions import PyCRMKitError, ValidationError
from pycrmkit.importers.base import ImportRow

Normalizer = Callable[[object], object]


@dataclass(frozen=True, slots=True)
class NormalizationRule:
    """Apply one normalizer to one field when the field is present."""

    field: str
    normalizer: Normalizer
    skip_none: bool = True

    def __post_init__(self) -> None:
        normalized = self.field.strip()
        if not normalized:
            raise ValidationError(
                "normalization field cannot be empty",
                code="import.normalization.field.empty",
            )
        object.__setattr__(self, "field", normalized)


@dataclass(frozen=True, slots=True)
class RecordNormalizer:
    """Apply ordered field normalization rules."""

    rules: tuple[NormalizationRule, ...]

    def normalize(self, row: ImportRow) -> ImportRow:
        values = dict(row.values)
        for rule in self.rules:
            if rule.field not in values:
                continue
            current = values[rule.field]
            if current is None and rule.skip_none:
                continue
            try:
                values[rule.field] = rule.normalizer(current)
            except PyCRMKitError:
                raise
            except (TypeError, ValueError) as exc:
                raise ValidationError(
                    "import value normalization failed",
                    code="import.normalization.failed",
                    context={"row": row.number, "field": rule.field},
                ) from exc
        return row.replace(values)


def strip_text(value: object) -> str:
    """Trim surrounding whitespace from a string."""

    if not isinstance(value, str):
        raise TypeError("expected string")
    return value.strip()


def casefold_text(value: object) -> str:
    """Unicode-aware case normalization for case-insensitive values."""

    if not isinstance(value, str):
        raise TypeError("expected string")
    return value.casefold()


def empty_text_to_none(value: object) -> object:
    """Convert blank strings to None while preserving non-string values."""

    if isinstance(value, str) and not value.strip():
        return None
    return value


def compose_normalizers(*normalizers: Normalizer) -> Normalizer:
    """Compose normalizers left-to-right into one callable."""

    def composed(value: object) -> object:
        current = value
        for normalizer in normalizers:
            current = normalizer(current)
        return current

    return composed


__all__ = [
    "NormalizationRule",
    "Normalizer",
    "RecordNormalizer",
    "casefold_text",
    "compose_normalizers",
    "empty_text_to_none",
    "strip_text",
]
