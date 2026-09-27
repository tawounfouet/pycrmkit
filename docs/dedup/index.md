# Deduplication

PyCRMKit `0.9.0b2` adds an explainable, conservative duplicate-detection engine
for CRM import workflows.

## Pipeline position

```text
Read
 ↓
Map
 ↓
Normalize
 ↓
Validate
 ↓
Deduplicate
 ↓
Persist
 ↓
Report
```

The engine implements the existing `ImportDeduplicator` protocol introduced by
the `0.9.0a2` Import Framework.

## Signals

The V0.9 engine supports the roadmap signals:

```text
normalized email
normalized phone
full name
organization
postal address
external identity
custom identifier
```

`DedupProfile.from_mapping()` extracts these values from canonical import/CRM
field names and normalizes them before comparison.

Email and phone normalization reuse the same contact-domain normalization rules
used by PyCRMKit entities. External identities reuse the provider-neutral
`system + external_id` normalization contract introduced in `0.9.0a1`.

## Candidate model

`CandidateRecord` represents an existing CRM entity plus the fields available
for matching.

```python
from pycrmkit.dedup import CandidateRecord

candidate = CandidateRecord(
    "contact-123",
    {
        "email": "ada@example.com",
        "full_name": "Ada Lovelace",
        "organization": "Analytical Engines",
    },
)
```

`CandidateSource` is a protocol, so larger applications can later replace the
in-memory source with repository/search-backed candidate retrieval without
changing the scoring engine.

## Matching

`StandardSignalMatcher` performs exact equality over normalized signal values.
It does not use fuzzy string similarity, embeddings or probabilistic inference
in this release.

This is intentional: V0.9 favors deterministic, auditable behavior over
aggressive matching.

## Default scoring

The default policy scores unique signal types, not the number of values within
a signal:

```text
external identity   100
custom identifier   100
email                70
phone                60
full name            25
organization         15
address              20
```

The total is capped at `100`.

Default thresholds:

```text
0–49     no_match
50–99    review
100      duplicate
```

Examples:

```text
email only                         → 70  → review
phone only                         → 60  → review
email + full name + organization  → 100 → duplicate
phone + full name + address       → 100 → duplicate
external identity                 → 100 → duplicate
custom identifier                 → 100 → duplicate
```

Thresholds and weights are configurable through `DedupScorePolicy`.

## Conflicts

`StandardConflictDetector` records contradictory signals independently from
positive matches.

Warnings currently include disagreements on:

```text
email
phone
full name
organization
external identity within the same system
```

A conflicting custom identifier in the same namespace is classified as
`blocking`, because an application-defined identifier such as a customer number
should prevent automatic duplicate selection when it contradicts the candidate.

A blocking conflict changes the candidate decision to `conflict` even when its
positive score would otherwise reach the duplicate threshold.

## Provenance

Every candidate assessment exposes `DedupProvenance`:

```text
candidate entity ID
score
decision
matched signals
conflicts
normalized matched values
```

This evidence is deterministic and machine-readable via `as_dict()`.

## Import integration

`DeduplicationEngine` implements both rich candidate evaluation and the simple
`ImportDeduplicator.detect()` contract:

```python
from pycrmkit.dedup import (
    CandidateRecord,
    DeduplicationEngine,
    InMemoryCandidateSource,
)

engine = DeduplicationEngine(
    InMemoryCandidateSource(
        (
            CandidateRecord(
                "contact-123",
                {
                    "email": "ada@example.com",
                    "full_name": "Ada Lovelace",
                    "organization": "Analytical Engines",
                },
            ),
        )
    )
)
```

Automatic import skipping occurs only when exactly one candidate receives a
`duplicate` decision. If zero or multiple candidates qualify, the engine does
not auto-select an entity.

That conservative rule prevents ambiguous candidate sets from becoming hidden
merge decisions.

## Scope boundary

`0.9.0b2` detects and explains duplicate candidates. It does **not** merge
records.

Merge execution, primary-record selection, relationship/activity reassignment,
tag union, custom-field conflict policy and merge audit remain scheduled for
`0.9.0b3 — Merge`.
