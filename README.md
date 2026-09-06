# PyCRMKit

PyCRMKit is a headless Python framework for customer relationships, activities, sales pipelines, and CRM automation.

## Status

Current version: **0.0.3 — Engineering Foundation**.

The repository foundation, packaging, quality tooling, CI, documentation scaffold, and release engineering are now established. The next implementation milestone is **0.1.0a1 — Core Primitives**.

The project is intentionally framework-agnostic at its core. Django, FastAPI, SQLAlchemy, PostgreSQL, communication providers, AI, and agent integrations are optional capabilities introduced through dedicated milestones.

## Architecture

```text
Application
    ↓
PyCRMKit
    ↓
CRM Domain Model
    ↓
Services / Policies / Events
    ↓
Repository Contracts
    ↓
Storage / Integrations
```

## Install for development

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
pytest
```

## Development roadmap

```text
0.0.1  Repository Bootstrap              ✓
0.0.2  Packaging & Quality Tooling       ✓
0.0.3  CI / Docs / Release Engineering  ✓
0.1.0  CRM Core Foundation
0.2.0  Activity & Timeline
0.3.0  Sales Foundation
0.4.0  Communication
0.5.0  Eventing & Webhooks
0.6.0  Persistence Foundation
0.7.0  FastAPI Integration
0.8.0  Django Integration
0.9.0  Data Operations
1.0.0  Production Stable
```

## Quality

```bash
make test
make lint
make typecheck
make coverage
make build
python scripts/release_check.py
```

## License

MIT © 2026 Thomas Awounfouet.
