# AGENTS.md

# PyCRMKit - Repository Instructions for Coding Agents

This file defines the canonical repository-level instructions for AI coding agents and automated contributors working on PyCRMKit.
It applies to the entire repository unless a more specific `AGENTS.md` exists in a subdirectory.

Human-maintained specifications, public contracts, tests, and release evidence remain authoritative over agent assumptions.

---

## 1. Repository Identity

```text
Project: PyCRMKit
Package: pycrmkit
Repository: tawounfouet/pycrmkit
Current stable baseline: 1.2.0
Current milestone: LOT-32-013 Stable (v1.2.0)
Python support: 3.11 / 3.12 / 3.13 / 3.14
Build tool: setuptools / wheel
```

PyCRMKit is a headless CRM framework providing typed, transactional, and engine-agnostic building blocks for Python applications.

Canonical Architecture & Execution Model:
```text
Application / Client Code
        ↓
Facade API (crm.contacts, crm.organizations, crm.pipelines, crm.opportunities, crm.campaigns, crm.segments, ...)
        ↓
Domain Services & Unit of Work (Transaction boundary, business validation, aggregate invariants)
        ↓
Repositories & Adapters (In-Memory for zero-dep dev/tests, SQLAlchemy/PostgreSQL for production)
        ↓
Domain Events / Audit Trail & Webhook Dispatchers (HMAC signatures, delivery retries)
```

---

## 2. Chain of Authority

When resolving ambiguity or handling test regressions, agents MUST follow this strict hierarchy:

```text
1. Specifications, RFCs, and Release closeout reports (docs/development/, docs/guides/)
2. Golden contracts (OpenAPI golden schemas, transport parity tests)
3. Architecture and Unit test suites (tests/unit/, tests/contracts/)
4. AGENTS.md (this file)
5. CLAUDE.md
6. Agent assumptions / LLM training weights
```

---

## 3. Non-Negotiable Architecture Invariants

### Invariant 1: Hexagonal Boundary Isolation & Domain Purity
- Domain modules (`src/pycrmkit/core/`, `src/pycrmkit/sales/`, `src/pycrmkit/campaigns/`, `src/pycrmkit/segments/`, `src/pycrmkit/communication/`) **MUST NOT** import physical storage drivers (`sqlalchemy`, `psycopg`, `alembic`) or transport frameworks (`fastapi`, `pydantic`, `django`).
- Physical connectors live strictly in `src/pycrmkit/storage/` and integrations live in `src/pycrmkit/integrations/` as optional extras (`sqlalchemy`, `postgresql`, `fastapi`, `django`).
- The in-memory adapter (`CRM.memory()`) must remain fully functional with **zero third-party dependencies**.

### Invariant 2: Transactional Integrity via Unit of Work
- All state mutations (create, update, delete, stage transitions) **MUST** execute inside an explicit Unit of Work (`with self._runtime.uow_factory() as uow:`).
- Audit trail recording (`_runtime.record_change`) and Domain Event emission are atomically committed with the Unit of Work. Never bypass the UoW to mutate storage directly.

### Invariant 3: Optimistic Concurrency Control (CAS) & Revision Guarantees
- Multi-user mutable aggregates (such as `Campaign`) enforce compare-and-swap (CAS) via `expected_revision`.
- If an update or transition specifies an `expected_revision` that does not match the active entity revision, it **MUST** raise `ConflictError` from `pycrmkit.exceptions`. Never perform blind overwrites.

### Invariant 4: Privacy & Isolation of Communication Payloads
- Campaign touchpoint linkage (`crm.campaigns.link_communication`) stores references, touchpoint roles, and delivery metadata; it **NEVER** duplicates, embeds, or leaks message bodies into campaign projection read-models.
- Emails and communications are isolated entities with dedicated providers (`EmailProvider` port).

### Invariant 5: DataOps Hygiene & Safe Import/Export
- Protection against spreadsheet formula injection (`prevent_spreadsheet_injection`) is mandatory on any CSV or tabular import/export path. Any cell value starting with `=`, `+`, `-`, or `@` must be safely escaped.
- Batch imports are strictly bounded (`MAX_CAMPAIGN_IMPORT_ROWS = 1000`). Stale or out-of-bound batch operations must fail closed.

### Invariant 6: Strict Financial Precision
- Monies are modeled exclusively through immutable `Money(amount: Decimal, currency: str)` Value Objects. Floating-point arithmetic for monetary calculations is strictly forbidden.

### Invariant 7: Golden Contracts & Contract Fixtures Immutability
- OpenAPI golden schemas and transport contract fixtures are auditable artifacts.
- Agents **MUST NEVER** alter golden contract fixtures to make a failing test pass. A mismatch indicates an implementation regression to be fixed in the code.

---

## 4. Test Suites & Verification Protocol

PyCRMKit enforces a multi-tier test pyramid:

1. **Feature Tours Suite** (`examples/feature_tours/run_all_tours.py`):
   Autonomous, in-memory end-to-end verification of all core domains in < 150 ms.
2. **Unit Tests** (`tests/unit/`):
   Domain logic, entities, value objects, and memory repositories.
3. **Contract & Transport Parity Tests** (`tests/contracts/`, `tests/integrations/test_campaign_transport_parity.py`):
   Parity between FastAPI, Django, and Core APIs against OpenAPI golden schemas.
4. **Integration & Migration Tests** (`tests/integrations/`, `tests/migrations/`):
   PostgreSQL and Alembic database migration qualifications.

---

## 5. Coding Conventions

- **Python version**: Modern Python 3.11+ syntax (`from __future__ import annotations`, pipe unions `X | Y`, tuple unpackings).
- **Type annotations**: `mypy --strict` compliance across `src/pycrmkit`. Every public function and method must have complete type signatures.
- **Linter & Formatter**: Ruff with 100 character line limit.
- **Docstrings & Comments**: Preserve existing documentation integrity; describe rationale over obvious syntax.
