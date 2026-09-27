# Import Framework

PyCRMKit `0.9.0a2` introduces the provider-neutral import pipeline used by later
CSV, JSON, JSONL, deduplication and merge milestones.

The framework deliberately separates **data-operation semantics** from physical
file formats:

```text
Source records
    ↓
Read
    ↓
Map
    ↓
Normalize
    ↓
Validate
    ↓
Deduplicate hook
    ↓
Persist
    ↓
Structured report
```

## Scope

`0.9.0a2` provides:

- `ImportReader`, `ImportMapper`, `ImportNormalizer`, `ImportValidator`,
  `ImportDeduplicator` and `ImportPersister` protocols;
- immutable `ImportRow` row envelopes;
- explicit field mapping through `FieldMapping` / `RecordMapper`;
- composable field normalization;
- structured validation issues;
- a provisional deduplication hook;
- explicit create/update/skip persistence outcomes;
- `ImportPipeline`;
- structured counters and per-row evidence through `ImportReport`.

It does **not** implement CSV, JSON or JSONL readers/exporters. Those belong to
`0.9.0b1`. The real CRM deduplication engine belongs to `0.9.0b2`, and merge
execution belongs to `0.9.0b3`.

## Minimal example

```python
from pycrmkit.importers import (
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


class ContactPersister:
    def persist(self, row: ImportRow) -> PersistResult:
        # Application-owned persistence logic.
        return PersistResult(
            PersistAction.CREATED,
            entity_id=f"contact-{row.number}",
        )


pipeline = ImportPipeline(
    reader=IterableReader(
        (
            {"Email": " Ada@Example.COM ", "Name": "Ada Lovelace"},
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
    persister=ContactPersister(),
)

report = pipeline.run()
assert report.rows_created == 1
```

## Report contract

Every run exposes these integration-facing counters:

```text
rows_read
rows_created
rows_updated
rows_skipped
duplicates
validation_errors
```

`validation_errors` counts structured validation/transformation issues, while
`rows_skipped` counts rows that did not produce a create/update result.

By default, the report also retains row-level results so applications can inspect the
source row number, duplicate disposition, validation stage, machine-readable
error code and persisted entity identifier.

For high-volume imports, PyCRMKit `1.0.0b2` adds summary mode:

```python
pipeline = ImportPipeline(
    reader=reader,
    persister=persister,
    retain_row_results=False,
)
```

All six counters remain exact, while `report.row_results` stays empty. This
avoids report memory growing linearly with the number of accepted/skipped rows.
The default remains `True` for backward compatibility.

## Failure semantics

Expected row-data failures during mapping, normalization and validation are
recorded and the pipeline continues with the next row.

Unexpected failures in duplicate detection or persistence are **not swallowed**.
Those layers can involve transactions, repositories and external state; hiding
their failure would make an import report misleading.

## Architecture boundary

The import framework has no dependency on CSV parsers, pandas, Django,
SQLAlchemy, FastAPI or a specific CRM entity. Format readers and domain-specific
persisters adapt to these contracts rather than redefining the pipeline.
