"""PostgreSQL fixtures for Alembic migration qualification."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, create_engine

DATABASE_ENV = "PYCRMKIT_DATABASE_URL"


@pytest.fixture(scope="session")
def migration_engine() -> Iterator[Engine]:
    database_url = os.environ.get(DATABASE_ENV)
    if not database_url:
        pytest.skip(f"{DATABASE_ENV} is required for migration qualification")
    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture(autouse=True)
def clean_public_schema(migration_engine: Engine) -> Iterator[None]:
    _reset_schema(migration_engine)
    yield
    _reset_schema(migration_engine)


def _reset_schema(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.exec_driver_sql("DROP SCHEMA IF EXISTS public CASCADE")
        connection.exec_driver_sql("CREATE SCHEMA public")
