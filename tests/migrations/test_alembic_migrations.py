"""Qualification of the versioned PostgreSQL migration chain."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import Engine, inspect, text
from sqlalchemy.orm import sessionmaker

from pycrmkit.contacts import Contact, ContactId
from pycrmkit.storage.sqlalchemy import Base, SQLAlchemyUnitOfWork

pytestmark = pytest.mark.postgresql

NOW = datetime(2026, 9, 26, 15, 0, tzinfo=UTC)


def _config() -> Config:
    return Config("alembic.ini")


def _current_revision(engine: Engine) -> str | None:
    inspector = inspect(engine)
    if "alembic_version" not in inspector.get_table_names():
        return None
    with engine.connect() as connection:
        return connection.scalar(text("SELECT version_num FROM alembic_version"))


def _application_tables(engine: Engine) -> set[str]:
    return {
        name
        for name in inspect(engine).get_table_names()
        if name != "alembic_version"
    }


def _schema_diffs(engine: Engine) -> list[object]:
    with engine.connect() as connection:
        context = MigrationContext.configure(
            connection,
            opts={
                "compare_type": True,
                "compare_server_default": True,
            },
        )
        return list(compare_metadata(context, Base.metadata))


def test_upgrade_empty_database_to_head_matches_metadata(
    migration_engine: Engine,
) -> None:
    command.upgrade(_config(), "head")

    assert _current_revision(migration_engine) == "0001"
    assert _application_tables(migration_engine) == set(Base.metadata.tables)
    assert _schema_diffs(migration_engine) == []


def test_baseline_downgrade_to_base_is_destructive_and_reversible(
    migration_engine: Engine,
) -> None:
    config = _config()
    command.upgrade(config, "head")
    command.downgrade(config, "base")

    assert _application_tables(migration_engine) == set()
    assert _current_revision(migration_engine) is None

    command.upgrade(config, "head")
    assert _current_revision(migration_engine) == "0001"
    assert _schema_diffs(migration_engine) == []


def test_existing_060b2_schema_can_be_verified_and_stamped_without_data_loss(
    migration_engine: Engine,
) -> None:
    Base.metadata.create_all(migration_engine)
    factory = sessionmaker(bind=migration_engine, expire_on_commit=False)
    contact = Contact(
        id=ContactId(UUID("00000000-0000-4000-8000-000000009931")),
        created_at=NOW,
        updated_at=NOW,
        display_name="Migration Fixture",
        metadata={"source": "0.6.0b2"},
    )

    with SQLAlchemyUnitOfWork(factory) as uow:
        uow.contacts.save(contact)
        uow.commit()

    assert _schema_diffs(migration_engine) == []

    command.stamp(_config(), "0001")
    assert _current_revision(migration_engine) == "0001"

    command.upgrade(_config(), "head")

    with SQLAlchemyUnitOfWork(factory) as uow:
        assert uow.contacts.get(contact.id) == contact


def test_alembic_head_has_no_model_drift(
    migration_engine: Engine,
) -> None:
    command.upgrade(_config(), "head")
    assert _schema_diffs(migration_engine) == []


def test_migration_version_table_tracks_head(
    migration_engine: Engine,
) -> None:
    command.upgrade(_config(), "head")

    with migration_engine.connect() as connection:
        rows = connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalars().all()

    assert rows == ["0001"]
