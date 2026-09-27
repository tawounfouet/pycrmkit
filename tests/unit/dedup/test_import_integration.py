"""Deduplication engine integration with ImportPipeline."""

from __future__ import annotations

from pycrmkit.dedup import (
    CandidateRecord,
    DeduplicationEngine,
    InMemoryCandidateSource,
)
from pycrmkit.importers import (
    ImportPipeline,
    ImportRow,
    IterableReader,
    PersistAction,
    PersistResult,
)


class RecordingPersister:
    def __init__(self) -> None:
        self.rows: list[ImportRow] = []

    def persist(self, row: ImportRow) -> PersistResult:
        self.rows.append(row)
        return PersistResult(PersistAction.CREATED, f"contact-{row.number}")


def test_import_pipeline_skips_unique_high_confidence_duplicate() -> None:
    deduplicator = DeduplicationEngine(
        InMemoryCandidateSource(
            (
                CandidateRecord(
                    "contact-existing",
                    {
                        "email": "ada@example.com",
                        "full_name": "Ada Lovelace",
                        "organization": "Analytical Engines",
                    },
                ),
            )
        )
    )
    persister = RecordingPersister()
    pipeline = ImportPipeline(
        reader=IterableReader(
            (
                {
                    "email": "ADA@EXAMPLE.COM",
                    "full_name": "Ada Lovelace",
                    "organization": "Analytical Engines",
                },
                {
                    "email": "grace@example.com",
                    "full_name": "Grace Hopper",
                    "organization": "US Navy",
                },
            )
        ),
        deduplicator=deduplicator,
        persister=persister,
    )

    report = pipeline.run()

    assert report.as_dict() == {
        "rows_read": 2,
        "rows_created": 1,
        "rows_updated": 0,
        "rows_skipped": 1,
        "duplicates": 1,
        "validation_errors": 0,
    }
    assert len(persister.rows) == 1
    assert persister.rows[0].values["email"] == "grace@example.com"
    assert report.row_results[0].duplicate_entity_id == "contact-existing"
