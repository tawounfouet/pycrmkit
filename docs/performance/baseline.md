# V1 Performance Baseline

PyCRMKit `1.0.0b2` establishes the first reproducible performance baseline for
the V1 candidate.

The milestone measures the six scenarios required by the implementation plan:

```text
contact creation
contact search
timeline retrieval
bulk import
repository query pagination
event publication
```

## Purpose

The baseline is intended to answer two different questions:

1. did a release introduce a catastrophic performance regression?
2. how does the current release compare with future V1 candidates on the same runner?

The configured budgets are deliberately broad **release guardrails**. They are
not latency SLAs and should not be presented as production guarantees.

The exact measured medians in the generated JSON artifacts are the comparison
baseline.

## Runner

The benchmark is implemented in:

```text
benchmarks/performance_baseline.py
```

Run it locally with:

```bash
python benchmarks/performance_baseline.py \
  --output performance-baseline.json
```

Each scenario executes:

```text
1 warm-up
5 measured samples
median / minimum / maximum milliseconds per logical operation
```

The JSON also records:

```text
PyCRMKit version
Python version
Python implementation
platform
dataset sizes
guardrail budget
pass/fail
```

## Scenario definitions

### Contact creation

Measures facade-level Contact creation on the Memory adapter with event and audit
work disabled so the baseline isolates Contact/domain/UoW creation overhead.

Dataset:

```text
250 Contact creations per measured sample
```

### Contact search

Measures normalized Contact name search over:

```text
2,000 Contacts
25 searches per sample
page size 25
```

### Timeline retrieval

Measures reverse-chronological Timeline lookup over:

```text
2,000 Timeline entries for one Contact
25 retrievals per sample
page size 50
```

### Bulk import

Measures the format-neutral import pipeline over:

```text
5,000 rows per sample
Read → Map → Normalize → Validate → Deduplicate → Persist → Report
```

The performance scenario uses:

```python
ImportPipeline(
    ...,
    retain_row_results=False,
)
```

This summary mode preserves exact counters without retaining one
`ImportRowResult` object per input row.

The default remains:

```python
retain_row_results=True
```

so existing detailed-report behavior is backward compatible.

### Repository query pagination

Measures paginated repository reads over:

```text
5,000 Contacts
page size 50
offset 2,500
25 queries per sample
```

### Event publication

Measures synchronous exact-type EventBus publication:

```text
10,000 publications per sample
1 subscribed handler
```

## Bounded-memory contract

The V1 performance rule is:

```text
No core API may require loading all records into memory.
```

The qualification interprets this as an API and production-adapter boundary:

- repository list/search contracts require `OffsetPageRequest`;
- default page size is 50;
- maximum page size is 200;
- SQLAlchemy pagination pushes `LIMIT` and `OFFSET` into the database query;
- bulk import accepts iterable readers rather than requiring a materialized list;
- high-volume import can disable per-row result retention while keeping exact
  counters.

The Memory adapter remains intentionally in-memory and is therefore not a claim
about production-scale storage behavior.

## Release guardrails

The current CI ceilings are:

| Scenario | Guardrail |
| --- | ---: |
| Contact creation | 5.0 ms/op |
| Contact search | 50.0 ms/op |
| Timeline retrieval | 50.0 ms/op |
| Bulk import | 1.0 ms/row |
| Repository query pagination | 50.0 ms/op |
| Event publication | 0.5 ms/event |

These ceilings are intentionally much looser than the expected baseline to
reduce false failures on shared CI runners.

Future optimization work should compare the emitted measurements rather than
silently tightening these limits.

## CI qualification

The dedicated workflow is:

```text
.github/workflows/performance-baseline.yml
```

It runs:

```text
performance contract tests
        ↓
source performance baseline
        ↓
build wheel/sdist
        ↓
clean virtual environment
        ↓
install wheel
        ↓
performance baseline with PYTHONPATH=""
        ↓
upload source + wheel JSON evidence
```

The evidence artifact is named:

```text
performance-baseline
```

and contains:

```text
performance-baseline-source.json
performance-baseline-wheel.json
```

## Scope boundary

`1.0.0b2` does not define:

```text
production SLA
PostgreSQL throughput SLA
multi-process scaling guarantees
distributed event throughput
HTTP/API latency SLA
capacity-planning recommendations
```

Those depend on deployment topology, database sizing, network, workload and
application-level integrations.

The next V1 milestone is:

```text
1.0.0b3 — Compatibility Matrix
```
