# Contributing to PyCRMKit

PyCRMKit is developed incrementally through qualified milestones.

## Development principles

- Keep the core headless and framework-agnostic.
- Put domain behavior before infrastructure.
- Add tests with every behavior change.
- Preserve explicit repository and adapter boundaries.
- Do not add optional framework dependencies to the core install.

## Local workflow

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
pytest
```

Before opening a pull request, run the project quality commands documented in the Makefile.

## Changes

User-facing changes should update `CHANGELOG.md`. Public API, event schema, migration, and compatibility impacts must be called out explicitly.
