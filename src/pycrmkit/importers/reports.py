"""Structured import execution reports."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from pycrmkit.importers.base import PersistAction, PersistResult, ValidationIssue


class ImportStage(StrEnum):
    """Pipeline stage associated with a row-level issue."""

    MAP = "map"
    NORMALIZE = "normalize"
    VALIDATE = "validate"


class ImportRowStatus(StrEnum):
    """Final row outcome exposed by the import report."""

    CREATED = "created"
    UPDATED = "updated"
    SKIPPED = "skipped"


@dataclass(frozen=True, slots=True)
class ImportRowError:
    """One structured issue tied to a source row and pipeline stage."""

    row_number: int
    stage: ImportStage
    code: str
    message: str
    field: str | None = None


@dataclass(frozen=True, slots=True)
class ImportRowResult:
    """Final observable result for one input row."""

    row_number: int
    status: ImportRowStatus
    entity_id: str | None = None
    duplicate: bool = False
    duplicate_entity_id: str | None = None
    errors: tuple[ImportRowError, ...] = ()


@dataclass(slots=True)
class ImportReport:
    """Counters and row-level evidence produced by one import run."""

    rows_read: int = 0
    rows_created: int = 0
    rows_updated: int = 0
    rows_skipped: int = 0
    duplicates: int = 0
    validation_errors: int = 0
    row_results: list[ImportRowResult] = field(default_factory=list)

    @property
    def errors(self) -> tuple[ImportRowError, ...]:
        """Flatten row errors while retaining source ordering."""

        return tuple(
            error
            for result in self.row_results
            for error in result.errors
        )

    def record_validation_failure(
        self,
        *,
        row_number: int,
        stage: ImportStage,
        issues: tuple[ValidationIssue, ...],
    ) -> None:
        errors = tuple(
            ImportRowError(
                row_number=row_number,
                stage=stage,
                code=issue.code,
                message=issue.message,
                field=issue.field,
            )
            for issue in issues
        )
        self.validation_errors += len(errors)
        self.rows_skipped += 1
        self.row_results.append(
            ImportRowResult(
                row_number=row_number,
                status=ImportRowStatus.SKIPPED,
                errors=errors,
            )
        )

    def record_duplicate(
        self,
        *,
        row_number: int,
        existing_entity_id: str | None,
    ) -> None:
        self.duplicates += 1
        self.rows_skipped += 1
        self.row_results.append(
            ImportRowResult(
                row_number=row_number,
                status=ImportRowStatus.SKIPPED,
                duplicate=True,
                duplicate_entity_id=existing_entity_id,
            )
        )

    def record_persisted(self, *, row_number: int, result: PersistResult) -> None:
        if result.action is PersistAction.CREATED:
            self.rows_created += 1
            status = ImportRowStatus.CREATED
        elif result.action is PersistAction.UPDATED:
            self.rows_updated += 1
            status = ImportRowStatus.UPDATED
        else:
            self.rows_skipped += 1
            status = ImportRowStatus.SKIPPED

        self.row_results.append(
            ImportRowResult(
                row_number=row_number,
                status=status,
                entity_id=result.entity_id,
            )
        )

    def as_dict(self) -> dict[str, object]:
        """Return the stable report counters for machine-readable integrations."""

        return {
            "rows_read": self.rows_read,
            "rows_created": self.rows_created,
            "rows_updated": self.rows_updated,
            "rows_skipped": self.rows_skipped,
            "duplicates": self.duplicates,
            "validation_errors": self.validation_errors,
        }


__all__ = [
    "ImportReport",
    "ImportRowError",
    "ImportRowResult",
    "ImportRowStatus",
    "ImportStage",
]
