# CLAUDE.md

# PyCRMKit — Claude Code & Interactive Agent Instructions

This file contains operational instructions for Claude Code, Antigravity, and interactive coding sessions.
It is intentionally a thin overlay. The canonical repository-wide instructions live in:

```text
AGENTS.md
```

Agents MUST read and follow `AGENTS.md` before making changes.

Authority order:
```text
specifications / golden contracts / tests
        ↓
AGENTS.md
        ↓
CLAUDE.md
```

---

## 1. First Action in Every Coding Session (Pre-Flight Protocol)

Before editing code:
```text
1. Read AGENTS.md.
2. Check git status and current branch (git status -sb).
3. Confirm version in src/pycrmkit/__about__.py and pyproject.toml.
4. Inspect the relevant guide or design document in docs/.
5. Inspect adjacent test suites and contract fixtures in tests/.
6. Plan changes strictly respecting hexagonal architecture, Unit of Work, and CAS invariants.
```

The live repository is the source of truth. Never assume state from memory or stale notes.

---

## 2. Preferred Test & Development Cycle

```text
inspect
  → implement small, coherent change
  → run targeted in-memory test: pytest -q tests/unit/core/test_<target>.py
  → run fast feature tours: python3 examples/feature_tours/run_all_tours.py
  → run static analysis: make quality (ruff check + ruff format --check + mypy)
  → run full verification: make verify
```

Do not defer all verification to the end of the session. The in-memory mode `CRM.memory()` and feature tours allow rapid sub-second verification loops.

---

## 3. Standard Commands Cheatsheet

```bash
# Fast feature tours (< 150 ms, zero external dependencies)
make tours
python3 examples/feature_tours/run_all_tours.py

# Executive Terminal CLI (pck) & Diagnostic
pck doctor            # Environment sanity & database connectivity audit
pck dashboard         # Visual sales funnel, KPIs & priority action items
pck config show       # Show active configuration (env, pycrm.yml, defaults)
pck contacts list     # List contacts with phone/email channels & status
pck orgs list         # List corporate accounts and organizations
pck sales opps        # List deal opportunities & weighted revenue forecast
pck sales move <id> <stage>  # Transition deal respecting pipeline rules

# Targeted unit testing
pytest tests/unit/core/test_entities.py -v
pytest tests/unit/sales/ -v
pytest tests/unit/campaigns/ -v
pytest tests/unit/cli/ -v

# Static analysis and quality
make lint             # ruff check .
make format           # ruff format .
make typecheck        # mypy src/pycrmkit
make quality          # ruff check + ruff format check + mypy strict

# Full verification suite
make verify           # tours + test-unit + quality + build

# Documentation
make docs-build       # mkdocs build
make docs-serve       # mkdocs serve

# Database migrations (when working on PostgreSQL storage)
make migration-check
make migration-upgrade
```

---

## 4. Agent Ecosystem & Operational Skills

Autonomous agents and specialized skills live in `.agents/`:
- **Architecture Manifest** : `.agents/AGENTS.md`
- **Specialized Agents** (`.agents/agents/`) :
  - `agency-copilot` : Studio web avant-vente, devis, delivery & MCO
  - `freelance-hunter` : ATS personnel, prospection & relances J+5
  - `tender-bid-manager` : Commande publique, Go/No-Go & verrou DLRO J-1
  - `student-career-coach` : Insertion professionnelle stages & alternances
  - `association-coordinator` : Onboarding associatif, cotisations multi-canal & M365
  - `alumni-network-manager` : Annuaire alumni Django, référents promo & activation
- **Operational Skills Triads** (`.agents/skills/<skill>/`) :
  - Each skill provides `SKILL.md` (rules & CLI), `workflow.md` (Mermaid + ASCII), and `examples.md` (concrete recipes).
  - All skill and agent links MUST remain relative (never use absolute `file:///Users/awf` links).

---

## 5. Prohibited Actions for Agents

- **DO NOT** import physical storage libraries (`sqlalchemy`, `psycopg`, `alembic`) or web frameworks (`fastapi`, `django`) into domain modules (`src/pycrmkit/core/`, `sales/`, `campaigns/`, `segments/`).
- **DO NOT** bypass the Unit of Work (`uow_factory()`) to directly mutate storage repositories.
- **DO NOT** perform blind overwrites on mutable aggregates; always enforce optimistic concurrency control via `expected_revision` and handle `ConflictError`.
- **DO NOT** duplicate or embed raw email/communication body content into campaign linkage models.
- **DO NOT** use floating-point types (`float`) for monetary amounts; always use the `Money` value object (`Decimal`).
- **DO NOT** edit OpenAPI golden schemas or test contract fixtures to make failing tests pass. A mismatch indicates an implementation regression to be fixed in the code.
- **DO NOT** disable spreadsheet formula injection escaping (`prevent_spreadsheet_injection`) on tabular/CSV imports or exports.
