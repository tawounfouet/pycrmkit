"""Provider-neutral primitives and contracts for CRM data imports."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, runtime_checkable

from pycrmkit.exceptions import ValidationError


@dataclass(frozen=True, slots=True)
class ImportRow:
    """One source row moving through the import pipeline."""

    number: int
    values: Mapping[str, object]

    def __post_init__(self) -> None:
        if self.number < 1:
            raise ValidationError(
                "import row numbers start at 1",
                code="import.row.number.invalid",
                context={"number": self.number},
            )
        object.__setattr__(self, "values", dict(self.values))

    def replace(self, values: Mapping[str, object]) -> ImportRow:
        """Return the same logical row with transformed values."""

        return ImportRow(number=self.number, values=values)


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """Structured row-level validation or transformation issue."""

    code: str
    message: str
    field: str | None = None


@dataclass(frozen=True, slots=True)
class DuplicateResult:
    """Result of the provisional duplicate-detection hook."""

    is_duplicate: bool
    existing_entity_id: str | None = None
    reason: str | None = None

    @classmethod
    def no_match(cls) -> DuplicateResult:
        return cls(is_duplicate=False)

    @classmethod
    def match(
        cls,
        *,
        existing_entity_id: str | None = None,
        reason: str | None = None,
    ) -> DuplicateResult:
        return cls(
            is_duplicate=True,
            existing_entity_id=existing_entity_id,
            reason=reason,
        )


class PersistAction(StrEnum):
    """Observable persistence outcome for one accepted row."""

    CREATED = "created"
    UPDATED = "updated"
    SKIPPED = "skipped"


@dataclass(frozen=True, slots=True)
class PersistResult:
    """Result returned by an import persistence adapter."""

    action: PersistAction
    entity_id: str | None = None


@runtime_checkable
class ImportReader(Protocol):
    """Read source records without imposing a physical file format."""

    def read(self) -> Iterable[Mapping[str, object]]:
        """Yield provider-owned records in source order."""


@runtime_checkable
class ImportMapper(Protocol):
    """Translate source field names into target CRM field names."""

    def map(self, row: ImportRow) -> ImportRow:
        """Map one row."""


@runtime_checkable
class ImportNormalizer(Protocol):
    """Normalize mapped values before validation."""

    def normalize(self, row: ImportRow) -> ImportRow:
        """Normalize one mapped row."""


@runtime_checkable
class ImportValidator(Protocol):
    """Return structured validation issues without mutating a row."""

    def validate(self, row: ImportRow) -> tuple[ValidationIssue, ...]:
        """Validate one normalized row."""


@runtime_checkable
class ImportDeduplicator(Protocol):
    """Provisional hook implemented by the dedicated 0.9.0b2 dedup engine later."""

    def detect(self, row: ImportRow) -> DuplicateResult:
        """Return whether the row is already represented."""


@runtime_checkable
class ImportPersister(Protocol):
    """Persist one accepted normalized row using application-owned semantics."""

    def persist(self, row: ImportRow) -> PersistResult:
        """Persist one row and report the observable outcome."""


@dataclass(slots=True)
class IterableReader:
    """Format-neutral reader for an existing iterable of mappings."""

    records: Iterable[Mapping[str, object]]

    def read(self) -> Iterable[Mapping[str, object]]:
        return self.records


class IdentityMapper:
    """Default mapper that preserves all fields."""

    def map(self, row: ImportRow) -> ImportRow:
        return row


class IdentityNormalizer:
    """Default normalizer that preserves all mapped values."""

    def normalize(self, row: ImportRow) -> ImportRow:
        return row


class AcceptAllValidator:
    """Default validator for pipelines without row constraints."""

    def validate(self, row: ImportRow) -> tuple[ValidationIssue, ...]:
        del row
        return ()


class NoDuplicateDetector:
    """Default duplicate hook until a dedicated detector is supplied."""

    def detect(self, row: ImportRow) -> DuplicateResult:
        del row
        return DuplicateResult.no_match()


__all__ = [
    "AcceptAllValidator",
    "DuplicateResult",
    "IdentityMapper",
    "IdentityNormalizer",
    "ImportDeduplicator",
    "ImportMapper",
    "ImportNormalizer",
    "ImportPersister",
    "ImportReader",
    "ImportRow",
    "ImportValidator",
    "IterableReader",
    "NoDuplicateDetector",
    "PersistAction",
    "PersistResult",
    "ValidationIssue",
]
