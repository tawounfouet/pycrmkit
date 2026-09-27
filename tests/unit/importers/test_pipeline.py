"""End-to-end behavior of the format-neutral import pipeline."""

from __future__ import annotations

from pycrmkit.importers import (
    DuplicateResult,
    FieldMapping,
    ImportPipeline,
    ImportRow,
    IterableReader,
    NormalizationRule,
    PersistAction,
    PersistResult,
    RecordMapper,
    RecordNormalizer,
    RequiredFieldsValidator,
    casefold_text,
    compose_normalizers,
    strip_text,
)


class EmailDuplicateDetector:
    def detect(self, row: ImportRow) -> DuplicateResult:
        if row.values.get("email") == "duplicate@example.com":
            return DuplicateResult.match(
                existing_entity_id="contact-existing",
                reason="normalized email",
            )
        return DuplicateResult.no_match()


class RecordingPersister:
    def __init__(self) -> None:
        self.rows: list[ImportRow] = []

    def persist(self, row: ImportRow) -> PersistResult:
        self.rows.append(row)
        if row.values.get("email") == "update@example.com":
            return PersistResult(PersistAction.UPDATED, "contact-update")
        return PersistResult(PersistAction.CREATED, f"contact-{row.number}")


def test_pipeline_runs_all_stages_and_produces_required_report_counters() -> None:
    persister = RecordingPersister()
    pipeline = ImportPipeline(
        reader=IterableReader(
            (
                {"Email": " New@Example.COM ", "Name": "New"},
                {"Email": " update@example.com ", "Name": "Update"},
                {"Email": " DUPLICATE@example.com ", "Name": "Duplicate"},
                {"Email": "   ", "Name": "Invalid"},
            )
        ),
        mapper=RecordMapper(
            (
                FieldMapping("Email", "email"),
                FieldMapping("Name", "display_name"),
            )
        ),
        normalizer=RecordNormalizer(
            (
                NormalizationRule(
                    "email",
                    compose_normalizers(strip_text, casefold_text),
                ),
            )
        ),
        validator=RequiredFieldsValidator(("email", "display_name")),
        deduplicator=EmailDuplicateDetector(),
        persister=persister,
    )

    report = pipeline.run()

    assert report.as_dict() == {
        "rows_read": 4,
        "rows_created": 1,
        "rows_updated": 1,
        "rows_skipped": 2,
        "duplicates": 1,
        "validation_errors": 1,
    }
    assert [row.values["email"] for row in persister.rows] == [
        "new@example.com",
        "update@example.com",
    ]
    assert report.row_results[2].duplicate is True
    assert report.row_results[2].duplicate_entity_id == "contact-existing"
    assert report.row_results[3].errors[0].code == "import.required.missing"


def test_normalization_error_is_reported_without_persisting_the_row() -> None:
    persister = RecordingPersister()
    pipeline = ImportPipeline(
        reader=IterableReader(({"email": 42},)),
        normalizer=RecordNormalizer((NormalizationRule("email", strip_text),)),
        persister=persister,
    )

    report = pipeline.run()

    assert report.rows_read == 1
    assert report.rows_skipped == 1
    assert report.validation_errors == 1
    assert report.errors[0].code == "import.normalization.failed"
    assert persister.rows == []


def test_summary_mode_keeps_exact_counters_without_row_result_retention() -> None:
    row_count = 1_000
    persister = RecordingPersister()
    records = (
        {"email": f"user-{index}@example.com", "display_name": f"User {index}"}
        for index in range(row_count)
    )
    pipeline = ImportPipeline(
        reader=IterableReader(records),
        persister=persister,
        retain_row_results=False,
    )

    report = pipeline.run()

    assert report.as_dict() == {
        "rows_read": row_count,
        "rows_created": row_count,
        "rows_updated": 0,
        "rows_skipped": 0,
        "duplicates": 0,
        "validation_errors": 0,
    }
    assert report.row_results == []
    assert report.errors == ()
    assert len(persister.rows) == row_count
