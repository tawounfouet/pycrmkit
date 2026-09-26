# Django Integration

PyCRMKit's Django integration is optional. The domain layer remains
framework-agnostic.

Install the alpha bridge with:

```bash
pip install "pycrmkit[django]"
```

## 0.8.0a1 scope

The initial application bridge provides:

```text
src/pycrmkit/integrations/django/
├── __init__.py
├── apps.py
├── models.py
├── repositories.py
└── typecheck_settings.py
```

Public runtime pieces are the application config, ORM persistence models and
repository adapters. `typecheck_settings.py` exists only to let
`django-stubs` understand the optional app under strict mypy.

## Application registration

Add:

```python
INSTALLED_APPS = [
    # application apps...
    "pycrmkit.integrations.django.apps.PyCRMKitDjangoConfig",
]
```

The application uses the non-generic label:

```text
pycrmkit_crm
```

to reduce collision risk inside larger Django projects.

## Dependency direction

The bridge preserves the persistence architecture:

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

Never:

```text
Django model
      ↓
becomes PyCRMKit domain entity
```

The ORM classes are adapter representations only.

## Initial models

`0.8.0a1` introduces persistence representations for the first core CRM
aggregate set:

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

The initial table names follow the existing `pycrmkit_*` naming convention.
This does not create a general promise that every SQLAlchemy and Django physical
schema will always be interchangeable without migration.

## Initial repositories

The alpha provides:

```python
from pycrmkit.integrations.django.repositories import (
    DjangoContactRepository,
    DjangoOrganizationRepository,
    DjangoRelationshipRepository,
)
```

These implement the existing backend-neutral contracts:

```text
ContactRepository
OrganizationRepository
RelationshipRepository
```

Observable semantics remain defined by PyCRMKit, not by Django QuerySet
behavior.

## Contract qualification

The exact reusable repository suites already used for Memory and SQLAlchemy are
replayed against Django:

```text
ContactRepositoryContract
OrganizationRepositoryContract
RelationshipRepositoryContract
```

They verify, among other behavior:

```text
get/find missing semantics
save replacement semantics
deterministic ordering
exact offset pagination
normalized email/domain filtering
archive visibility
relationship filtering
historical relationship activity
```

The alpha contract tests use an isolated in-memory SQLite database and create
the temporary schema through Django's schema editor. That mechanism is test
infrastructure only.

## Migrations are intentionally deferred

`0.8.0a1` does **not** ship the Django migration lifecycle yet.

Production applications should not treat schema-editor bootstrap as an
application setup API. The next milestone, `0.8.0b1`, owns:

```text
Django migrations
transaction / Unit-of-Work bridge
admin helpers
```

Migration execution will remain explicit; importing PyCRMKit must never mutate a
production database schema.

## Optional dependency boundary

The normal core installation remains:

```bash
pip install pycrmkit
```

and must not import Django transitively.

Django-specific imports require:

```bash
pip install "pycrmkit[django]"
```

The integration package raises an actionable error if Django itself is missing.

## Typing

Development uses `django-stubs` and the mypy Django plugin so strict typing can
understand field descriptors and reverse relations. This typing dependency is
not a runtime requirement of `pycrmkit[django]`.

## Compatibility target

For this alpha:

```text
Django >=5.2,<6
Python 3.11–3.13
```

Django 5.2 LTS is used so the adapter can preserve PyCRMKit's existing Python
3.11–3.13 matrix.

## Next milestone

The next delivery is **`0.8.0b1 — Django Migrations & Admin`**.
