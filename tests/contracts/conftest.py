"""Shared fixtures for backend-neutral repository contracts."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pycrmkit.storage.sqlalchemy import Base


@pytest.fixture
def session(tmp_path: Path) -> Iterator[Session]:
    engine = create_engine(
        f"sqlite+pysqlite:///{tmp_path / 'contracts.sqlite'}",
    )
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as session:
            yield session
            session.rollback()
    finally:
        engine.dispose()
