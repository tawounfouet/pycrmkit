# PyCRMKit

**Headless, framework-agnostic CRM building blocks for Python applications.**

Build customer relationship workflows without running a full CRM server. PyCRMKit provides a typed domain model, a Python facade, events and pluggable persistence; your application controls its API, identity and deployment.

## Features

- **CRM:** contacts, organizations, relationships, tags and custom fields.
- **Sales & activities:** leads, opportunities, pipelines, tasks and customer timelines.
- **Segmentation & campaigns:** saved queries, segment membership, Campaign metadata, audiences and attribution references.
- **Automation:** domain events, audit history, webhooks and provider-neutral email workflows.
- **Data operations:** CSV/JSON/JSONL import and export, external identities, duplicate review and contact merge.
- **Integrations:** in-memory storage, SQLAlchemy/PostgreSQL, FastAPI, Django and Django REST Framework.
- **CLI & Executive Diagnostics:** terminal command center (`pck` / `pycrm`), live visual sales funnel, pipeline KPIs, environment diagnostics (`pck doctor`), and declarative config (`pycrm.yml`, `.env`).
- **Autonomous Agent Ecosystem:** orchestration layer (`.agents/`) with 6 specialized domain agents and 7 operational skill triads equipped with dual Mermaid and clean ASCII workflows.
- **Business Architecture Blueprints:** 7 production-grade blueprints (`docs/analysis/`) covering web agencies, WhatsApp CRM, freelance hunting, public tenders, student careers, non-profit onboarding, and alumni networks.

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

## CLI Tool (`pck` / `pycrm`)

PyCRMKit includes an optional modern terminal CLI powered by Typer and Rich with zero external database dependencies:

```bash
# Install CLI optional dependencies (from local editable checkout)
pip install -e ".[cli]"
# Or using uv:
uv pip install -e ".[cli]"

# Executive CRM Command Center & Analytics Dashboard
pck dashboard         # Live KPIs, visual sales funnel, campaigns, action items
pck config show       # Show active configuration (env, pycrm.yml, safe defaults)
pck seed              # Seed realistic B2B enterprise demonstration scenario
pck reset -f          # Reset local CRM store state

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
pck tours             # Run autonomous feature tours suite (< 150 ms)
pck migrate --help    # Manage database schema migrations via Alembic
```

## Business Architecture Blueprints

Real-world architectural blueprints with transactional code patterns, Mermaid flows, and ASCII schemas:

- [Web Agency Client Lifecycle](docs/analysis/web-agency-client-lifecycle.md) — Commercial avant-vente, devis, delivery & ongoing MCO contracts.
- [WhatsApp Dialog Processor](docs/analysis/whatsapp-and-referral-crm-analysis.md) — Conversational intake, phone identity (E.164) & entity extraction.
- [Freelance Mission Hunter](docs/analysis/freelance-mission-hunt-and-kpis.md) — Personal ATS, application tracking & J+5 relances.
- [Public Procurement & Tender Qualification](docs/analysis/public-tenders-and-rfp-bid-management.md) — Go/No-Go scorecard, GME consortia & J-1 16h00 DLRO deadline lock.
- [Student Career Launch](docs/analysis/student-internship-alternance-job-hunt.md) — Junior & student job hunt, interview notes & academic exports.
- [Non-Profit Member Onboarding](docs/analysis/association-member-lifecycle-and-onboarding.md) — Multi-channel fees (HelloAsso/virement/PayPal), M365 IT tasks & annual renewal campaigns (*Diversité Alternative*).
- [Alumni Directory & Network Activation](docs/analysis/alumni-directory-and-network-activation.md) — Cohort ambassadors, Google Forms import, tokenized invite & Django account activation.

## Autonomous Agent Ecosystem (`.agents/`)

PyCRMKit embeds an operational agent ecosystem in `.agents/`:
- **6 Autonomous Agents** (`.agents/agents/`): `agency-copilot`, `freelance-hunter`, `tender-bid-manager`, `student-career-coach`, `association-coordinator`, `alumni-network-manager`.
- **7 Operational Skill Triads** (`.agents/skills/`): complete specification (`SKILL.md`), operational workflow with dual Mermaid & ASCII diagrams (`workflow.md`), and concrete recipes (`examples.md`).
- **Standardized Workflows**: all skill workflows include dual Mermaid and ASCII diagrams, and strictly use relative links.

## Architecture

```text
Application → CRM facade → Domain services & events → Repository contracts → Adapters
```

The core has **no mandatory third-party runtime dependencies**. SQLAlchemy, PostgreSQL, FastAPI, Django/DRF and email integrations are opt-in.

**Scope:** Campaigns manage metadata, audiences and references; they do not send marketing messages. Host applications must enforce authentication, tenant authorization and database migration ownership.

## Documentation

- [Quickstart](docs/getting-started/quickstart.md) · [Guides](docs/guides/index.md) · [Blueprints & Analysis](docs/analysis/web-agency-client-lifecycle.md)
- [Campaigns](docs/campaigns/index.md) · [Compatibility](docs/reference/1.2.0-support-and-compatibility.md) · [Agent Ecosystem](.agents/AGENTS.md)
- [Releases](https://github.com/tawounfouet/pycrmkit/releases) · [Changelog](CHANGELOG.md) · [Contributing](CONTRIBUTING.md)

**Release availability:** Check the GitHub Releases page and PyPI independently. A version present in source control is not necessarily published on either platform.

## Development

```bash
python -m pip install -e ".[dev]"
pytest
```

## License

[MIT](https://github.com/tawounfouet/pycrmkit/blob/main/LICENSE) © 2026 Thomas Awounfouet.
