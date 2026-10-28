"""Contracts for DRF Campaign serializers (without public route exposure)."""

from __future__ import annotations

from rest_framework.exceptions import ValidationError

from pycrmkit.campaigns import UNSET
from pycrmkit.integrations.django.drf.campaign_serializers import (
    CampaignCreateSerializer,
    CampaignMembersSerializer,
    CampaignRevisionSerializer,
    CampaignUpdateSerializer,
)


def test_drf_campaign_patch_preserves_omitted_values() -> None:
    serializer = CampaignUpdateSerializer(data={"expected_revision": 3})
    assert serializer.is_valid(), serializer.errors
    changes = serializer.to_domain()
    assert changes.name is UNSET
    assert changes.description is UNSET
    assert changes.starts_at is UNSET
    assert changes.ends_at is UNSET
    assert changes.owner_id is UNSET
    assert changes.metadata is UNSET


def test_drf_campaign_patch_preserves_explicit_null() -> None:
    serializer = CampaignUpdateSerializer(
        data={"expected_revision": 3, "description": None, "owner_id": None}
    )
    assert serializer.is_valid(), serializer.errors
    changes = serializer.to_domain()
    assert changes.description is None
    assert changes.owner_id is None
    assert changes.name is UNSET


def test_drf_campaign_patch_rejects_status_and_key_changes() -> None:
    serializer = CampaignUpdateSerializer(
        data={"expected_revision": 1, "status": "active"}
    )
    assert not serializer.is_valid()
    assert "status" in serializer.errors

    serializer = CampaignUpdateSerializer(
        data={"expected_revision": 1, "key": "new-key"}
    )
    assert not serializer.is_valid()
    assert "key" in serializer.errors


def test_drf_campaign_patch_rejects_invalid_revision_and_null_metadata() -> None:
    serializer = CampaignUpdateSerializer(data={"expected_revision": 0})
    assert not serializer.is_valid()
    serializer = CampaignUpdateSerializer(
        data={"expected_revision": 1, "metadata": None}
    )
    assert not serializer.is_valid()


def test_drf_campaign_create_rejects_naive_timestamp() -> None:
    serializer = CampaignCreateSerializer(
        data={
            "key": "renewal-q4",
            "name": "Renewal Q4",
            "starts_at": "2026-10-28T15:00:00",
        }
    )
    assert not serializer.is_valid()
    assert "starts_at" in serializer.errors


def test_drf_campaign_create_rejects_client_supplied_revision() -> None:
    serializer = CampaignCreateSerializer(
        data={"key": "renewal-q4", "name": "Renewal Q4", "revision": 10}
    )
    assert not serializer.is_valid()
    assert "revision" in serializer.errors


def test_drf_campaign_revision_required_for_lifecycle() -> None:
    serializer = CampaignRevisionSerializer(data={})
    assert not serializer.is_valid()
    assert "expected_revision" in serializer.errors


def test_drf_campaign_members_reject_duplicate_references() -> None:
    ref = {"kind": "contact", "id": "00000000-0000-4000-8000-000000000001"}
    serializer = CampaignMembersSerializer(data={"members": [ref, ref]})
    assert not serializer.is_valid()
    assert "members" in serializer.errors


def test_drf_campaign_members_require_at_least_one_reference() -> None:
    serializer = CampaignMembersSerializer(data={"members": []})
    assert not serializer.is_valid()
    assert "members" in serializer.errors
