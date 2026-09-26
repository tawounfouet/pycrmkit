# Compatibility

This page records the currently qualified compatibility baseline for PyCRMKit.

## Current stable line

```text
PyCRMKit 0.8.0 — Django Integration Stable
```

## Python

The current CI matrix qualifies:

```text
Python 3.11
Python 3.12
Python 3.13
```

## Core installation

The core package remains framework-agnostic and has no mandatory runtime
dependency on FastAPI, Pydantic, SQLAlchemy, Django or Django REST Framework.

```bash
pip install pycrmkit
```

must remain sufficient for `import pycrmkit` and in-memory CRM usage.

## Stable optional integration ranges

The package metadata currently declares:

```text
FastAPI        >=0.141,<1
Pydantic       >=2.13,<3
SQLAlchemy     >=2.0,<3
psycopg        >=3.2,<4
Alembic        >=1.16,<2
Django         >=5.2,<6
DRF            >=3.18,<4
```

These ranges describe install compatibility. CI qualification uses
representative current versions within those ranges rather than every possible
combination.

## Django stable qualification

`0.8.0` promotes the qualified Django/DRF release candidate to the stable
`0.8.x` integration line without adding new functional scope.

It is currently qualified with:

```text
Django 5.2 LTS
Python 3.11
Python 3.12
Python 3.13
Django REST Framework 3.18.x
SQLite in-memory repository, migration, admin, transaction and DRF qualification
PostgreSQL 17 reference application E2E
clean installed-wheel Django/PostgreSQL/DRF E2E
```

The stable line qualifies application loading,
Contact/Organization/Relationship repository semantics, packaged migration
`0001_initial`, migration/model drift checking, admin registration, explicit
transaction semantics, the optional facade-backed DRF transport and a real
PostgreSQL-backed reference application.

The `django` extra is also explicitly qualified without DRF installed. The
reference E2E is executed twice: from the source checkout and from a clean wheel
after resetting the PostgreSQL schema.

It does **not** claim full cross-domain Django UnitOfWork/DRF coverage; the
Django persistence adapter remains bounded to Contacts, Organizations and
Relationships in the `0.8.x` line.

## PostgreSQL

The production-reference persistence, FastAPI E2E and stable Django reference
paths are qualified against:

```text
PostgreSQL 17
```

Other PostgreSQL versions are not claimed by this document unless separately
qualified.

## Persistence schema

The stable `0.8.0` line keeps the SQLAlchemy/Alembic and Django migration
histories explicit and separate.

SQLAlchemy-backed applications migrate through:

```bash
pycrmkit-migrate upgrade head
```

Django-backed applications migrate the Django adapter through:

```bash
python manage.py migrate pycrmkit_crm
```

Applications should not create production schemas from ORM metadata helpers or
run migrations implicitly at import/startup time.

## FastAPI compatibility contract

Within `0.7.x`, backward compatibility covers the documented public
integration surface:

```text
request/response schemas
router paths and HTTP methods
pagination shape
ErrorResponse shape
documented error/status mapping
request context headers
OpenAPI generation
create_crm_router(...)
install_error_handlers(...)
```

Internal module layout and undocumented implementation details are not public
compatibility promises.

## Django compatibility contract

Within `0.8.x`, backward compatibility covers the documented stable Django
integration surface:

```text
PyCRMKitDjangoConfig and the pycrmkit_crm app label
Contact / Organization / Relationship Django repositories
packaged Django migration history beginning at 0001_initial
DjangoTransactionBridge explicit commit/rollback semantics
post-commit event publication semantics
Django admin registrations for the three persisted aggregate families
create_drf_router()
DRF serializer/update semantics
DRF pagination shape
DRF domain/request error mapping
X-Actor-ID / X-Correlation-ID propagation
PYCRMKIT_CRM_FACTORY application-owned wiring
```

The stable Django adapter is intentionally bounded to Contacts, Organizations
and Relationships. `0.8.0` does not claim a complete cross-domain Django
`UnitOfWork` or a persistent Django implementation for every PyCRMKit module.

## Pre-1.0 policy

PyCRMKit remains pre-`1.0.0`. Each stable milestone establishes compatibility
for its documented line, while broader V1 public API freeze remains planned for
`1.0.0`.
