# SQLAlchemy Persistence

PyCRMKit keeps SQLAlchemy behind the persistence boundary. Domain entities,
services, repository contracts and the public CRM facade remain ORM-neutral.

The `0.6.0b1` milestone adds the SQLAlchemy Unit of Work on top of the
repository adapters delivered in `0.6.0a2`.

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

## Current database scope

SQLite is used in `0.6.0b1` for deterministic adapter/UoW qualification.

The next milestone, `0.6.0b2 — PostgreSQL`, adds the production reference
backend, database constraints/index qualification, transaction tests and
concurrency tests. Alembic migrations follow in `0.6.0b3`.
