# PyCRMKit

**Release channels:** The last GitHub stable release verified for this project is [v1.2.0](https://github.com/tawounfouet/pycrmkit/releases/tag/v1.2.0). The current source checkout targets `1.3.0.dev0`, a development candidate that is **not a published stable v1.3.0 release**. Verify PyPI distribution availability independently at [PyPI](https://pypi.org/project/pycrmkit/). Features on `main` (including the terminal CLI and `.agents/` guides) are not necessarily included in the stable wheel. The `.agents/` directory contains workflow guides, not an autonomous agent execution runtime.


**Headless, framework-agnostic CRM building blocks for Python applications.**

Build customer relationship workflows without running a full CRM server. PyCRMKit provides a typed domain model, a Python facade, events and pluggable persistence; your application controls its API, identity and deployment.

## Features

- **CRM:** contacts, organizations, relationships, tags and custom fields.
- **Sales & activities:** leads, opportunities, pipelines, tasks and customer timelines.
- **Segmentation & campaigns:** saved queries, segment membership, Campaign metadata, audiences and attribution references.
- **Automation:** domain events, audit history, webhooks and provider-neutral email workflows.
- **Data operations:** CSV/JSON/JSONL import and export, external identities, duplicate review and contact merge.
- **Integrations:** in-memory storage, SQLAlchemy/PostgreSQL, FastAPI, Django and Django REST Framework.
- **CLI & Diagnostics (optional):** terminal commands (`pck` / `pycrm`), demonstration dashboards, diagnostic checks (`pck doctor`) and declarative configuration (`pycrm.yml`, `.env`). Dashboard metrics require verification of limits, completeness and currency handling.
- **Agent playbooks (documentation only):** 6 role guides and 7 skill collections in `.agents/`. These are illustrative instructions, not an autonomous agent execution runtime or verified callable toolset.
- **Business Architecture Blueprints:** 7 illustrative design blueprints (`docs/analysis/`) covering web agencies, WhatsApp CRM, freelance hunting, public tenders, student careers, non-profit onboarding, and alumni networks.

## Installation

Requires **Python 3.11–3.13**. For a version available on [PyPI](https://pypi.org/project/pycrmkit/):

```bash
python -m pip install pycrmkit
```

For the latest source checkout (including versions not yet published):

```bash
git clone https://github.com/tawounfouet/pycrmkit.git
cd pycrmkit
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

## Quickstart

```python
from pycrmkit import CRM
from pycrmkit.core.references import EntityReference

crm = CRM.memory()
contact = crm.contacts.create(first_name="Ada", last_name="Lovelace")
contact_ref = EntityReference("contact", contact.id)

task = crm.tasks.create(title="Prepare follow-up", references=(contact_ref,))
crm.tasks.complete(task.id)

for entry in crm.timeline.for_contact(contact.id).items:
    print(entry.title)
```

`CRM.memory()` requires no database or web framework. Add an adapter for durable storage or HTTP endpoints.

## Optional CLI Tool (`pck` / `pycrm`)

The development checkout includes an optional Typer/Rich CLI. Commands below were checked against the current command registration; inspect `pck --help` for the exact installed version. Persistent database operations require explicit configuration and authorization:

```bash
# Install CLI optional dependencies (from local editable checkout)
pip install -e ".[cli]"
# Or using uv:
uv pip install -e ".[cli]"

# Executive CRM Command Center & Analytics Dashboard
pck dashboard --demo  # Ephemeral in-memory demonstration; no persistent seed
pck --help            # Discover supported commands; 'config show' is not registered
pck seed --local      # Explicitly select local demo state; never silently write a DB
pck reset             # Interactively confirm removal of local CRM state

# Domain Management Commands
pck contacts list     # List contacts with phone/email channels & status
pck orgs list         # List corporate accounts and trading brands
pck sales pipelines   # List commercial pipelines & stage probabilities
pck sales opps        # List deal opportunities & weighted revenue forecast
pck sales move <id> <stage>  # Advance opportunity respecting pipeline transition rules
pck campaigns list    # List multi-channel marketing campaigns (v1.2.0)
pck campaigns audience <id>  # View enrolled VIP audience members
pck tasks list        # List scheduled follow-ups and priority action items
pck tasks complete <id>      # Mark action item as completed

# Diagnostics & Engine
pck doctor            # Run diagnostic checks & environment audit
pck version           # Show capability extras (SQLAlchemy, PostgreSQL, FastAPI, etc.)
pck tours             # Run six self-contained demonstration tours
pck migrate --help    # Manage database schema migrations via Alembic
```

## Business Architecture Blueprints

Real-world architectural blueprints with transactional code patterns, Mermaid flows, and ASCII schemas:

- [Web Agency Client Lifecycle](https://github.com/tawounfouet/pycrmkit/blob/main/docs/analysis/web-agency-client-lifecycle.md) - Commercial avant-vente, devis, delivery & ongoing MCO contracts.
- [WhatsApp Dialog Processor](https://github.com/tawounfouet/pycrmkit/blob/main/docs/analysis/whatsapp-and-referral-crm-analysis.md) - Conversational intake, phone identity (E.164) & entity extraction.
- [Freelance Mission Hunter](https://github.com/tawounfouet/pycrmkit/blob/main/docs/analysis/freelance-mission-hunt-and-kpis.md) - Personal ATS, application tracking & J+5 relances.
- [Public Procurement & Tender Qualification](https://github.com/tawounfouet/pycrmkit/blob/main/docs/analysis/public-tenders-and-rfp-bid-management.md) - Go/No-Go scorecard, GME consortia & J-1 16h00 DLRO deadline lock.
- [Student Career Launch](https://github.com/tawounfouet/pycrmkit/blob/main/docs/analysis/student-internship-alternance-job-hunt.md) - Junior & student job hunt, interview notes & academic exports.
- [Non-Profit Member Onboarding](https://github.com/tawounfouet/pycrmkit/blob/main/docs/analysis/association-member-lifecycle-and-onboarding.md) - Multi-channel fees (HelloAsso/virement/PayPal), M365 IT tasks & annual renewal campaigns (*Diversité Alternative*).
- [Alumni Directory & Network Activation](https://github.com/tawounfouet/pycrmkit/blob/main/docs/analysis/alumni-directory-and-network-activation.md) - Cohort ambassadors, Google Forms import, tokenized invite & Django account activation.

## Agent Playbooks (`.agents/`) - Documentation Only

PyCRMKit provides role and workflow documents in `.agents/`. These instructions have not been qualified as an agent runtime, and their sample commands are illustrative unless validated against the installed CLI and public Python API:
- **6 Agent Role Guides** (`.agents/agents/`): `agency-copilot`, `freelance-hunter`, `tender-bid-manager`, `student-career-coach`, `association-coordinator`, `alumni-network-manager`.
- **7 Illustrative Skill Triads** (`.agents/skills/`): complete specification (`SKILL.md`), operational workflow with dual Mermaid & ASCII diagrams (`workflow.md`), and candidate recipes (`examples.md`). Some commands in these recipes are not currently supported and must not be executed without verification.
- **Standardized Workflows**: all skill workflows include dual Mermaid and ASCII diagrams, and strictly use relative links.

## Architecture

```text
Application → CRM facade → Domain services & events → Repository contracts → Adapters
```

The core has **no mandatory third-party runtime dependencies**. SQLAlchemy, PostgreSQL, FastAPI, Django/DRF and email integrations are opt-in.

**Scope:** Campaigns manage metadata, audiences and references; they do not send marketing messages. Host applications must enforce authentication, tenant authorization and database migration ownership.

## Documentation

- [Quickstart](https://github.com/tawounfouet/pycrmkit/blob/main/docs/getting-started/quickstart.md) · [Guides](https://github.com/tawounfouet/pycrmkit/blob/main/docs/guides/index.md) · [Blueprints & Analysis](https://github.com/tawounfouet/pycrmkit/blob/main/docs/analysis/web-agency-client-lifecycle.md)
- [Campaigns](https://github.com/tawounfouet/pycrmkit/blob/main/docs/campaigns/index.md) · [Compatibility](https://github.com/tawounfouet/pycrmkit/blob/main/docs/reference/1.2.0-support-and-compatibility.md) · [Agent Ecosystem](https://github.com/tawounfouet/pycrmkit/blob/main/.agents/AGENTS.md)
- [Releases](https://github.com/tawounfouet/pycrmkit/releases) · [Changelog](https://github.com/tawounfouet/pycrmkit/blob/main/CHANGELOG.md) · [Contributing](https://github.com/tawounfouet/pycrmkit/blob/main/CONTRIBUTING.md)

**Release availability:** Check the GitHub Releases page and PyPI independently. A version present in source control is not necessarily published on either platform.

## Development

```bash
python -m pip install -e ".[dev]"
pytest
```

## License

[MIT](https://github.com/tawounfouet/pycrmkit/blob/main/LICENSE) © 2026 Thomas Awounfouet.
