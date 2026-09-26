"""Shared SQLAlchemy adapter test fixtures."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pycrmkit.storage.sqlalchemy import Base


@pytest.fixture
def session() -> Iterator[Session]:
    """Provide an isolated SQLAlchemy transaction surface for each repository test."""
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
        session.rollback()
    engine.dispose()
