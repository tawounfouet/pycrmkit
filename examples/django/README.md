# PyCRMKit Django + PostgreSQL Reference Application

This example is the release-candidate reference path for PyCRMKit's optional
Django integration.

It deliberately assembles the pieces delivered across the `0.8.x` line:

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

The application does not make Django ORM models the domain model. HTTP requests
still enter through the public `CRM` facade.

## Install

From the repository root:

```bash
python -m pip install -e ".[django,drf,postgresql]"
```

## Start PostgreSQL

```bash
docker compose -f examples/django/compose.yaml up -d
export PYCRMKIT_DATABASE_URL="postgresql://pycrmkit:pycrmkit@localhost:5432/pycrmkit_django"
```

## Apply migrations

Django migrations are explicit deployment steps:

```bash
python examples/django/manage.py migrate
```

Importing PyCRMKit or starting the application never runs migrations
automatically.

## Validate the project

```bash
python examples/django/manage.py check
```

## Run the development server

```bash
python examples/django/manage.py runserver
```

Useful endpoints:

```text
GET  /health/
GET  /admin/login/
GET  /crm/contacts/
POST /crm/contacts/
GET  /crm/organizations/
POST /crm/organizations/
GET  /crm/relationships/
POST /crm/relationships/
```

## Reproduce the E2E smoke

The release gate intentionally uses two Python processes so the verification
does not depend on process-local state:

```bash
python examples/django/smoke.py seed --state /tmp/pycrmkit-django-state.json
python examples/django/smoke.py verify --state /tmp/pycrmkit-django-state.json
```

The seed phase creates Contact → Organization → Relationship through DRF. The
verify phase starts a fresh Django process, reloads those records from
PostgreSQL, executes an update and relationship end, verifies the admin
registration and confirms that `pycrmkit_crm.0001_initial` is applied.

## Current boundary

The Django persistence adapter currently implements Contacts, Organizations and
Relationships. Consequently this reference application limits its persistent
DRF surface to those aggregate families.

`DjangoTransactionBridge` is intentionally not documented as the complete
cross-domain PyCRMKit `UnitOfWork` until the remaining repository families
have Django implementations.
