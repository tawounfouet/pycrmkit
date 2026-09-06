# PyCRMKit

PyCRMKit is a headless Python framework for customer relationships, activities, sales pipelines, and CRM automation.

## Status

Current version: **0.1.0 — CRM Core Stable**.

The first stable CRM Core release exposes a transactional `CRM` facade over Contacts, Organizations, Relationships, Tags, Custom Fields, Events, Audit, and the official Memory adapter. `CRM.memory()` is fully wired, facade mutations commit audit atomically and dispatch domain events after commit, and `CRM.with_context()` carries actor/correlation/causation metadata. The documented `0.1` public API is now compatibility-frozen for the `0.1.x` line. The next milestone is **0.2.0a1 — Activities**.

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

## Quickstart

```python
from pycrmkit import CRM

crm = CRM.memory()
contact = crm.contacts.create(first_name="Ada", last_name="Lovelace")
print(contact.display_name)
```

Use `crm.with_context(actor_id=..., correlation_id=...)` for mutation context, `crm.events` for in-process subscriptions, and `crm.audit` for append-only mutation history.

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
0.1.0a1 Core Primitives                    ✓
0.1.0a2 Contacts                           ✓
0.1.0a3 Organizations                      ✓
0.1.0b1 Relationships                      ✓
0.1.0b2 Tags & Custom Fields               ✓
0.1.0b3 Memory Adapter                      ✓
0.1.0b4 Events & Audit                      ✓
0.1.0rc1 CRM Facade & Integration           ✓
0.1.0  CRM Core Foundation                  ✓
0.2.0a1 Activities                            →
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
