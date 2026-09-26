"""Live PostgreSQL fixtures for persistence qualification."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from pycrmkit.storage.sqlalchemy import Base

DATABASE_ENV = "PYCRMKIT_TEST_POSTGRES_URL"


@pytest.fixture(scope="session")
def postgres_engine() -> Iterator[Engine]:
    database_url = os.environ.get(DATABASE_ENV)
    if not database_url:
        pytest.skip(f"{DATABASE_ENV} is required for PostgreSQL qualification")

    engine = create_engine(database_url, pool_pre_ping=True)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def postgres_session_factory(
    postgres_engine: Engine,
) -> Iterator[sessionmaker[Session]]:
    factory = sessionmaker(bind=postgres_engine, expire_on_commit=False)
    _truncate(postgres_engine)
    try:
        yield factory
    finally:
        _truncate(postgres_engine)


def _truncate(engine: Engine) -> None:
    tables = ", ".join(
        f'"{table.name}"'
        for table in reversed(Base.metadata.sorted_tables)
    )
    if not tables:
        return
    with engine.begin() as connection:
        connection.exec_driver_sql(
            f"TRUNCATE TABLE {tables} RESTART IDENTITY CASCADE"
        )
