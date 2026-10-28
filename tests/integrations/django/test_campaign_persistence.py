"""Django Campaign facade and three-adapter behavioral contract smoke."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from typing import cast
from uuid import UUID

import pytest
from django.db import connection, connections, transaction

from pycrmkit import CRM
from pycrmkit.campaigns import (
    Campaign,
    CampaignAttributionReference,
    CampaignAttributionUnitOfWork,
    CampaignAudienceUnitOfWork,
    CampaignId,
    CampaignLinkageRepository,
    CampaignQuery,
    CampaignUnitOfWork,
)
from pycrmkit.communication import (
    CommunicationAddress,
    CommunicationChannel,
    CommunicationDirection,
    CommunicationRecord,
    CommunicationRecordId,
)
from pycrmkit.config import CRMConfig
from pycrmkit.core.pagination import OffsetPageRequest
from pycrmkit.core.references import EntityReference
from pycrmkit.core.time import FixedClock
from pycrmkit.core.unit_of_work import UnitOfWork
from pycrmkit.events import InProcessEventBus
from pycrmkit.exceptions import ConflictError, DuplicateError, NotFoundError
from pycrmkit.integrations.django.campaign_audience import DjangoCampaignAudienceRepository
from pycrmkit.integrations.django.campaign_codec import (
    campaign_from_model,
    campaign_to_model,
)
from pycrmkit.integrations.django.campaign_linkage import DjangoCampaignLinkageRepository
from pycrmkit.integrations.django.campaign_repositories import DjangoCampaignRepository
from pycrmkit.integrations.django.models import CampaignModel
from pycrmkit.integrations.django.transactions import DjangoTransactionBridge

NOW = datetime(2026, 10, 28, 8, 30, tzinfo=UTC)


def _crm() -> CRM:
    bus = InProcessEventBus()

    def factory() -> UnitOfWork:
        return cast(UnitOfWork, DjangoTransactionBridge(event_publisher=bus))

    return CRM(
        uow_factory=factory,
        event_bus=bus,
        clock=FixedClock(NOW),
        config=CRMConfig(events_enabled=True, audit_enabled=False),
        webhook_auto_delivery=False,
    )


def _campaign(number: int, *, revision: int = 1, name: str = "Django") -> Campaign:
    return Campaign(
        id=CampaignId(UUID(int=number)),
        created_at=NOW,
        updated_at=NOW if revision == 1 else NOW + timedelta(minutes=1),
        key=f"django-contract-{number}",
        name=name,
        revision=revision,
        metadata={"nested": {"items": [1, 2]}},
    )


def test_django_bridge_exposes_contracts_and_closes_after_commit() -> None:
    bridge = DjangoTransactionBridge()
    with bridge:
        assert isinstance(bridge, CampaignUnitOfWork)
        assert isinstance(bridge, CampaignAudienceUnitOfWork)
        assert isinstance(bridge, CampaignAttributionUnitOfWork)
        assert isinstance(bridge.campaign_linkage, CampaignLinkageRepository)
        bridge.campaigns.save(_campaign(901))
        bridge.commit()
    assert DjangoCampaignRepository().get(CampaignId(UUID(int=901))).name == "Django"


def test_campaign_repo_save_update_find_and_revision_conflicts() -> None:
    repo = DjangoCampaignRepository()
    initial = _campaign(902)
    repo.save(initial)
    assert repo.get(initial.id) == initial
    assert repo.find_by_key(" DJANGO-CONTRACT-902 ") == initial
    assert repo.search(CampaignQuery(), OffsetPageRequest()).total == 1
    with pytest.raises(ConflictError) as err:
        repo.save(_campaign(902, name="Silently altered"))
    assert err.value.code == "campaign.revision.conflict"

    revised = _campaign(902, revision=2, name="Revision two")
    repo.save(revised)
    assert repo.get(initial.id) == revised
    repo.save(revised)
    with pytest.raises(ConflictError):
        repo.save(_campaign(902, revision=2, name="Conflicting state"))

    with pytest.raises(DuplicateError) as duplicate:
        repo.save(Campaign(
            id=CampaignId(UUID(int=903)),
            created_at=NOW,
            updated_at=NOW,
            key=initial.key,
            name="Collision",
        ))
    assert duplicate.value.code == "campaign.key.duplicate"


def test_django_campaign_codec_preserves_metadata_and_utc() -> None:
    campaign = _campaign(904)
    orm = campaign_to_model(campaign)
    orm.save()
    restored = campaign_from_model(CampaignModel.objects.get(pk=str(campaign.id)))
    assert restored == campaign
    assert restored.metadata == campaign.metadata
    assert restored.created_at.tzinfo is not None


def test_django_facade_persists_audience_segment_snapshot_and_attribution() -> None:
    crm = _crm()
    ada = crm.contacts.create(display_name="Ada", source="LinkedIn")
    grace = crm.contacts.create(display_name="Grace", source="Newsletter")
    ada_ref = EntityReference("contact", ada.id)
    grace_ref = EntityReference("contact", grace.id)

    campaign = crm.campaigns.create(key="django-launch", name="Django Launch")
    crm.campaigns.add_member(campaign.id, ada_ref)
    segment = crm.segments.create_static(
        key="django-audience", name="Django Audience", entity_kind="contact"
    )
    crm.segments.add_member(segment.id, ada_ref)
    crm.segments.add_member(segment.id, grace_ref)
    source = crm.campaigns.attach_segment_source(campaign.id, segment.id)
    assert source.member_count == 2
    assert crm.campaigns.audience_count(campaign.id) == 2
    assert set(crm.campaigns.audience(campaign.id).items) == {ada_ref, grace_ref}

    crm.segments.remove_member(segment.id, grace_ref)
    assert crm.campaigns.contains(campaign.id, grace_ref)
    refreshed = crm.campaigns.refresh_segment_source(campaign.id, segment.id)
    assert refreshed.member_count == 1
    assert not crm.campaigns.contains(campaign.id, grace_ref)

    attribution = crm.campaigns.add_attribution(
        campaign.id, ada_ref, source=" LinkedIn Organic ", external_ref=None
    )
    assert isinstance(attribution, CampaignAttributionReference)
    assert crm.campaigns.attributions(campaign.id).items == (attribution,)
    assert crm.campaigns.communication_links(campaign.id).total == 0

    unknown_id = CommunicationRecordId(UUID(int=999))
    with pytest.raises(NotFoundError) as missing:
        crm.campaigns.link_communication(campaign.id, unknown_id)
    assert missing.value.code == "communication.record.not_found"

    record = CommunicationRecord(
        id=CommunicationRecordId(UUID(int=998)),
        created_at=NOW,
        updated_at=NOW,
        channel=CommunicationChannel.EMAIL,
        direction=CommunicationDirection.OUTBOUND,
        occurred_at=NOW,
        counterparties=(
            CommunicationAddress(CommunicationChannel.EMAIL, "ada@example.com"),
        ),
        references=(ada_ref,),
        subject="Django native",
        metadata={"nested": {"campaign": True}},
    )
    with DjangoTransactionBridge() as bridge:
        bridge.communications.save_record(record)
        bridge.commit()
    linked = crm.campaigns.link_communication(campaign.id, record.id)
    assert linked.communication_id == record.id
    assert crm.campaigns.communications(campaign.id).items == (record,)

    another = _crm()
    assert another.campaigns.get(campaign.id) == campaign
    assert another.campaigns.audience(campaign.id).items == (ada_ref,)
    assert another.campaigns.attributions(campaign.id).items == (attribution,)
    assert another.campaigns.communications(campaign.id).items == (record,)


def test_django_campaign_rollback_discards_all_state() -> None:
    campaign = _campaign(905)
    with DjangoTransactionBridge() as bridge:
        bridge.campaigns.save(campaign)
        bridge.rollback()
        assert bridge.campaigns.find(campaign.id) is None
    assert DjangoCampaignRepository().find(campaign.id) is None


def test_django_campaign_repositories_can_operate_in_one_outer_atomic() -> None:
    campaign = _campaign(906)
    with transaction.atomic():
        with DjangoTransactionBridge() as bridge:
            bridge.campaigns.save(campaign)
            bridge.commit()
        assert DjangoCampaignRepository().get(campaign.id) == campaign
    assert DjangoCampaignRepository().get(campaign.id) == campaign

    assert isinstance(DjangoCampaignAudienceRepository(), object)
    assert isinstance(DjangoCampaignLinkageRepository(), object)


def test_postgresql_concurrent_campaign_revision_cas() -> None:
    """Two writers of the same revision cannot both overwrite one aggregate."""
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL concurrency qualification only")
    original = _campaign(907)
    DjangoCampaignRepository().save(original)
    barrier = Barrier(2)

    def update(name: str) -> str:
        try:
            repository = DjangoCampaignRepository()
            current = repository.get(original.id)
            candidate = Campaign(
                id=current.id,
                created_at=current.created_at,
                updated_at=current.updated_at + timedelta(minutes=1),
                key=current.key,
                name=name,
                revision=current.revision + 1,
                metadata=dict(current.metadata),
            )
            barrier.wait(timeout=15)
            try:
                repository.save(candidate)
                return "success"
            except ConflictError:
                return "conflict"
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(update, ("writer-one", "writer-two")))
    assert sorted(results) == ["conflict", "success"]
    assert DjangoCampaignRepository().get(original.id).revision == 2
