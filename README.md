# PyCRMKit

PyCRMKit is a headless Python framework for customer relationships, activities, sales pipelines, and CRM automation.

## Status

Current stable version: **0.7.0 — FastAPI Integration Stable**.  
Latest integration prerelease: **0.8.0rc1 — Django Example + E2E**.

The stable `0.1`–`0.5` CRM, Activity/Timeline, Sales, Communication and Eventing/Webhooks contracts are now compatibility-governed. `0.5.0` promotes the fully qualified release candidate without new functional scope: committed CRM domain events automatically match registered subscriptions, serialize/sign/deliver, persist retry/dead-letter state, and expose delivery history.

The project is intentionally framework-agnostic at its core. SMTP, Jinja2, Resend, SQLAlchemy/PostgreSQL, FastAPI, Django, and Django REST Framework remain opt-in integrations. `0.7.0` is the stable FastAPI line. `0.8.0rc1` now qualifies the Django app/persistence bridge, migrations, admin, transactions and optional DRF surface together through a PostgreSQL 17 reference application and clean-wheel E2E.

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

Use `crm.with_context(actor_id=..., correlation_id=...)` for explicit mutation context. For event-driven work, use `crm.with_event(parent_event)` so actor/correlation context is propagated and `causation_id` points to the direct parent event.

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
0.3.0b2 Lead Conversion                           ✓
0.3.0rc1 Sales Integration                         ✓
0.3.0  Sales Foundation                             ✓
0.4.0a1 Communication Domain                         ✓
0.4.0a2 Email Provider Protocol                      ✓
0.4.0b1 Templates & SMTP                             ✓
0.4.0b2 Resend Adapter                               ✓
0.4.0rc1 Delivery Events & History                   ✓
0.4.0  Communication Stable                          ✓
0.5.0a1 Event Registry & Serialization                ✓
0.5.0a2 Correlation & Causation                       ✓
0.5.0b1 Webhook Registrations                          ✓
0.5.0b2 Webhook Delivery Engine                         ✓
0.5.0rc1 Eventing & Webhooks E2E                         ✓
0.5.0  Eventing & Webhooks Stable                            ✓
0.6.0a1 SQLAlchemy Foundation                                ✓
0.6.0a2 Repository Adapters                                   ✓
0.6.0b1 Unit of Work & Transactions                           ✓
0.6.0b2 PostgreSQL                                             ✓
0.6.0b3 Alembic / Migrations                                   ✓
0.6.0rc1 Persistence Qualification                              ✓
0.6.0  Persistence Foundation                                    ✓
0.7.0a1 Schemas & Dependency Bridge                              ✓
0.7.0b1 Routers                                                   ✓
0.7.0b2 OpenAPI & Error Mapping                                  ✓
0.7.0rc1 Example + E2E                                             ✓
0.7.0  FastAPI Integration                                           ✓
0.8.0a1 Django Application Bridge                                     ✓
0.8.0b1 Django Migrations & Admin                                      ✓
0.8.0b2 Optional DRF                                                   ✓
0.8.0rc1 Django Example + E2E                                          ✓
0.8.0  Django Integration                                              →
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
