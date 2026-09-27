# Data Operations E2E

PyCRMKit `0.9.0rc1` qualified the complete V0.9 data-operations journey without
introducing a new public orchestration API. `0.9.0` promotes the same behavior
to the stable Data Operations line.

The reference scenario composes the existing public building blocks delivered by
`0.9.0a1` through `0.9.0b3`.

## Qualified journey

```text
CSV source
   ↓
Read
   ↓
Map
   ↓
Normalize
   ↓
Validate
   ↓
Persist Contacts
   ↓
Detect duplicate candidates
   ↓
Review score + provenance
   ↓
Explicit primary selection
   ↓
Merge duplicate
   ↓
Verify audit + external identity ownership
   ↓
Export active normalized contacts
   ↓
CSV / JSON / JSONL round-trip
```

The source scenario lives at:

```text
examples/data_operations/scenario.py
```

The release-candidate E2E test lives at:

```text
tests/e2e/test_data_operations_rc.py
```

## Input fixture

The reference CSV deliberately contains four rows:

```text
Ada Lovelace     primary candidate
Ada Lovelace     duplicate candidate
Grace Hopper     independent contact
Invalid Missing  invalid email
```

The import pipeline therefore proves both accepted-row and rejected-row
behavior.

Expected import report:

```text
rows_read          4
rows_created       3
rows_updated       0
rows_skipped       1
duplicates         0
validation_errors  1
```

The RC scenario imports all valid rows first and then performs the explicit
duplicate-review workflow. This mirrors application-controlled review rather
than silently merging during import.

## Mapping and normalization

The CSV source uses presentation-oriented headers:

```text
First Name
Last Name
Email
Phone
Source
```

`RecordMapper` maps them to canonical fields.

`RecordNormalizer` then applies:

```text
name fields  → strip_text
email        → strip_text + normalize_email
phone        → strip_text + normalize_phone
source       → strip_text + casefold_text
```

`RequiredFieldsValidator` rejects incomplete records before persistence.

## Persistence boundary

The reference application provides a small application-owned
`ImportPersister` implementation backed by `MemoryUnitOfWork` and
`ContactService`.

This is intentional.

PyCRMKit keeps the generic import framework independent from a specific Contact
creation policy. The E2E proves that an application adapter can bridge the two
public contracts without requiring new framework internals.

## Duplicate review

After import, the primary Ada record is evaluated against committed Contact
candidates.

The expected candidate evidence is:

```text
email      match
phone      match
full_name  match
```

The default score reaches:

```text
score     100
decision  duplicate
```

The full `DedupProvenance` from that review is passed directly to
`MergeService`.

## Merge

The caller explicitly selects:

```text
primary_id
duplicate_id
provenance
```

No record is chosen automatically.

The merge verifies:

```text
duplicate archived
external identity transferred to primary
contact.merged audit appended
dedup decision preserved in audit evidence
full provenance retained by MergeResult
```

## Export qualification

After merge, only two active Contacts remain:

```text
Ada Lovelace
Grace Hopper
```

The normalized records are exported through all three V0.9 format adapters:

```text
CSV
JSON
JSONL
```

Each generated representation is read back through the corresponding PyCRMKit
reader and compared with the normalized export records.

This qualifies both write and read interoperability rather than checking only
that files can be emitted.

## Source and installed-wheel qualification

The dedicated GitHub Actions workflow is:

```text
.github/workflows/data-operations-e2e.yml
```

It runs the same scenario twice:

```text
source checkout
built wheel in a clean virtual environment
```

The installed-wheel run clears `PYTHONPATH` so the scenario cannot
accidentally import the source checkout instead of the built distribution.

## Stable boundary

`0.9.0` freezes the behavior qualified by `0.9.0rc1` without expanding the
V0.9 feature surface.

It does not add:

```text
new domain capability
new public orchestration facade
automatic primary selection
automatic merge approval
new persistence schema
new provider dependency
```

The next roadmap milestone is:

```text
1.0.0a1 — Public API Freeze Candidate
```
