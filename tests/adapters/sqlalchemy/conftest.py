"""Shared SQLAlchemy adapter test fixtures."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from pycrmkit.storage.sqlalchemy import Base

DATABASE_ENV = "PYCRMKIT_SQLALCHEMY_TEST_URL"


@pytest.fixture
def session() -> Iterator[Session]:
    """Provide an isolated SQLAlchemy repository contract surface."""

    database_url = os.environ.get(DATABASE_ENV)
    engine = _engine(database_url)

    if database_url:
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    try:
        with Session(engine) as session:
            yield session
            session.rollback()
    finally:
        if database_url:
            Base.metadata.drop_all(engine)
        engine.dispose()


def _engine(database_url: str | None) -> Engine:
    if database_url:
        return create_engine(database_url, pool_pre_ping=True)
    return create_engine("sqlite+pysqlite:///:memory:")
