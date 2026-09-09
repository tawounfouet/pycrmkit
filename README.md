# PyCRMKit

PyCRMKit is a headless Python framework for customer relationships, activities, sales pipelines, and CRM automation.

## Status

Current version: **0.3.0b1 — Pipeline & Stage**.

The stable `0.2` Activity/Task/Timeline contract remains compatibility-frozen. `0.3.0b1` adds configurable Pipeline/Stage definitions, explicit transition policies, terminal outcomes, Decimal probability defaults, stage-entry timestamps and policy-driven `crm.opportunities.move(...)`. Lead-to-Opportunity conversion remains deferred to **0.3.0b2 — Lead Conversion**.

The project is intentionally framework-agnostic at its core. Django, FastAPI, SQLAlchemy, PostgreSQL, communication providers, AI, and agent integrations are optional capabilities introduced through dedicated milestones.

## Architecture

```text
Application
    ↓
PyCRMKit
    ↓
CRM Domain Model
    ↓
Services / Policies / Domain Events
    ↓
Timeline Projectors / Repository Contracts
    ↓
Storage / Integrations
```

## Quickstart

```python
from pycrmkit import CRM
from pycrmkit.activities import ActivityParticipant
from pycrmkit.core.references import EntityReference

crm = CRM.memory()
contact = crm.contacts.create(first_name="Ada", last_name="Lovelace")
contact_ref = EntityReference("contact", contact.id)

crm.activities.log(
    type="call",
    subject="Commercial follow-up",
    direction="outbound",
    participants=(ActivityParticipant(contact_ref, is_primary=True),),
)
task = crm.tasks.create(
    title="Prepare renewal",
    priority="high",
    references=(contact_ref,),
)
crm.tasks.complete(task.id)

history = crm.timeline.for_contact(contact.id)
for entry in history.items:
    print(entry.occurred_at, entry.event_type, entry.title)
```

Use `crm.with_context(actor_id=..., correlation_id=...)` for mutation context, `crm.events` for in-process subscriptions, `crm.audit` for append-only system mutation history, and `crm.timeline` for customer/relationship history.

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
0.2.0a1 Activities                            ✓
0.2.0a2 Tasks                                 ✓
0.2.0b1 Timeline                              ✓
0.2.0rc1 Activity & Timeline Integration       ✓
0.2.0  Activity & Timeline Stable              ✓
0.3.0a1 Money & Lead Foundation                ✓
0.3.0a2 Opportunities                           ✓
0.3.0b1 Pipeline & Stage                         ✓
0.3.0b2 Lead Conversion                           →
0.3.0rc1 Sales Integration
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
