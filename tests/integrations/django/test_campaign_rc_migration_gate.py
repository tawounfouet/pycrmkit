"""LOT-31-010 - Django Campaign PostgreSQL migration and transaction gate.

The isolated Django fixture migrates its own database; it must not reuse an
Alembic-managed schema or the Django production reference app database.
"""
from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Barrier
from urllib.parse import urlsplit
from uuid import UUID

import pytest
from django.core.management import call_command
from django.db import IntegrityError, connection, connections, transaction
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.recorder import MigrationRecorder

from pycrmkit.campaigns import (
    Campaign,
    CampaignAttributionReference,
    CampaignId,
    CampaignMember,
    CampaignSegmentSource,
)
from pycrmkit.contacts import ContactId
from pycrmkit.core.events import EventId, EventType
from pycrmkit.core.references import EntityReference
from pycrmkit.events import DomainEvent, InProcessEventBus
from pycrmkit.exceptions import DuplicateError
from pycrmkit.integrations.django.campaign_audience import DjangoCampaignAudienceRepository
from pycrmkit.integrations.django.campaign_linkage import DjangoCampaignLinkageRepository
from pycrmkit.integrations.django.models import (
    CampaignAttributionModel,
    CampaignMemberModel,
    CampaignModel,
    CampaignSegmentMemberModel,
    CampaignSegmentSourceModel,
    CommunicationRecordModel,
    ContactModel,
)
from pycrmkit.integrations.django.transactions import DjangoTransactionBridge
from pycrmkit.segments import SegmentId

NOW = datetime(2026, 10, 29, 15, 0, tzinfo=UTC)
CAMPAIGN_NUMBER = 31010
CONTACT_NUMBER = 31011
SEGMENT_NUMBER = 31012


def _campaign(number: int = CAMPAIGN_NUMBER) -> Campaign:
    return Campaign(
        id=CampaignId(UUID(int=number)),
        created_at=NOW,
        updated_at=NOW,
        key=f"rc-django-migration-{number}",
        name="RC Django persistence",
        metadata={"qualification": {"version": "rc1"}},
    )


def _reference(number: int = CONTACT_NUMBER) -> EntityReference:
    return EntityReference("contact", ContactId(UUID(int=number)))


def _event(number: int = 31014) -> DomainEvent:
    return DomainEvent(
        id=EventId(UUID(int=number)),
        type=EventType("campaign.member_added"),
        schema_version=1,
        aggregate_type="campaign",
        aggregate_id=str(CampaignId(UUID(int=CAMPAIGN_NUMBER))),
        occurred_at=NOW,
    )


def _source(campaign: Campaign, number: int = SEGMENT_NUMBER) -> CampaignSegmentSource:
    return CampaignSegmentSource(
        campaign_id=campaign.id,
        segment_id=SegmentId(UUID(int=number)),
        segment_revision=1,
        entity_kind="contact",
        attached_at=NOW,
        captured_at=NOW,
        member_count=1,
    )


def test_django_migration_chain_and_model_drift_are_explicit() -> None:
    loader = MigrationLoader(connection)
    graph = loader.graph
    assert ("pycrmkit_crm", "0004_campaign_persistence") in graph.nodes
    assert ("pycrmkit_crm", "0005_communication_record_store") in graph.nodes
    assert ("pycrmkit_crm", "0004_campaign_persistence") in graph.forwards_plan(
        ("pycrmkit_crm", "0005_communication_record_store")
    )
    applied = MigrationRecorder(connection).applied_migrations()
    assert ("pycrmkit_crm", "0004_campaign_persistence") in applied
    assert ("pycrmkit_crm", "0005_communication_record_store") in applied
    assert not (set(connection.introspection.table_names()) & {"alembic_version"})
    call_command("makemigrations", "pycrmkit_crm", check=True, dry_run=True, verbosity=0)


def test_django_and_alembic_use_separate_physical_databases_in_pg_ci() -> None:
    django_url = os.environ.get("PYCRMKIT_DJANGO_TEST_DATABASE_URL")
    other_url = os.environ.get("PYCRMKIT_DATABASE_URL")
    if connection.vendor != "postgresql" or not django_url or not other_url:
        pytest.skip("dedicated PostgreSQL CI ownership proof")
    django_name = urlsplit(django_url).path.strip("/")
    other_name = urlsplit(other_url).path.strip("/")
    assert django_name and other_name and django_name != other_name
    assert "alembic_version" not in connection.introspection.table_names()


def test_0005_reverse_and_forward_preserve_0004_campaign_data() -> None:
    """0005 may be reversed on a dedicated test DB without dropping 0004."""
    campaign = _campaign(31015)
    contact_id = str(UUID(int=31016))
    ContactModel.objects.create(
        id=contact_id, status="active", created_at=NOW, updated_at=NOW,
    )
    with DjangoTransactionBridge() as bridge:
        bridge.campaigns.save(campaign)
        bridge.commit()

    try:
        call_command(
            "migrate", "pycrmkit_crm", "0004_campaign_persistence",
            verbosity=0, interactive=False,
        )
        tables = set(connection.introspection.table_names())
        assert "pycrmkit_communication_records" not in tables
        assert "pycrmkit_campaigns" in tables
        assert CampaignModel.objects.filter(pk=str(campaign.id)).exists()
        assert ContactModel.objects.filter(pk=contact_id).exists()
        applied = MigrationRecorder(connection).applied_migrations()
        assert ("pycrmkit_crm", "0004_campaign_persistence") in applied
        assert ("pycrmkit_crm", "0005_communication_record_store") not in applied
    finally:
        call_command(
            "migrate", "pycrmkit_crm",
            verbosity=0, interactive=False,
        )

    assert "pycrmkit_communication_records" in connection.introspection.table_names()
    assert CampaignModel.objects.get(pk=str(campaign.id)).name == campaign.name
    assert ContactModel.objects.filter(pk=contact_id).exists()
    assert ("pycrmkit_crm", "0005_communication_record_store") in (
        MigrationRecorder(connection).applied_migrations()
    )


def test_campaign_multi_repository_injected_failure_rolls_back_all_rows_and_events() -> None:
    campaign = _campaign(31017)
    member = CampaignMember(campaign.id, _reference(), NOW)
    source = _source(campaign, 31018)
    attribution = CampaignAttributionReference(
        campaign_id=campaign.id,
        target=_reference(),
        source="organic",
        external_ref=None,
        recorded_at=NOW,
    )
    bus = InProcessEventBus()
    published: list[DomainEvent] = []
    bus.subscribe("campaign.member_added", published.append)

    with pytest.raises(RuntimeError, match="injected Django failure"):
        with DjangoTransactionBridge(event_publisher=bus) as bridge:
            bridge.campaigns.save(campaign)
            bridge.campaign_audience.add_member(member)
            bridge.campaign_audience.add_segment_source(source, (_reference(),))
            bridge.campaign_linkage.add_attribution(attribution)
            bridge.add_event(_event(31019))
            assert CampaignMemberModel.objects.filter(
                campaign_id=str(campaign.id)
            ).count() == 1
            assert CampaignSegmentMemberModel.objects.filter(
                source__campaign_id=str(campaign.id)
            ).count() == 1
            raise RuntimeError("injected Django failure")

    assert published == []
    assert not CampaignModel.objects.filter(pk=str(campaign.id)).exists()
    assert not CampaignMemberModel.objects.filter(campaign_id=str(campaign.id)).exists()
    assert not CampaignSegmentSourceModel.objects.filter(
        campaign_id=str(campaign.id)
    ).exists()
    assert not CampaignSegmentMemberModel.objects.filter(
        source__campaign_id=str(campaign.id)
    ).exists()
    assert not CampaignAttributionModel.objects.filter(
        campaign_id=str(campaign.id)
    ).exists()


def test_outer_django_rollback_reverses_bridge_commit_and_defers_event() -> None:
    campaign = _campaign(31020)
    bus = InProcessEventBus()
    published: list[DomainEvent] = []
    bus.subscribe("campaign.member_added", published.append)

    with pytest.raises(RuntimeError, match="rollback ambient"):
        with transaction.atomic():
            with DjangoTransactionBridge(event_publisher=bus) as bridge:
                bridge.campaigns.save(campaign)
                bridge.campaign_audience.add_member(
                    CampaignMember(campaign.id, _reference(), NOW)
                )
                bridge.add_event(_event(31021))
                bridge.commit()
            assert published == []
            assert CampaignModel.objects.filter(pk=str(campaign.id)).exists()
            raise RuntimeError("rollback ambient")

    assert published == []
    assert not CampaignModel.objects.filter(pk=str(campaign.id)).exists()
    assert not CampaignMemberModel.objects.filter(campaign_id=str(campaign.id)).exists()


def test_duplicate_capture_constraint_rolls_back_siblings_and_events() -> None:
    campaign = _campaign(31022)
    source = _source(campaign, 31023)
    bus = InProcessEventBus()
    published: list[DomainEvent] = []
    bus.subscribe("campaign.member_added", published.append)

    with pytest.raises(IntegrityError):
        with DjangoTransactionBridge(event_publisher=bus) as bridge:
            bridge.campaigns.save(campaign)
            bridge.campaign_audience.add_member(
                CampaignMember(campaign.id, _reference(), NOW)
            )
            bridge.campaign_audience.add_segment_source(source, (_reference(),))
            bridge.add_event(_event(31024))
            row = CampaignSegmentSourceModel.objects.get(
                campaign_id=str(campaign.id)
            )
            # Direct ORM constraint violation is deliberately caught at
            # this test boundary; the public facade normally maps errors.
            CampaignSegmentMemberModel.objects.create(
                source=row,
                entity_kind="contact",
                entity_id=str(_reference().id),
            )
            bridge.commit()

    assert published == []
    assert not CampaignModel.objects.filter(pk=str(campaign.id)).exists()
    assert not CampaignSegmentSourceModel.objects.filter(
        campaign_id=str(campaign.id)
    ).exists()
    assert not CampaignSegmentMemberModel.objects.filter(
        source__campaign_id=str(campaign.id)
    ).exists()


def test_django_null_external_ref_normalizes_to_unique_empty_db_value() -> None:
    campaign = _campaign(31025)
    with DjangoTransactionBridge() as bridge:
        bridge.campaigns.save(campaign)
        bridge.commit()
    target = CampaignAttributionReference(
        campaign_id=campaign.id, target=_reference(), source="Organic",
        external_ref=None, recorded_at=NOW,
    )
    repo = DjangoCampaignLinkageRepository()
    repo.add_attribution(target)
    with pytest.raises(DuplicateError) as exc:
        repo.add_attribution(target)
    assert exc.value.code == "campaign.attribution.duplicate"
    persisted = CampaignAttributionModel.objects.get(
        campaign_id=str(campaign.id)
    )
    assert persisted.external_ref == ""


def test_orm_campaign_delete_cascades_children_without_deleting_communication_store() -> None:
    campaign = _campaign(31026)
    with DjangoTransactionBridge() as bridge:
        bridge.campaigns.save(campaign)
        bridge.campaign_audience.add_member(
            CampaignMember(campaign.id, _reference(), NOW)
        )
        bridge.campaign_audience.add_segment_source(
            _source(campaign, 31027), (_reference(),)
        )
        bridge.commit()
    CampaignModel.objects.filter(pk=str(campaign.id)).delete()
    assert CampaignMemberModel.objects.filter(campaign_id=str(campaign.id)).count() == 0
    assert CampaignSegmentSourceModel.objects.filter(
        campaign_id=str(campaign.id)
    ).count() == 0
    assert not CampaignSegmentMemberModel.objects.exists()
    assert CommunicationRecordModel._meta.db_table in connection.introspection.table_names()


def test_postgres_two_writers_duplicate_direct_member_has_one_winner() -> None:
    if connection.vendor != "postgresql":
        pytest.skip("requires real PostgreSQL, never SQLite")
    campaign = _campaign(31028)
    with DjangoTransactionBridge() as bridge:
        bridge.campaigns.save(campaign)
        bridge.commit()
    member = CampaignMember(campaign.id, _reference(), NOW)
    barrier = Barrier(2)

    def writer() -> str:
        try:
            barrier.wait(timeout=15)
            try:
                DjangoCampaignAudienceRepository().add_member(member)
            except DuplicateError as error:
                assert error.code == "campaign.member.duplicate"
                return "duplicate"
            return "committed"
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: writer(), range(2)))
    assert sorted(results) == ["committed", "duplicate"]
    assert CampaignMemberModel.objects.filter(
        campaign_id=str(campaign.id)
    ).count() == 1


def test_postgres_django_source_fk_is_real_and_orphans_are_rejected() -> None:
    if connection.vendor != "postgresql":
        pytest.skip("requires real PostgreSQL")
    with connection.cursor() as cursor:
        constraints = connection.introspection.get_constraints(
            cursor, "pycrmkit_campaign_segment_members"
        )
    assert any(
        item.get("foreign_key") == ("pycrmkit_campaign_segment_sources", "id")
        for item in constraints.values()
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            CampaignSegmentMemberModel.objects.create(
                source_id=987654321,
                entity_kind="contact",
                entity_id=str(UUID(int=31029)),
            )
    assert not CampaignSegmentMemberModel.objects.exists()
