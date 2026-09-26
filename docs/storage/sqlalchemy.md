# SQLAlchemy Persistence

PyCRMKit keeps SQLAlchemy behind the persistence boundary. Domain entities,
services, repository contracts and the public CRM facade remain ORM-neutral.

The `0.6.0b1` milestone adds the SQLAlchemy Unit of Work on top of the
repository adapters delivered in `0.6.0a2`. `0.6.0b2` qualifies PostgreSQL
as the production-reference backend.

## Dependency direction

```text
Domain
  ↓
Repository contracts
  ↓
Unit of Work
  ↓
SQLAlchemy repository adapters
  ↓
SQLAlchemy Session
  ↓
Database
```

Domain objects are never ORM models. Repository methods return PyCRMKit domain
entities and value objects, not SQLAlchemy model instances or query objects.

## Transaction ownership

Every repository exposed by one `SQLAlchemyUnitOfWork` shares the same
`Session`.

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from pycrmkit.storage.sqlalchemy import Base, SQLAlchemyUnitOfWork

engine = create_engine("sqlite+pysqlite:///crm.db")

# Appropriate for local experimentation only. Production schema evolution is
# introduced later through Alembic.
Base.metadata.create_all(engine)

SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

with SQLAlchemyUnitOfWork(SessionLocal) as uow:
    # all repositories below share the same SQLAlchemy Session
    contact = uow.contacts.get(contact_id)
    organization = uow.organizations.get(organization_id)

    # repository writes do not commit independently
    uow.contacts.save(contact)
    uow.organizations.save(organization)

    uow.commit()
```

The transaction rules are explicit:

- entering the Unit of Work opens one logical transaction scope;
- repository adapters never call `commit()`;
- `uow.commit()` persists all participating repositories together;
- leaving the context without commit rolls back;
- exceptions roll back uncommitted state;
- `uow.rollback()` discards pending writes and keeps the UoW usable;
- a second commit on the same transaction is rejected;
- staged domain events are published only after the database commit succeeds.

## Post-commit events

Domain events follow the same semantics as the Memory adapter:

```text
domain mutation
  ↓
repository writes
  ↓
uow.add_event(...)
  ↓
database COMMIT
  ↓
event publisher
```

If a synchronous subscriber fails after commit, the database transaction is
already durable and is not rolled back. A subscriber may open a fresh Unit of
Work and observe the committed state.

## Transactional qualification

`0.6.0b1` qualifies the flows explicitly required by the implementation plan:

- Lead conversion across Lead + Opportunity persistence;
- Contact merge foundation through coordinated Contact/related-state writes;
- Pipeline transitions with transactional Audit history;
- bulk-write commit/rollback foundations.

The "contact merge foundation" is intentionally a transaction capability, not a
new public merge API. The dedicated data merge feature remains part of the later
Data Operations roadmap.

## PostgreSQL production reference

Install the PostgreSQL adapter dependencies with:

```bash
pip install "pycrmkit[postgresql]"
```

A PostgreSQL session factory can be wired with standard SQLAlchemy primitives:

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from pycrmkit.storage.sqlalchemy import SQLAlchemyUnitOfWork

engine = create_engine(
    "postgresql+psycopg://crm:secret@localhost:5432/crm",
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

with SQLAlchemyUnitOfWork(SessionLocal) as uow:
    contact = uow.contacts.get(contact_id)
    contact.source = "postgresql"
    uow.contacts.save(contact)
    uow.commit()
```

PostgreSQL is now exercised in CI against a live PostgreSQL 17 service.

The qualification validates:

- generated tables, named constraints and indexes;
- foreign-key enforcement;
- Unicode and timezone-aware datetime round trips;
- Decimal precision used by Sales;
- JSON and Custom Field persistence;
- transaction commit/rollback behavior;
- concurrent uniqueness races across independent Sessions.

### Concurrency and normalized uniqueness

Application-level duplicate checks are useful for early feedback, but they are
not sufficient under concurrency. Two transactions may both observe "missing"
before either commits.

For invariants that must survive such races, `0.6.0b2` adds corresponding
database constraints. In particular:

- Tag `normalized_name` is persisted and unique;
- one Tag may be assigned to a given `(entity_kind, entity_id)` at most once.

A competing commit that loses the race is translated from PostgreSQL SQLSTATE
`23505` into PyCRMKit `DuplicateError`.

### Backend error boundary

The SQLAlchemy Unit of Work translates commit-time SQLAlchemy/driver errors into
the public PyCRMKit persistence hierarchy. PostgreSQL diagnostic metadata is
restricted to safe fields such as SQLSTATE and constraint/table/column names;
SQL text and bound parameter values are not exposed.

## Schema lifecycle

`0.6.0b3` introduces Alembic as the production schema-evolution mechanism.

Install migration tooling with:

```bash
pip install "pycrmkit[migrations]"
```

For a fresh PostgreSQL database:

```bash
export PYCRMKIT_DATABASE_URL='postgresql+psycopg://crm:secret@localhost:5432/crm'
alembic upgrade head
alembic current
alembic check
```

The current head is revision `0002 — align repository reference semantics`.

`Base.metadata.create_all(...)` remains useful for tests and local
experimentation, but it is no longer the production schema lifecycle.

### Existing 0.6.0b2 databases

A database created under `0.6.0b2` has the pre-Alembic schema represented by
revision `0001`, but no Alembic version table.

After verifying that the database still matches the `0.6.0b2`/`0001`
schema, adopt the migration history and then apply the RC migration:

```bash
alembic stamp 0001
alembic upgrade head
alembic current
alembic check
```

Stamping itself does not recreate tables or remove CRM data. The subsequent
`0001 → 0002` upgrade removes only non-contractual cross-aggregate foreign
key constraints.

### Existing 0.6.0b3 databases

A `0.6.0b3` database is already tracked at revision `0001`. Upgrade it with:

```bash
alembic upgrade head
alembic current
alembic check
```

Revision `0002` preserves the reference columns and indexes while removing
database-only existence requirements for:

- Lead → Contact / Organization references;
- Opportunity → Contact / Organization references;
- Webhook Delivery → Subscription references.

Ownership foreign keys remain enforced.

### Downgrade policy

`alembic downgrade base` is implemented and tested for the baseline, but it is
destructive because it drops the persistence tables.

Use that downgrade only for disposable environments or explicit destructive
rollback. Production recovery should normally use application rollback plus a
forward corrective migration unless a future revision documents a data-safe
downgrade.

Released migration revisions are immutable. Persistence-model changes require a
new reviewed Alembic revision.

The `0.6.0rc1` qualification additionally executes the reusable repository
contract suite against PostgreSQL and verifies the packaged migration chain from
an installed wheel.

The next milestone is **`0.6.0 — Persistence Foundation Stable`**.
