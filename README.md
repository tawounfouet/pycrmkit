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

## Architecture

```text
Application → CRM facade → Domain services & events → Repository contracts → Adapters
```

The core has **no mandatory third-party runtime dependencies**. SQLAlchemy, PostgreSQL, FastAPI, Django/DRF and email integrations are opt-in.

**Scope:** Campaigns manage metadata, audiences and references; they do not send marketing messages. Host applications must enforce authentication, tenant authorization and database migration ownership.

## Documentation

- [Quickstart](https://github.com/tawounfouet/pycrmkit/blob/main/docs/getting-started/quickstart.md) · [Guides](https://github.com/tawounfouet/pycrmkit/blob/main/docs/guides/index.md)
- [Campaigns](https://github.com/tawounfouet/pycrmkit/blob/main/docs/campaigns/index.md) · [Compatibility](https://github.com/tawounfouet/pycrmkit/blob/main/docs/reference/1.2.0-support-and-compatibility.md)
- [Releases](https://github.com/tawounfouet/pycrmkit/releases) · [Changelog](https://github.com/tawounfouet/pycrmkit/blob/main/CHANGELOG.md) · [Contributing](https://github.com/tawounfouet/pycrmkit/blob/main/CONTRIBUTING.md)

**Release availability:** Check the GitHub Releases page and PyPI independently. A version present in source control is not necessarily published on either platform.

## Development

```bash
python -m pip install -e ".[dev]"
pytest
```

## License

[MIT](https://github.com/tawounfouet/pycrmkit/blob/main/LICENSE) © 2026 Thomas Awounfouet.
