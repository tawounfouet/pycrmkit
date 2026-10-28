# Django Integration

PyCRMKit's Django integration is optional. The domain layer remains
framework-agnostic.

Install it with:

```bash
pip install "pycrmkit[django]"
```

## Stable 0.8.x scope

`0.8.0 — Django Integration Stable` promotes the fully qualified release
candidate without adding new Django feature scope. The Django application,
persistence, migration, admin, transaction and optional DRF layers are
qualified together against PostgreSQL 17.

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

The bridge exposes the Django repositories implemented in the stable `0.8.x`
line:

```text
contacts
organizations
relationships
```

It must therefore not be described as the complete PyCRMKit `UnitOfWork`
protocol. Full cross-domain Django persistence is outside the stable `0.8.0`
scope and requires a future qualified milestone.

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

## Reference application

The stable reference application lives under `examples/django/` and assembles:

```text
Django 5.2
  ↓
Django admin + DRF
  ↓
PyCRMKit CRM facade
  ↓
DjangoTransactionBridge
  ↓
Django repositories
  ↓
PostgreSQL 17
```

Its deployment path is intentionally migration-first:

```text
configure PYCRMKIT_DATABASE_URL
    ↓
python manage.py migrate
    ↓
python manage.py check
    ↓
start Django
```

The stable release gate performs a two-process E2E: one process creates a Contact,
Organization and Relationship through DRF, then a fresh Python/Django process
reloads the records from PostgreSQL, mutates them, verifies admin registration
and checks the applied `pycrmkit_crm.0001_initial` migration. The complete path
is repeated from a clean installed wheel after resetting the PostgreSQL schema.

## Compatibility target

```text
Django >=5.2,<6
DRF >=3.18,<4
PostgreSQL 17 reference E2E
Python 3.11–3.13
```

## Stable boundary

The Django persistence adapter remains intentionally bounded to Contacts,
Organizations and Relationships. Stable status freezes that documented scope;
it does not imply a complete cross-domain Django UnitOfWork.

## V0.9 prerelease extension — External Identities

`0.9.0a1` adds `ExternalIdentityModel` and `DjangoExternalIdentityRepository` to the optional Django adapter. Django schemas advance explicitly through:

```text
0001_initial
    ↓
0002_external_identity
```

The new repository participates in `DjangoTransactionBridge` and is qualified against the same external-identity repository contract as Memory and SQLAlchemy. The stable `0.8.x` compatibility promise remains unchanged; this is prerelease `0.9.x` scope.

## Next milestone

The project roadmap now advances to **`0.9.0a2 — Import Framework`**.

## Next milestone

The next delivery is **`0.8.0 — Django Integration Stable`**.


## V1.1 beta extension — Segmentation

**1.1.0b2** adds Django persistence capabilities for the Segmentation domain:

~~~text
DjangoTransactionBridge
├── segments
├── segment_memberships
├── segment_query_executor
└── saved_queries
~~~

The packaged Django migration history now continues:

~~~text
0001_initial
    ↓
0002_external_identity
    ↓
0003_segmentation
~~~

The new persistence representations are:

~~~text
SegmentModel
SegmentMemberModel
SavedQueryModel
~~~

The Django query executor compiles provider-neutral `QueryExpression` objects
into Django ORM predicates. It currently evaluates the aggregate families
persisted by this Django bridge:

~~~text
Contact
Organization
~~~

Lead, Opportunity, Tag and Custom Field query state is not silently simulated.
A query that requires persistence state not owned by the Django bridge fails
with an explicit adapter capability error.

Snapshot materialization and bulk Static membership use the same
`crm.segments` facade as Memory and SQLAlchemy/PostgreSQL. No Django ORM model
leaks into the domain API.


## Campaign persistence in the 1.2.0b2 development branch

**Status: implemented on PR #99; awaiting the complete CI/PostgreSQL release gate.**
Use the built-in optional Django app and migrate it to its latest revision.
The existing Campaign services and public Python facade are not Django-specific.

```bash
python manage.py migrate pycrmkit_crm
```

The Campaign schema is introduced by `0004_campaign_persistence` and has
six independent Django ORM tables (Campaign, direct members, materialized
Segment sources and members, attribution, communication linkage). A separate
additive migration, `0005_communication_record_store`, supplies a real
Django-owned record lookup/save boundary for `CommunicationRecord`. It does
not provide email delivery, intents, attempts, or the entire
`CommunicationRepository` protocol.

The existing Django `DjangoTransactionBridge` now includes the
`campaigns`, `campaign_audience`, `campaign_linkage`, and
`communications` (record-level only) properties. They share its
`transaction.atomic()` and deferred `on_commit` semantics. A consuming
application can use the standard `CRM(..., uow_factory=...)` facade:

```python
from typing import cast

from pycrmkit import CRM
from pycrmkit.config import CRMConfig
from pycrmkit.core.unit_of_work import UnitOfWork
from pycrmkit.integrations.django.transactions import DjangoTransactionBridge

def uow_factory() -> UnitOfWork:
    return cast(UnitOfWork, DjangoTransactionBridge())

crm = CRM(
    uow_factory=uow_factory,
    config=CRMConfig(audit_enabled=False),
    webhook_auto_delivery=False,
)

campaign = crm.campaigns.create(key="django-launch", name="Django Launch")
print(crm.campaigns.get(campaign.id).key)
```

The Django bridge remains partial for unrelated CRM bounded contexts.
The `cast` above only documents the known narrower application capability.
It does not add missing repositories to the bridge. When a
`CommunicationRecord` exists inside the Django store,
`crm.campaigns.link_communication(...)` validates and loads it using
the **same Django transaction** before saving a Campaign-owned link.

### Deployment and schema ownership

**Do not apply Django Campaign migrations to tables managed by SQLAlchemy/
Alembic in the same schema.** The Django Segment source has an internal
`BigAutoField` and captured members reference it with `source_id`;
SQLAlchemy b1 uses a composite source key and composite child foreign key.
Identical `pycrmkit_campaign*` table names do **not** imply physical
compatibility or shared migration ownership. Provision a separate schema or
database for each persistence adapter until a formally qualified cross-adapter
data migration exists.

`models.CASCADE` provides Django ORM deletion behavior; this does not by
itself promise a PostgreSQL `ON DELETE CASCADE` constraint. Database FK
integrity and ORM-level deletion are tested separately. Production claims
require the real PostgreSQL CI qualification, especially for concurrent
revisions, duplicate writes, transaction rollback and schema upgrades.
