"""Orchestration of the provider-neutral import stages."""

from __future__ import annotations

from dataclasses import dataclass, field

from pycrmkit.exceptions import ValidationError
from pycrmkit.importers.base import (
    AcceptAllValidator,
    IdentityMapper,
    IdentityNormalizer,
    ImportDeduplicator,
    ImportMapper,
    ImportNormalizer,
    ImportPersister,
    ImportReader,
    ImportRow,
    ImportValidator,
    NoDuplicateDetector,
    ValidationIssue,
)
from pycrmkit.importers.reports import ImportReport, ImportStage


def _issue_from_error(error: ValidationError) -> ValidationIssue:
    field = error.context.get("field")
    return ValidationIssue(
        code=error.code,
        message=error.message,
        field=field if isinstance(field, str) else None,
    )


@dataclass(slots=True)
class ImportPipeline:
    """Execute Read → Map → Normalize → Validate → Deduplicate → Persist → Report."""

    reader: ImportReader
    persister: ImportPersister
    mapper: ImportMapper = field(default_factory=IdentityMapper)
    normalizer: ImportNormalizer = field(default_factory=IdentityNormalizer)
    validator: ImportValidator = field(default_factory=AcceptAllValidator)
    deduplicator: ImportDeduplicator = field(default_factory=NoDuplicateDetector)
    retain_row_results: bool = True

    def run(self) -> ImportReport:
        report = ImportReport(retain_row_results=self.retain_row_results)

        for row_number, raw_values in enumerate(self.reader.read(), start=1):
            report.rows_read += 1
            row = ImportRow(row_number, raw_values)

            try:
                row = self.mapper.map(row)
            except ValidationError as error:
                report.record_validation_failure(
                    row_number=row.number,
                    stage=ImportStage.MAP,
                    issues=(_issue_from_error(error),),
                )
                continue

            try:
                row = self.normalizer.normalize(row)
            except ValidationError as error:
                report.record_validation_failure(
                    row_number=row.number,
                    stage=ImportStage.NORMALIZE,
                    issues=(_issue_from_error(error),),
                )
                continue

            issues = self.validator.validate(row)
            if issues:
                report.record_validation_failure(
                    row_number=row.number,
                    stage=ImportStage.VALIDATE,
                    issues=issues,
                )
                continue

            duplicate = self.deduplicator.detect(row)
            if duplicate.is_duplicate:
                report.record_duplicate(
                    row_number=row.number,
                    existing_entity_id=duplicate.existing_entity_id,
                )
                continue

            persisted = self.persister.persist(row)
            report.record_persisted(row_number=row.number, result=persisted)

        return report


__all__ = ["ImportPipeline"]
