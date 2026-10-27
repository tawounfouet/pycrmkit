"""Campaign 1.2 migration qualification from stable 0005 to packaged 0006."""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from pycrmkit.contacts import Contact, ContactId
from pycrmkit.storage.sqlalchemy import Base, SQLAlchemyUnitOfWork
from pycrmkit.storage.sqlalchemy.migrations.cli import migration_config

pytestmark = pytest.mark.postgresql

DATABASE_ENV = "PYCRMKIT_TEST_POSTGRES_URL"
NOW = datetime(2026, 9, 30, 17, tzinfo=UTC)


@pytest.fixture
def campaign_migration_engine() -> Iterator[Engine]:
    database_url = os.environ.get(DATABASE_ENV)
    if not database_url:
        pytest.skip(f"{DATABASE_ENV} is required for migration qualification")
    engine = create_engine(database_url, pool_pre_ping=True)
    _reset(engine)
    try:
        yield engine
    finally:
        _reset(engine)
        engine.dispose()


def _reset(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.exec_driver_sql("DROP SCHEMA IF EXISTS public CASCADE")
        connection.exec_driver_sql("CREATE SCHEMA public")


def _development_config(database_url: str) -> Config:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def _current_revision(engine: Engine) -> str | None:
    if "alembic_version" not in inspect(engine).get_table_names():
        return None
    with engine.connect() as connection:
        return connection.scalar(text("SELECT version_num FROM alembic_version"))


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


def test_stable_0005_data_survives_upgrade_downgrade_and_reupgrade(
    campaign_migration_engine: Engine,
) -> None:
    database_url = os.environ[DATABASE_ENV]
    config = _development_config(database_url)
    command.upgrade(config, "0005")
    assert _current_revision(campaign_migration_engine) == "0005"

    factory = sessionmaker(bind=campaign_migration_engine, expire_on_commit=False)
    fixture = Contact(
        id=ContactId(UUID("00000000-0000-4000-8000-00000000d001")),
        created_at=NOW,
        updated_at=NOW,
        display_name="Stable 1.1 Fixture",
        metadata={"release": "1.1.0"},
    )
    with SQLAlchemyUnitOfWork(factory) as uow:
        uow.contacts.save(fixture)
        uow.commit()

    command.upgrade(config, "0006")
    assert _current_revision(campaign_migration_engine) == "0006"
    assert _schema_diffs(campaign_migration_engine) == []
    with SQLAlchemyUnitOfWork(factory) as uow:
        assert uow.contacts.get(fixture.id) == fixture

    command.downgrade(config, "0005")
    assert _current_revision(campaign_migration_engine) == "0005"
    assert "pycrmkit_campaigns" not in inspect(
        campaign_migration_engine
    ).get_table_names()
    with SQLAlchemyUnitOfWork(factory) as uow:
        assert uow.contacts.get(fixture.id) == fixture

    command.upgrade(config, "head")
    assert _current_revision(campaign_migration_engine) == "0006"
    assert _schema_diffs(campaign_migration_engine) == []


def test_packaged_0006_chain_matches_development_migration_and_model_metadata(
    campaign_migration_engine: Engine,
) -> None:
    database_url = os.environ[DATABASE_ENV]
    config = migration_config(database_url)
    script = ScriptDirectory.from_config(config)

    assert script.get_current_head() == "0006"
    revision = script.get_revision("0006")
    assert revision is not None
    assert revision.down_revision == "0005"

    command.upgrade(config, "head")
    assert _current_revision(campaign_migration_engine) == "0006"
    assert _schema_diffs(campaign_migration_engine) == []

    development = Path("migrations/versions/0006_campaign_persistence.py").read_text(
        encoding="utf-8"
    )
    packaged = Path(
        "src/pycrmkit/storage/sqlalchemy/migrations/versions/"
        "0006_campaign_persistence.py"
    ).read_text(encoding="utf-8")
    assert packaged == development
