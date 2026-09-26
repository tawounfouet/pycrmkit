# PyCRMKit Database Migrations

PyCRMKit uses Alembic to version the SQLAlchemy/PostgreSQL persistence schema.

The database URL is supplied through `PYCRMKIT_DATABASE_URL`.

```bash
export PYCRMKIT_DATABASE_URL='postgresql+psycopg://user:password@localhost/pycrmkit'
alembic upgrade head
```

Migration revisions are immutable release artifacts. Do not edit an already
released revision; add a new revision instead.
