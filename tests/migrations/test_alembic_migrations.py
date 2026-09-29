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

    assert _current_revision(migration_engine) == "0004"
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
    assert _current_revision(migration_engine) == "0004"
    assert _schema_diffs(migration_engine) == []


def test_previous_060b3_schema_upgrades_to_head_without_data_loss(
    migration_engine: Engine,
) -> None:
    config = _config()
    command.upgrade(config, "0001")
    assert _current_revision(migration_engine) == "0001"

    factory = sessionmaker(bind=migration_engine, expire_on_commit=False)
    contact = Contact(
        id=ContactId(UUID("00000000-0000-4000-8000-000000009931")),
        created_at=NOW,
        updated_at=NOW,
        display_name="Migration Fixture",
        metadata={"source": "0.6.0b3"},
    )

    with SQLAlchemyUnitOfWork(factory) as uow:
        uow.contacts.save(contact)
        uow.commit()

    command.upgrade(config, "head")
    assert _current_revision(migration_engine) == "0004"
    assert _schema_diffs(migration_engine) == []

    with SQLAlchemyUnitOfWork(factory) as uow:
        assert uow.contacts.get(contact.id) == contact


def test_task_type_migration_backfills_existing_tasks_as_general(
    migration_engine: Engine,
) -> None:
    config = _config()
    command.upgrade(config, "0003")

    task_id = "00000000-0000-4000-8000-000000009941"
    with migration_engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO pycrmkit_tasks (
                    id, title, status, priority, description, due_at,
                    owner_id, assignee_id, source, external_id, metadata,
                    started_at, completed_at, cancelled_at, created_at, updated_at
                ) VALUES (
                    :id, :title, 'open', 20, NULL, NULL,
                    NULL, NULL, NULL, NULL, CAST('{}' AS JSON),
                    NULL, NULL, NULL, :created_at, :updated_at
                )
                """
            ),
            {
                "id": task_id,
                "title": "Legacy task",
                "created_at": NOW,
                "updated_at": NOW,
            },
        )

    command.upgrade(config, "head")

    with migration_engine.connect() as connection:
        task_type = connection.scalar(
            text(
                "SELECT task_type FROM pycrmkit_tasks WHERE id = :id"
            ),
            {"id": task_id},
        )

    assert task_type == "general"


def test_head_removes_non_contractual_cross_aggregate_foreign_keys(
    migration_engine: Engine,
) -> None:
    config = _config()
    command.upgrade(config, "0001")

    expected = {
        ("pycrmkit_leads", ("contact_id",), "pycrmkit_contacts"),
        ("pycrmkit_leads", ("organization_id",), "pycrmkit_organizations"),
        ("pycrmkit_opportunities", ("contact_id",), "pycrmkit_contacts"),
        (
            "pycrmkit_opportunities",
            ("organization_id",),
            "pycrmkit_organizations",
        ),
        (
            "pycrmkit_webhook_deliveries",
            ("subscription_id",),
            "pycrmkit_webhook_subscriptions",
        ),
    }

    def cross_aggregate_foreign_keys() -> set[tuple[str, tuple[str, ...], str]]:
        return {
            (
                table,
                tuple(item["constrained_columns"]),
                str(item["referred_table"]),
            )
            for table in (
                "pycrmkit_leads",
                "pycrmkit_opportunities",
                "pycrmkit_webhook_deliveries",
            )
            for item in inspect(migration_engine).get_foreign_keys(table)
        }

    assert expected <= cross_aggregate_foreign_keys()

    command.upgrade(config, "head")

    assert expected.isdisjoint(cross_aggregate_foreign_keys())


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

    assert rows == ["0004"]
