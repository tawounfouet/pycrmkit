# Compatibility

This page records the currently qualified compatibility baseline for PyCRMKit.

## Current stable line

```text
PyCRMKit 0.7.0 — FastAPI Integration Stable
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
dependency on FastAPI, Pydantic, SQLAlchemy or Django.

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
```

These ranges describe install compatibility. CI qualification uses
representative current versions within those ranges rather than every possible
combination.

## PostgreSQL

The production-reference persistence and FastAPI E2E paths are qualified
against:

```text
PostgreSQL 17
```

Other PostgreSQL versions are not claimed by this document unless separately
qualified.

## Persistence schema

The stable `0.7.0` FastAPI line builds on the stable `0.6.0` persistence
foundation and its packaged Alembic migration history. Applications should
always migrate through:

```bash
pycrmkit-migrate upgrade head
```

rather than creating production schemas with ORM metadata helpers.

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

## Pre-1.0 policy

PyCRMKit remains pre-`1.0.0`. Each stable milestone establishes compatibility
for its documented line, while broader V1 public API freeze remains planned for
`1.0.0`.
