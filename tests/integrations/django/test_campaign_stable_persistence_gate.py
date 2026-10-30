"""LOT-32-004: Django outer transaction events and migration ownership."""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from django.db import connection, transaction
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.recorder import MigrationRecorder

from pycrmkit.campaigns import Campaign, CampaignId
from pycrmkit.core.events import EventId, EventType
from pycrmkit.events import DomainEvent, InProcessEventBus
from pycrmkit.integrations.django.campaign_codec import campaign_from_model
from pycrmkit.integrations.django.models import CampaignModel
from pycrmkit.integrations.django.transactions import DjangoTransactionBridge

NOW = datetime(2026, 10, 30, 11, tzinfo=UTC)


def test_stable_django_outer_commit_defers_event_until_database_commit() -> None:
    identifier = CampaignId(UUID(int=3200421))
    bus = InProcessEventBus()
    observed: list[DomainEvent] = []
    bus.subscribe("campaign.created", observed.append)
    event = DomainEvent(
        id=EventId(UUID(int=3200422)),
        type=EventType("campaign.created"), schema_version=1,
        aggregate_type="campaign", aggregate_id=str(identifier), occurred_at=NOW,
    )
    with transaction.atomic():
        with DjangoTransactionBridge(event_publisher=bus) as uow:
            uow.campaigns.save(Campaign(
                id=identifier, key="stable-django-outer",
                name="Committed only with owner", created_at=NOW, updated_at=NOW,
                metadata={"source": "stable-contract"},
            ))
            uow.add_event(event)
            uow.commit()
        assert CampaignModel.objects.filter(pk=str(identifier)).exists()
        assert observed == []
    assert observed == [event]
    assert campaign_from_model(CampaignModel.objects.get(pk=str(identifier))).metadata == {
        "source": "stable-contract"
    }


def test_stable_django_migration_heads_have_separate_ownership() -> None:
    graph = MigrationLoader(connection).graph
    assert ("pycrmkit_crm", "0004_campaign_persistence") in graph.nodes
    assert ("pycrmkit_crm", "0005_communication_record_store") in graph.nodes
    assert ("pycrmkit_crm", "0004_campaign_persistence") in graph.forwards_plan(
        ("pycrmkit_crm", "0005_communication_record_store")
    )
    applied = MigrationRecorder(connection).applied_migrations()
    assert ("pycrmkit_crm", "0005_communication_record_store") in applied
    tables = connection.introspection.table_names()
    assert "django_migrations" in tables
    assert "alembic_version" not in tables
