"""Django migration qualification for the PyCRMKit adapter."""

from __future__ import annotations

from django.core.management import call_command
from django.db import connection
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.recorder import MigrationRecorder

TABLES = {
    "pycrmkit_contacts",
    "pycrmkit_contact_emails",
    "pycrmkit_contact_phones",
    "pycrmkit_contact_addresses",
    "pycrmkit_organizations",
    "pycrmkit_organization_domains",
    "pycrmkit_organization_addresses",
    "pycrmkit_relationships",
    "pycrmkit_external_identities",
}


def test_initial_migration_is_discoverable_and_applied() -> None:
    loader = MigrationLoader(connection)
    assert ("pycrmkit_crm", "0001_initial") in loader.graph.nodes
    assert ("pycrmkit_crm", "0002_external_identity") in loader.graph.nodes
    assert (
        "pycrmkit_crm",
        "0001_initial",
    ) in MigrationRecorder(connection).applied_migrations()
    assert (
        "pycrmkit_crm",
        "0002_external_identity",
    ) in MigrationRecorder(connection).applied_migrations()


def test_models_and_migration_state_are_in_sync() -> None:
    call_command(
        "makemigrations",
        "pycrmkit_crm",
        check=True,
        dry_run=True,
        verbosity=0,
    )


def test_empty_database_to_latest_migration_path() -> None:
    try:
        call_command(
            "migrate",
            "pycrmkit_crm",
            "zero",
            verbosity=0,
            interactive=False,
        )
        tables_after_zero = set(connection.introspection.table_names())
        assert TABLES.isdisjoint(tables_after_zero)

        call_command(
            "migrate",
            "pycrmkit_crm",
            verbosity=0,
            interactive=False,
        )
        tables_after_latest = set(connection.introspection.table_names())
        assert TABLES <= tables_after_latest
    finally:
        call_command(
            "migrate",
            "pycrmkit_crm",
            verbosity=0,
            interactive=False,
        )
