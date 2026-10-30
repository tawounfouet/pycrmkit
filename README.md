# PyCRMKit

**Headless, framework-agnostic CRM building blocks for Python applications.**

Build customer relationship workflows without adopting a full CRM server. PyCRMKit provides a typed domain model, a Python facade, events and pluggable persistence; your application controls its API, identity and deployment.

> **Release status:** The `1.2.0` source is qualified on `main`, but **`v1.2.0` is not yet published** as a GitHub stable release and PyPI availability is not verified. The latest verified GitHub prerelease is [`v1.2.0rc1`](https://github.com/tawounfouet/pycrmkit/releases/tag/v1.2.0rc1). See the [1.2.0 release notes](docs/releases/1.2.0.md).

## Features

- **CRM:** contacts, organizations, relationships, tags and custom fields.
- **Sales & activities:** leads, opportunities, pipelines, tasks and customer timelines.
- **Segmentation & campaigns:** saved queries, segment membership, Campaign metadata, audiences and attribution references.
- **Automation:** domain events, audit history, webhooks and provider-neutral email workflows.
- **Data operations:** CSV/JSON/JSONL import and export, external identities, duplicate review and contact merge.
- **Integrations:** in-memory storage, SQLAlchemy/PostgreSQL, FastAPI, Django and Django REST Framework.

## Quickstart

Requires **Python 3.11–3.13**. Until the stable release is published, install the current source from a checkout:

```bash
git clone https://github.com/tawounfouet/pycrmkit.git
cd pycrmkit
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

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

`CRM.memory()` requires no database or web framework. Add an adapter when your application needs durable storage or HTTP endpoints.

## Architecture

```text
Application → CRM facade → Domain services & events → Repository contracts → Adapters
```

The core has **no mandatory third-party runtime dependencies**. SQLAlchemy, PostgreSQL, FastAPI, Django/DRF and email integrations are opt-in.

**Scope:** Campaigns manage metadata, audiences and references; they do not send marketing messages. Host applications must enforce authentication, tenant authorization and their chosen database migration ownership.

## Documentation

- [Getting started](docs/getting-started/quickstart.md) · [Step-by-step guides](docs/guides/index.md)
- [Campaigns](docs/campaigns/index.md) · [Compatibility and support](docs/reference/1.2.0-support-and-compatibility.md)
- [Changelog](CHANGELOG.md) · [Release notes](docs/releases/1.2.0.md) · [Contributing](CONTRIBUTING.md)

## Development

```bash
python -m pip install -e ".[dev]"
pytest
```

## License

[MIT](LICENSE) © 2026 Thomas Awounfouet.
