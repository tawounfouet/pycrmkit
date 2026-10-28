"""Structural and integrity tests for Django Campaign persistence models."""

from __future__ import annotations

from uuid import uuid4

import pytest
from django.db import IntegrityError, models, transaction
from django.utils import timezone

from pycrmkit.integrations.django.models import (
    CampaignAttributionModel,
    CampaignCommunicationLinkModel,
    CampaignMemberModel,
    CampaignModel,
    CampaignSegmentMemberModel,
    CampaignSegmentSourceModel,
)


def _campaign(*, key: str | None = None) -> CampaignModel:
    now = timezone.now()
    return CampaignModel.objects.create(
        id=str(uuid4()),
        key=key or f"campaign-{uuid4().hex}",
        name="Campaign persistence qualification",
        status="draft",
        revision=1,
        metadata_json={"nested": {"source": ["django", "orm"]}},
        created_at=now,
        updated_at=now,
    )


def _source(
    campaign: CampaignModel,
    *,
    segment_id: str | None = None,
    member_count: int = 0,
) -> CampaignSegmentSourceModel:
    now = timezone.now()
    return CampaignSegmentSourceModel.objects.create(
        campaign=campaign,
        segment_id=segment_id or str(uuid4()),
        segment_revision=1,
        entity_kind="contact",
        attached_at=now,
        captured_at=now,
        member_count=member_count,
    )


def test_six_campaign_tables_and_internal_source_identity() -> None:
    assert {
        model._meta.db_table
        for model in (
            CampaignModel,
            CampaignMemberModel,
            CampaignSegmentSourceModel,
            CampaignSegmentMemberModel,
            CampaignAttributionModel,
            CampaignCommunicationLinkModel,
        )
    } == {
        "pycrmkit_campaigns",
        "pycrmkit_campaign_members",
        "pycrmkit_campaign_segment_sources",
        "pycrmkit_campaign_segment_members",
        "pycrmkit_campaign_attributions",
        "pycrmkit_campaign_communication_links",
    }
    assert CampaignModel._meta.pk.name == "id"
    assert CampaignModel._meta.get_field("id").primary_key
    assert isinstance(
        CampaignSegmentSourceModel._meta.get_field("id"),
        models.BigAutoField,
    )
    captured_fk = CampaignSegmentMemberModel._meta.get_field("source")
    assert isinstance(captured_fk, models.ForeignKey)
    assert captured_fk.db_constraint
    assert captured_fk.remote_field.model is CampaignSegmentSourceModel
    assert captured_fk.remote_field.on_delete is models.CASCADE
    assert captured_fk.column == "source_id"


def test_campaign_owns_children_without_cross_aggregate_fks() -> None:
    for child_model in (
        CampaignMemberModel,
        CampaignSegmentSourceModel,
        CampaignAttributionModel,
        CampaignCommunicationLinkModel,
    ):
        fk = child_model._meta.get_field("campaign")
        assert isinstance(fk, models.ForeignKey)
        assert fk.db_constraint
        assert fk.remote_field.model is CampaignModel
        assert fk.remote_field.on_delete is models.CASCADE

    assert isinstance(
        CampaignSegmentSourceModel._meta.get_field("segment_id"),
        models.CharField,
    )
    assert isinstance(
        CampaignCommunicationLinkModel._meta.get_field("communication_id"),
        models.CharField,
    )
    assert not isinstance(
        CampaignCommunicationLinkModel._meta.get_field("communication_id"),
        models.ForeignKey,
    )


def test_capture_rejects_orphan_source_fk() -> None:
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            CampaignSegmentMemberModel.objects.create(
                source_id=987654321,
                entity_kind="contact",
                entity_id=str(uuid4()),
            )
    assert not CampaignSegmentMemberModel.objects.exists()


def test_source_orm_cascade_only_deletes_its_snapshot() -> None:
    campaign = _campaign()
    direct_entity_id = str(uuid4())
    CampaignMemberModel.objects.create(
        campaign=campaign,
        entity_kind="contact",
        entity_id=direct_entity_id,
        added_at=timezone.now(),
        source="manual",
    )
    first = _source(campaign, member_count=2)
    second = _source(campaign, member_count=1)
    for _ in range(2):
        CampaignSegmentMemberModel.objects.create(
            source=first, entity_kind="contact", entity_id=str(uuid4())
        )
    CampaignSegmentMemberModel.objects.create(
        source=second, entity_kind="contact", entity_id=str(uuid4())
    )

    first.delete()

    assert CampaignSegmentMemberModel.objects.count() == 1
    assert CampaignSegmentSourceModel.objects.count() == 1
    assert CampaignMemberModel.objects.get().entity_id == direct_entity_id


def test_campaign_segment_business_key_unique_per_campaign() -> None:
    first_campaign = _campaign()
    second_campaign = _campaign()
    segment_id = str(uuid4())
    _source(first_campaign, segment_id=segment_id)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _source(first_campaign, segment_id=segment_id)

    other = _source(second_campaign, segment_id=segment_id)
    assert other.campaign_id == second_campaign.id
    assert CampaignSegmentSourceModel.objects.count() == 2


def test_capture_source_member_uniqueness() -> None:
    source = _source(_campaign())
    entity_id = str(uuid4())
    CampaignSegmentMemberModel.objects.create(
        source=source, entity_kind="contact", entity_id=entity_id
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            CampaignSegmentMemberModel.objects.create(
                source=source, entity_kind="contact", entity_id=entity_id
            )
    assert CampaignSegmentMemberModel.objects.count() == 1


def test_attribution_blank_external_ref_is_unique() -> None:
    campaign = _campaign()
    target_id = str(uuid4())
    values = dict(
        campaign=campaign,
        target_kind="contact",
        target_id=target_id,
        source="email",
        external_ref="",
        recorded_at=timezone.now(),
    )
    CampaignAttributionModel.objects.create(**values)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            CampaignAttributionModel.objects.create(**values)
    assert CampaignAttributionModel.objects.count() == 1


def test_communication_link_is_unique_but_has_no_cross_domain_fk() -> None:
    campaign = _campaign()
    communication_id = str(uuid4())
    values = dict(
        campaign=campaign,
        communication_id=communication_id,
        linked_at=timezone.now(),
        role="touchpoint",
    )
    CampaignCommunicationLinkModel.objects.create(**values)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            CampaignCommunicationLinkModel.objects.create(**values)
    assert CampaignCommunicationLinkModel.objects.count() == 1


def test_nested_metadata_and_timestamps_round_trip_at_orm_boundary() -> None:
    campaign = _campaign()
    campaign.refresh_from_db()
    assert campaign.metadata_json == {"nested": {"source": ["django", "orm"]}}
    assert timezone.is_aware(campaign.created_at)
    assert timezone.is_aware(campaign.updated_at)
