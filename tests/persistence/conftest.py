"""Release-candidate PostgreSQL fixtures built from Alembic history."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

DATABASE_ENV = "PYCRMKIT_TEST_POSTGRES_URL"


@pytest.fixture
def persistence_session_factory() -> Iterator[sessionmaker[Session]]:
    database_url = os.environ.get(DATABASE_ENV)
    if not database_url:
        pytest.skip(f"{DATABASE_ENV} is required for persistence RC qualification")

    engine = create_engine(database_url, pool_pre_ping=True)
    with engine.begin() as connection:
        connection.exec_driver_sql("DROP SCHEMA IF EXISTS public CASCADE")
        connection.exec_driver_sql("CREATE SCHEMA public")

    previous = os.environ.get("PYCRMKIT_DATABASE_URL")
    os.environ["PYCRMKIT_DATABASE_URL"] = database_url
    command.upgrade(Config("alembic.ini"), "head")

    factory = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        if previous is None:
            os.environ.pop("PYCRMKIT_DATABASE_URL", None)
        else:
            os.environ["PYCRMKIT_DATABASE_URL"] = previous
        engine.dispose()
