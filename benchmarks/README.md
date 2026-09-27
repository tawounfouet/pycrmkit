# PyCRMKit Performance Baseline

This directory contains the reproducible V1 performance baseline introduced in
`1.0.0b2`.

Run it with:

```bash
python benchmarks/performance_baseline.py --output performance-baseline.json
```

The runner measures:

```text
contact creation
contact search
timeline retrieval
bulk import
repository query pagination
event publication
```

Each result reports median/min/max milliseconds per logical operation across
five measured samples after one warm-up.

The configured budgets are **release guardrails, not product SLAs**. Their job
is to detect catastrophic regressions on shared CI runners. The actual measured
JSON artifact is the baseline to compare between releases.

The dedicated GitHub Actions workflow executes the same runner twice:

```text
source checkout
built wheel in a clean virtual environment
```

For high-volume imports, the benchmark uses:

```python
ImportPipeline(..., retain_row_results=False)
```

so exact counters are retained without requiring one `ImportRowResult` object
per source row.
