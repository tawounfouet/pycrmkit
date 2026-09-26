# Django Integration

PyCRMKit's Django integration is optional. The domain layer remains
framework-agnostic.

Install it with:

```bash
pip install "pycrmkit[django]"
```

## Current prerelease scope

`0.8.0b2 — Optional DRF` builds on the Django application, persistence,
migration, admin, and transaction bridge delivered by the preceding milestones.

```text
src/pycrmkit/integrations/django/
├── __init__.py
├── apps.py
├── models.py
├── repositories.py
├── transactions.py
├── admin.py
├── migrations/
│   ├── __init__.py
│   └── 0001_initial.py
└── typecheck_settings.py
```

The runtime integration remains optional. `typecheck_settings.py` exists only
for strict `django-stubs` analysis.

## Application registration

Add:

```python
INSTALLED_APPS = [
    # application apps...
    "pycrmkit.integrations.django.apps.PyCRMKitDjangoConfig",
]
```

The application label is:

```text
pycrmkit_crm
```

The package `pycrmkit.integrations.django` deliberately stays registry-safe:
it does not eagerly import models, repositories, admin or the transaction
bridge while Django is still populating the app registry.

## Dependency direction

```text
Django application
      ↓
PyCRMKit service / facade
      ↓
Repository Protocol
      ↓
Django Repository
      ↓
Django ORM model
      ↓
Database
```

Django models are persistence representations only. They do not become
PyCRMKit domain entities.

## Current persistence models

```text
Contact
├── ContactEmail
├── ContactPhone
└── ContactAddress

Organization
├── OrganizationDomain
└── OrganizationAddress

Relationship
```

The initial physical tables follow the existing `pycrmkit_*` naming
convention. Behavioral adapter equivalence does not imply that arbitrary
SQLAlchemy and Django schemas can always be swapped without migration.

## Repositories

```python
from pycrmkit.integrations.django.repositories import (
    DjangoContactRepository,
    DjangoOrganizationRepository,
    DjangoRelationshipRepository,
)
```

These implement the existing backend-neutral repository contracts and replay
the same contract suites used by other supported adapters.

## Django migrations

`0.8.0b1` introduces the adapter-specific migration history:

```text
pycrmkit_crm
└── 0001_initial
```

Apply it through Django's normal migration lifecycle:

```bash
python manage.py migrate pycrmkit_crm
```

Importing PyCRMKit never runs migrations automatically.

The test gate verifies:

```text
migration discovery
empty database → 0001_initial
0001_initial → zero
model/migration state drift via makemigrations --check --dry-run
packaged-wheel migration execution
```

Django and Alembic migrations remain separate infrastructure histories.

## Transaction bridge

Use:

```python
from pycrmkit.integrations.django.transactions import DjangoTransactionBridge

with DjangoTransactionBridge() as bridge:
    bridge.contacts.save(contact)
    bridge.organizations.save(organization)
    bridge.commit()
```

Observable semantics are:

```text
enter
  ↓
Django transaction.atomic()
  ↓
repository writes
  ↓
explicit commit
  ├─ success → durable state
  └─ failure → mapped RepositoryError

exit without commit → rollback
exception → rollback
explicit rollback → discard work + fresh transaction
```

The bridge currently exposes the Django repositories implemented in this
prerelease line:

```text
contacts
organizations
relationships
```

It should therefore not be described as the complete PyCRMKit
`UnitOfWork` protocol yet. Full cross-domain Django persistence conformance
belongs to later qualification.

### Ambient Django transactions

If the bridge is opened inside an existing `transaction.atomic()` block, its
internal atomic block participates through Django's savepoint semantics.

Staged PyCRMKit domain events are deferred until the actual outer transaction
commits:

```text
outer transaction
    ↓
DjangoTransactionBridge
    ↓
bridge.commit()
    ↓
savepoint released
    ↓
NO event yet
    ↓
outer COMMIT
    ↓
event published
```

If the outer transaction rolls back, the staged callback is discarded and the
event is not published.

For a top-level bridge transaction, events are published only after its
database commit has succeeded. A post-commit subscriber failure therefore does
not make already committed database state appear rolled back.

## Django admin

When `django.contrib.admin` is installed, Django's normal admin autodiscovery
loads the PyCRMKit admin helpers.

Registered parents:

```text
ContactModel
OrganizationModel
RelationshipModel
```

Contact exposes inline Email/Phone/Address rows. Organization exposes inline
Domain/Address rows.

The admin is an operational persistence view; domain correctness still belongs
to PyCRMKit services and policies, not Django admin hooks or signals.

## Optional dependency boundary

```bash
pip install pycrmkit
```

still works without Django installed or configured.

Django-specific code requires:

```bash
pip install "pycrmkit[django]"
```

Typing uses `django-stubs` only as a development dependency. Runtime admin
classes do not require `django-stubs-ext` monkeypatching.

## Optional DRF bridge

Django REST Framework remains a separate install:

```bash
pip install "pycrmkit[drf]"
```

The plain `pycrmkit[django]` extra deliberately does not include DRF.

The DRF transport preserves the application boundary:

```text
HTTP / DRF
    ↓
serializer / ViewSet
    ↓
CRM facade
    ↓
domain service
    ↓
Unit of Work / Repository Protocol
    ↓
selected adapter
```

The initial router exposes Contacts, Organizations, and Relationships. It does
not use Django ORM models or repositories directly.

The application supplies a request-time CRM factory with
`PYCRMKIT_CRM_FACTORY`. `X-Actor-ID` and `X-Correlation-ID` are propagated
into the CRM context when present.

The error bridge maps stable PyCRMKit exceptions to 404/409/422/500/502 and
normalizes DRF input validation into `request.validation_error` payloads
without echoing submitted input values.

See the dedicated [DRF Integration](drf.md) guide.

## Compatibility target

```text
Django >=5.2,<6
Python 3.11–3.13
```

## Deferred scope

Still intentionally deferred:

```text
0.8.0rc1  reference Django application + E2E
0.8.0     stable Django integration
```

## Next milestone

The next delivery is **`0.8.0rc1 — Django Example + E2E`**.
