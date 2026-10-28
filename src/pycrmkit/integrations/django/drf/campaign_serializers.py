"""DRF Campaign request/response serializers.

The serializers translate to domain DTOs and never serialize Django ORM models.
Campaign routes must provide a trusted security boundary before registration.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import TYPE_CHECKING, Any, cast

from rest_framework import serializers

from pycrmkit.campaigns import (
    Campaign,
    CampaignAttributionReference,
    CampaignCommunicationLink,
    CampaignMember,
    CampaignSegmentSource,
    CampaignStatus,
    CampaignUpdate,
)
from pycrmkit.core.ids import EntityId
from pycrmkit.integrations.campaign_payload_validation import (
    validate_campaign_metadata,
)
from pycrmkit.integrations.django.drf.segmentation_serializers import (
    EntityReferenceSerializer,
)

if TYPE_CHECKING:
    class _SerializerBase(serializers.Serializer[Any]):
        pass
else:
    _SerializerBase = serializers.Serializer


class StrictCampaignSerializer(_SerializerBase):
    """Reject unknown request fields rather than silently ignoring them."""

    def to_internal_value(self, data: Any) -> dict[str, Any]:
        if isinstance(data, Mapping):
            extra = set(data) - set(self.fields)
            if extra:
                raise serializers.ValidationError(
                    {key: ["unknown field"] for key in sorted(extra)}
                )
        return cast(dict[str, Any], super().to_internal_value(data))

    def validate_metadata(self, value: Any) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise serializers.ValidationError("metadata must be a JSON object")
        try:
            return validate_campaign_metadata(value)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc)) from exc


class AwareDateTimeField(serializers.DateTimeField):
    """Do not silently assume a timezone when the client omits one."""

    def to_internal_value(self, value: Any) -> datetime:
        if isinstance(value, datetime):
            parsed = value
        elif isinstance(value, str):
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                parsed = None
        else:
            parsed = None
        if parsed is not None and (
            parsed.tzinfo is None or parsed.utcoffset() is None
        ):
            raise serializers.ValidationError(
                "datetime must include a timezone offset"
            )
        return super().to_internal_value(value)


class CampaignFilterSerializer(StrictCampaignSerializer):
    status = serializers.ChoiceField(
        choices=[item.value for item in CampaignStatus], required=False
    )
    owner_id = serializers.UUIDField(required=False)
    include_archived = serializers.BooleanField(required=False, default=False)
    limit = serializers.IntegerField(required=False, min_value=1, max_value=200)
    offset = serializers.IntegerField(required=False, min_value=0)


class CampaignCreateSerializer(StrictCampaignSerializer):
    key = serializers.CharField(max_length=120)
    name = serializers.CharField(max_length=200)
    description = serializers.CharField(
        max_length=2000, required=False, allow_null=True, allow_blank=True
    )
    starts_at = AwareDateTimeField(required=False, allow_null=True)
    ends_at = AwareDateTimeField(required=False, allow_null=True)
    owner_id = serializers.UUIDField(required=False, allow_null=True)
    metadata = serializers.JSONField(required=False, default=dict)


class CampaignUpdateSerializer(StrictCampaignSerializer):
    expected_revision = serializers.IntegerField(min_value=1)
    name = serializers.CharField(max_length=200, required=False)
    description = serializers.CharField(
        max_length=2000, required=False, allow_null=True, allow_blank=True
    )
    starts_at = AwareDateTimeField(required=False, allow_null=True)
    ends_at = AwareDateTimeField(required=False, allow_null=True)
    owner_id = serializers.UUIDField(required=False, allow_null=True)
    metadata = serializers.JSONField(required=False, allow_null=False)

    def to_domain(self) -> CampaignUpdate:
        """Preserve UNSET for missing keys and None for explicit null."""
        data = cast(dict[str, Any], self.validated_data)
        fields = (
            "name",
            "description",
            "starts_at",
            "ends_at",
            "owner_id",
            "metadata",
        )
        changes = {key: data[key] for key in fields if key in data}
        if changes.get("owner_id") is not None and "owner_id" in changes:
            changes["owner_id"] = EntityId(changes["owner_id"])
        return CampaignUpdate(**changes)


class CampaignRevisionSerializer(StrictCampaignSerializer):
    expected_revision = serializers.IntegerField(min_value=1)


class CampaignResponseSerializer(StrictCampaignSerializer):
    id = serializers.UUIDField()
    key = serializers.CharField()
    name = serializers.CharField()
    description = serializers.CharField(allow_null=True)
    status = serializers.ChoiceField(
        choices=[status.value for status in CampaignStatus]
    )
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()
    starts_at = serializers.DateTimeField(allow_null=True)
    ends_at = serializers.DateTimeField(allow_null=True)
    owner_id = serializers.UUIDField(allow_null=True)
    revision = serializers.IntegerField()
    metadata = serializers.JSONField()
    archived_at = serializers.DateTimeField(allow_null=True)


def campaign_payload(value: Campaign) -> dict[str, Any]:
    return {
        "id": value.id.value,
        "key": value.key,
        "name": value.name,
        "description": value.description,
        "status": value.status.value,
        "created_at": value.created_at,
        "updated_at": value.updated_at,
        "starts_at": value.starts_at,
        "ends_at": value.ends_at,
        "owner_id": value.owner_id.value if value.owner_id else None,
        "revision": value.revision,
        "metadata": value.metadata,
        "archived_at": value.archived_at,
    }


class CampaignMembersSerializer(StrictCampaignSerializer):
    members = EntityReferenceSerializer(
        many=True, allow_empty=False
    )
    source: Any = serializers.CharField(required=False, max_length=120, default="api")
    metadata = serializers.JSONField(required=False, default=dict)

    def validate_members(self, value: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if len(value) > 1000:
            raise serializers.ValidationError("at most 1000 members are allowed")
        identities = [(v["kind"].casefold(), v["id"]) for v in value]
        if len(identities) != len(set(identities)):
            raise serializers.ValidationError("duplicate member reference")
        return value


class CampaignRemoveMembersSerializer(StrictCampaignSerializer):
    members = EntityReferenceSerializer(
        many=True, allow_empty=False
    )

    def validate_members(self, value: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if len(value) > 1000:
            raise serializers.ValidationError("at most 1000 members are allowed")
        return value


class CampaignMemberResponseSerializer(StrictCampaignSerializer):
    campaign_id = serializers.UUIDField()
    entity = EntityReferenceSerializer()
    added_at = serializers.DateTimeField()
    source: Any = serializers.CharField()
    metadata = serializers.JSONField()


def campaign_member_payload(value: CampaignMember) -> dict[str, Any]:
    return {
        "campaign_id": value.campaign_id.value,
        "entity": {"kind": value.entity.kind, "id": value.entity.id.value},
        "added_at": value.added_at,
        "source": value.source,
        "metadata": value.metadata,
    }


class CampaignSegmentAttachSerializer(StrictCampaignSerializer):
    segment_id = serializers.UUIDField()
    metadata = serializers.JSONField(required=False, default=dict)


class CampaignSegmentSourceResponseSerializer(StrictCampaignSerializer):
    campaign_id = serializers.UUIDField()
    segment_id = serializers.UUIDField()
    segment_revision = serializers.IntegerField()
    entity_kind = serializers.CharField()
    attached_at = serializers.DateTimeField()
    captured_at = serializers.DateTimeField()
    member_count = serializers.IntegerField()
    metadata = serializers.JSONField()


def campaign_segment_source_payload(value: CampaignSegmentSource) -> dict[str, Any]:
    return {
        "campaign_id": value.campaign_id.value,
        "segment_id": value.segment_id.value,
        "segment_revision": value.segment_revision,
        "entity_kind": value.entity_kind,
        "attached_at": value.attached_at,
        "captured_at": value.captured_at,
        "member_count": value.member_count,
        "metadata": value.metadata,
    }


class CampaignAttributionSerializer(StrictCampaignSerializer):
    target = EntityReferenceSerializer()
    source: Any = serializers.CharField(max_length=120)
    external_ref = serializers.CharField(
        required=False, allow_null=True, allow_blank=True, max_length=512
    )
    metadata = serializers.JSONField(required=False, default=dict)


class CampaignAttributionRemoveSerializer(StrictCampaignSerializer):
    target = EntityReferenceSerializer()
    source: Any = serializers.CharField(max_length=120)
    external_ref = serializers.CharField(
        required=False, allow_null=True, allow_blank=True, max_length=512
    )


class CampaignAttributionResponseSerializer(StrictCampaignSerializer):
    campaign_id = serializers.UUIDField()
    target = EntityReferenceSerializer()
    source: Any = serializers.CharField()
    external_ref = serializers.CharField(allow_null=True)
    recorded_at = serializers.DateTimeField()
    metadata = serializers.JSONField()


def campaign_attribution_payload(value: CampaignAttributionReference) -> dict[str, Any]:
    return {
        "campaign_id": value.campaign_id.value,
        "target": {"kind": value.target.kind, "id": value.target.id.value},
        "source": value.source,
        "external_ref": value.external_ref,
        "recorded_at": value.recorded_at,
        "metadata": value.metadata,
    }


class CampaignCommunicationLinkSerializer(StrictCampaignSerializer):
    communication_id = serializers.UUIDField()
    role = serializers.CharField(
        required=False, default="touchpoint", max_length=120
    )
    metadata = serializers.JSONField(required=False, default=dict)


class CampaignCommunicationUnlinkSerializer(StrictCampaignSerializer):
    communication_id = serializers.UUIDField()


class CampaignCommunicationLinkResponseSerializer(StrictCampaignSerializer):
    campaign_id = serializers.UUIDField()
    communication_id = serializers.UUIDField()
    linked_at = serializers.DateTimeField()
    role = serializers.CharField()
    metadata = serializers.JSONField()


def campaign_communication_link_payload(
    value: CampaignCommunicationLink,
) -> dict[str, Any]:
    return {
        "campaign_id": value.campaign_id.value,
        "communication_id": value.communication_id.value,
        "linked_at": value.linked_at,
        "role": value.role,
        "metadata": value.metadata,
    }


__all__ = [
    "StrictCampaignSerializer",
    "AwareDateTimeField",
    "CampaignFilterSerializer",
    "CampaignCreateSerializer",
    "CampaignUpdateSerializer",
    "CampaignRevisionSerializer",
    "CampaignResponseSerializer",
    "campaign_payload",
    "CampaignMembersSerializer",
    "CampaignRemoveMembersSerializer",
    "CampaignMemberResponseSerializer",
    "campaign_member_payload",
    "CampaignSegmentAttachSerializer",
    "CampaignSegmentSourceResponseSerializer",
    "campaign_segment_source_payload",
    "CampaignAttributionSerializer",
    "CampaignAttributionRemoveSerializer",
    "CampaignAttributionResponseSerializer",
    "campaign_attribution_payload",
    "CampaignCommunicationLinkSerializer",
    "CampaignCommunicationUnlinkSerializer",
    "CampaignCommunicationLinkResponseSerializer",
    "campaign_communication_link_payload",
]
