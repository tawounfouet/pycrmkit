# FastAPI + PostgreSQL reference application

This example demonstrates the complete PyCRMKit 0.7 release-candidate path:

```text
FastAPI
  ↓
PyCRMKit routers + error handlers
  ↓
CRM facade
  ↓
SQLAlchemyUnitOfWork
  ↓
PostgreSQL
```

## 1. Install the required extras

From the repository root:

```bash
python -m pip install -e ".[fastapi,postgresql,migrations]"
python -m pip install uvicorn
```

## 2. Start PostgreSQL

```bash
docker compose -f examples/fastapi_postgres/compose.yaml up -d
```

## 3. Configure the database URL

```bash
export PYCRMKIT_DATABASE_URL='postgresql+psycopg://pycrmkit:pycrmkit@localhost:5432/pycrmkit'
```

## 4. Apply the packaged migrations

```bash
pycrmkit-migrate upgrade head
pycrmkit-migrate current
pycrmkit-migrate check
```

Migrations are intentionally explicit. The application factory never mutates
the database schema during startup.

## 5. Run the API

```bash
uvicorn examples.fastapi_postgres.app:create_app --factory --reload
```

Open:

```text
http://127.0.0.1:8000/docs
http://127.0.0.1:8000/openapi.json
http://127.0.0.1:8000/health
```

## 6. Exercise the CRM API

Create a contact:

```bash
curl -X POST http://127.0.0.1:8000/crm/contacts \
  -H 'Content-Type: application/json' \
  -H 'X-Actor-ID: example-user' \
  -H 'X-Correlation-ID: example-request-1' \
  -d '{"first_name":"Ada","last_name":"Lovelace","source":"example"}'
```

List contacts:

```bash
curl 'http://127.0.0.1:8000/crm/contacts?limit=50&offset=0'
```

## Runtime ownership

`create_app()` owns one SQLAlchemy Engine, one Session factory, one in-process
event bus and one base CRM facade. Each HTTP request receives a contextual CRM
view through `CRMDependency`; routers never receive SQLAlchemy Sessions or ORM
models directly.

## Deployment sequence

A production-style deployment should preserve this ordering:

```text
build/install artifact
      ↓
configure PYCRMKIT_DATABASE_URL
      ↓
pycrmkit-migrate upgrade head
      ↓
start ASGI application
```

The release-candidate E2E workflow in this repository executes this same
migration-first sequence against PostgreSQL 17 before calling the API.
