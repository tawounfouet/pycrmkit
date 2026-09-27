# CSV / JSON / JSONL

PyCRMKit `0.9.0b1` provides standard-library format adapters around the
provider-neutral import framework introduced in `0.9.0a2`.

## Available adapters

```text
Import
  CSVReader
  JSONReader
  JSONLReader

Export
  CSVExporter
  JSONExporter
  JSONLExporter
```

All adapters accept filesystem paths. Readers and exporters also accept open
text streams, making them usable with `StringIO`, HTTP/download layers, object
storage wrappers and application-owned file abstractions.

## CSV

`CSVReader` uses the standard library `csv.DictReader`. Paths default to
`utf-8-sig`, which accepts both normal UTF-8 files and UTF-8 files carrying a
BOM. The first row is the header.

```python
from pycrmkit.importers import CSVReader

reader = CSVReader("contacts.csv")
for record in reader.read():
    print(record)
```

`CSVExporter` writes a deterministic header followed by scalar rows:

```python
from pycrmkit.exporters import CSVExporter

CSVExporter("contacts.csv").write(
    (
        {"email": "ada@example.com", "name": "Ada"},
        {"email": "zoe@example.com", "name": "Zoé"},
    )
)
```

CSV cells are intentionally scalar. Strings, numbers, booleans, Decimal,
date/datetime, UUID and `None` are supported. Nested dict/list/set structures
must be flattened or mapped before CSV export.

CSV import returns textual cell values (or `None` for missing columns). Type
normalization belongs to the Import Framework normalization stage.

Structural problems such as duplicate headers or rows containing more columns
than the header raise typed `ValidationError` instances rather than silently
dropping data.

## JSON

`JSONReader` expects a top-level JSON array whose entries are objects:

```json
[
  {"email": "ada@example.com", "custom_fields": {"tier": 1}},
  {"email": "zoe@example.com", "tags": ["vip"]}
]
```

JSON preserves nested objects, arrays, booleans, numbers and null values.
`JSONExporter` writes the array incrementally so records do not need to be
materialized into one Python list before export.

Malformed JSON, a non-array root, or non-object array entries raise a typed
`ValidationError`.

## JSON Lines

`JSONLReader` processes one non-blank line at a time:

```text
{"email":"ada@example.com","name":"Ada"}
{"email":"zoe@example.com","name":"Zoé"}
```

`JSONLExporter` is the preferred adapter for very large record streams because
both reading and writing operate line-by-line without buffering the entire
dataset.

Blank input lines are ignored. A malformed non-blank line raises an error with
its physical source line number.

## Duplicate semantics

Format adapters do not deduplicate records. Duplicate source rows are preserved
exactly and continue into the `ImportDeduplicator` stage. The production
candidate/scoring engine remains the responsibility of `0.9.0b2`.

## Format failures vs row validation

Syntax and structural format errors abort reading because the source itself is
not reliably interpretable. Semantic row problems continue through the normal
Map → Normalize → Validate path and can be represented in `ImportReport`.

## Scope boundary

`0.9.0b1` does not introduce:

```text
Excel
Parquet
Salesforce-specific exports
HubSpot-specific exports
dedup scoring
merge execution
```

The next milestone is `0.9.0b2 — Deduplication`.
