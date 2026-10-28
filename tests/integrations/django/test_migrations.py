"""Django migration qualification for the PyCRMKit adapter."""

from __future__ import annotations

from django.core.management import call_command
from django.db import connection
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.recorder import MigrationRecorder
from django.utils import timezone

from pycrmkit.integrations.django.models import ContactModel, SegmentModel

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
    "pycrmkit_segments",
    "pycrmkit_segment_members",
    "pycrmkit_saved_queries",
    "pycrmkit_campaigns",
    "pycrmkit_campaign_members",
    "pycrmkit_campaign_segment_sources",
    "pycrmkit_campaign_segment_members",
    "pycrmkit_campaign_attributions",
    "pycrmkit_campaign_communication_links",
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
    assert ("pycrmkit_crm", "0003_segmentation") in loader.graph.nodes
    assert ("pycrmkit_crm", "0004_campaign_persistence") in loader.graph.nodes
    assert (
        "pycrmkit_crm",
        "0004_campaign_persistence",
    ) in MigrationRecorder(connection).applied_migrations()
    assert (
        "pycrmkit_crm",
        "0003_segmentation",
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


def test_campaign_fk_and_unique_constraints_exist_in_database() -> None:
    with connection.cursor() as cursor:
        sources = connection.introspection.get_constraints(
            cursor, "pycrmkit_campaign_segment_sources"
        )
        captures = connection.introspection.get_constraints(
            cursor, "pycrmkit_campaign_segment_members"
        )
        attributes = connection.introspection.get_constraints(
            cursor, "pycrmkit_campaign_attributions"
        )
        links = connection.introspection.get_constraints(
            cursor, "pycrmkit_campaign_communication_links"
        )

    assert sources["uq_dj_campaign_source"]["unique"]
    assert captures["uq_dj_campaign_snapshot"]["unique"]
    assert attributes["uq_dj_campaign_attribution"]["unique"]
    assert links["uq_dj_campaign_link"]["unique"]
    assert any(
        constraint.get("foreign_key")
        == ("pycrmkit_campaign_segment_sources", "id")
        for constraint in captures.values()
    )


def test_0003_to_0004_to_0003_to_0004_preserves_legacy_rows() -> None:
    now = timezone.now()
    contact = ContactModel.objects.create(
        id="11111111-1111-4111-8111-111111111111",
        status="active",
        created_at=now,
        updated_at=now,
    )
    segment = SegmentModel.objects.create(
        id="22222222-2222-4222-8222-222222222222",
        key="campaign-schema-qualification",
        name="Legacy Segment",
        entity_kind="contact",
        mode="static",
        status="active",
        created_at=now,
        updated_at=now,
    )
    campaign_tables = {table for table in TABLES if "campaign" in table}
    try:
        call_command(
            "migrate",
            "pycrmkit_crm",
            "0003_segmentation",
            verbosity=0,
            interactive=False,
        )
        assert campaign_tables.isdisjoint(
            set(connection.introspection.table_names())
        )
        assert ContactModel.objects.filter(pk=contact.pk).exists()
        assert SegmentModel.objects.filter(pk=segment.pk).exists()

        call_command(
            "migrate",
            "pycrmkit_crm",
            "0004_campaign_persistence",
            verbosity=0,
            interactive=False,
        )
        assert campaign_tables <= set(connection.introspection.table_names())
        assert ContactModel.objects.filter(pk=contact.pk).exists()
        assert SegmentModel.objects.filter(pk=segment.pk).exists()
    finally:
        call_command(
            "migrate",
            "pycrmkit_crm",
            verbosity=0,
            interactive=False,
        )
        ContactModel.objects.filter(pk=contact.pk).delete()
        SegmentModel.objects.filter(pk=segment.pk).delete()
