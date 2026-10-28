"""Strict Campaign transport schemas for the optional FastAPI adapter.

The schemas intentionally encode the domain-facing CRM facade, not database models.
They must not be imported by the framework-neutral core.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

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
from pycrmkit.integrations.campaign_payload_validation import validate_campaign_metadata
from pycrmkit.core.references import EntityReference
from pycrmkit.integrations.fastapi.schemas import EntityReferenceSchema


class CampaignAPIModel(BaseModel):
    """Base schema rejecting unexpected request and response fields."""

    model_config = ConfigDict(extra="forbid")


class CampaignCreateRequest(CampaignAPIModel):
    key: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    starts_at: AwareDatetime | None = None
    ends_at: AwareDatetime | None = None
    owner_id: UUID | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("metadata")
    @classmethod
    def check_metadata(cls, value: dict[str, Any]) -> dict[str, Any]:
        return validate_campaign_metadata(value)


class CampaignUpdateRequest(CampaignAPIModel):
    """Transport PATCH with positive expected revision and explicit key presence."""

    expected_revision: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    starts_at: AwareDatetime | None = None
    ends_at: AwareDatetime | None = None
    owner_id: UUID | None = None
    metadata: dict[str, Any] | None = None

    @model_validator(mode="after")
    def disallow_null_for_nonnullable(self) -> CampaignUpdateRequest:
        if "name" in self.model_fields_set and self.name is None:
            raise ValueError("name cannot be null")
        if "metadata" in self.model_fields_set and self.metadata is None:
            raise ValueError("metadata cannot be null")
        return self

    @field_validator("metadata")
    @classmethod
    def check_metadata(
        cls, value: dict[str, Any] | None
    ) -> dict[str, Any] | None:
        return validate_campaign_metadata(value) if value is not None else None

    def to_domain(self) -> CampaignUpdate:
        """Only supplied fields are mapped; omitted values stay domain UNSET."""
        names = (
            "name",
            "description",
            "starts_at",
            "ends_at",
            "owner_id",
            "metadata",
        )
        changes: dict[str, Any] = {}
        for name in names:
            if name not in self.model_fields_set:
                continue
            value = getattr(self, name)
            if name == "owner_id" and value is not None:
                value = EntityId(value)
            changes[name] = value
        return CampaignUpdate(**changes)


class CampaignRevisionRequest(CampaignAPIModel):
    expected_revision: int = Field(ge=1)


class CampaignResponse(CampaignAPIModel):
    id: UUID
    key: str
    name: str
    description: str | None
    status: CampaignStatus
    created_at: datetime
    updated_at: datetime
    starts_at: datetime | None
    ends_at: datetime | None
    owner_id: UUID | None
    revision: int
    metadata: dict[str, Any]
    archived_at: datetime | None

    @classmethod
    def from_domain(cls, value: Campaign) -> CampaignResponse:
        return cls(
            id=value.id.value,
            key=value.key,
            name=value.name,
            description=value.description,
            status=value.status,
            created_at=value.created_at,
            updated_at=value.updated_at,
            starts_at=value.starts_at,
            ends_at=value.ends_at,
            owner_id=value.owner_id.value if value.owner_id is not None else None,
            revision=value.revision,
            metadata=value.metadata,
            archived_at=value.archived_at,
        )


class CampaignMembersRequest(CampaignAPIModel):
    members: list[EntityReferenceSchema] = Field(min_length=1, max_length=1000)
    source: str = Field(default="api", min_length=1, max_length=120)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("metadata")
    @classmethod
    def check_metadata(cls, value: dict[str, Any]) -> dict[str, Any]:
        return validate_campaign_metadata(value)

    @model_validator(mode="after")
    def no_repeated_member(self) -> CampaignMembersRequest:
        keys = [(item.kind.casefold(), item.id) for item in self.members]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate member reference in request")
        return self

    def references(self) -> tuple[EntityReference, ...]:
        return tuple(item.to_domain() for item in self.members)


class CampaignRemoveMembersRequest(CampaignAPIModel):
    members: list[EntityReferenceSchema] = Field(min_length=1, max_length=1000)

    def references(self) -> tuple[EntityReference, ...]:
        return tuple(item.to_domain() for item in self.members)


class CampaignMemberResponse(CampaignAPIModel):
    campaign_id: UUID
    entity: EntityReferenceSchema
    added_at: datetime
    source: str
    metadata: dict[str, Any]

    @classmethod
    def from_domain(cls, value: CampaignMember) -> CampaignMemberResponse:
        return cls(
            campaign_id=value.campaign_id.value,
            entity=EntityReferenceSchema.from_domain(value.entity),
            added_at=value.added_at,
            source=value.source,
            metadata=value.metadata,
        )


class CampaignSegmentAttachRequest(CampaignAPIModel):
    segment_id: UUID
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("metadata")
    @classmethod
    def check_metadata(cls, value: dict[str, Any]) -> dict[str, Any]:
        return validate_campaign_metadata(value)


class CampaignSegmentSourceResponse(CampaignAPIModel):
    campaign_id: UUID
    segment_id: UUID
    segment_revision: int
    entity_kind: str
    attached_at: datetime
    captured_at: datetime
    member_count: int
    metadata: dict[str, Any]

    @classmethod
    def from_domain(
        cls, value: CampaignSegmentSource
    ) -> CampaignSegmentSourceResponse:
        return cls(
            campaign_id=value.campaign_id.value,
            segment_id=value.segment_id.value,
            segment_revision=value.segment_revision,
            entity_kind=value.entity_kind,
            attached_at=value.attached_at,
            captured_at=value.captured_at,
            member_count=value.member_count,
            metadata=value.metadata,
        )


class CampaignAttributionRequest(CampaignAPIModel):
    target: EntityReferenceSchema
    source: str = Field(min_length=1, max_length=120)
    external_ref: str | None = Field(default=None, max_length=512)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("metadata")
    @classmethod
    def check_metadata(cls, value: dict[str, Any]) -> dict[str, Any]:
        return validate_campaign_metadata(value)


class CampaignAttributionRemoveRequest(CampaignAPIModel):
    target: EntityReferenceSchema
    source: str = Field(min_length=1, max_length=120)
    external_ref: str | None = Field(default=None, max_length=512)


class CampaignAttributionResponse(CampaignAPIModel):
    campaign_id: UUID
    target: EntityReferenceSchema
    source: str
    external_ref: str | None
    recorded_at: datetime
    metadata: dict[str, Any]

    @classmethod
    def from_domain(
        cls, value: CampaignAttributionReference
    ) -> CampaignAttributionResponse:
        return cls(
            campaign_id=value.campaign_id.value,
            target=EntityReferenceSchema.from_domain(value.target),
            source=value.source,
            external_ref=value.external_ref,
            recorded_at=value.recorded_at,
            metadata=value.metadata,
        )


class CampaignCommunicationLinkRequest(CampaignAPIModel):
    communication_id: UUID
    role: str = Field(default="touchpoint", min_length=1, max_length=120)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("metadata")
    @classmethod
    def check_metadata(cls, value: dict[str, Any]) -> dict[str, Any]:
        return validate_campaign_metadata(value)


class CampaignCommunicationUnlinkRequest(CampaignAPIModel):
    communication_id: UUID


class CampaignCommunicationLinkResponse(CampaignAPIModel):
    campaign_id: UUID
    communication_id: UUID
    linked_at: datetime
    role: str
    metadata: dict[str, Any]

    @classmethod
    def from_domain(
        cls, value: CampaignCommunicationLink
    ) -> CampaignCommunicationLinkResponse:
        return cls(
            campaign_id=value.campaign_id.value,
            communication_id=value.communication_id.value,
            linked_at=value.linked_at,
            role=value.role,
            metadata=value.metadata,
        )


__all__ = [
    "CampaignAPIModel",
    "CampaignCreateRequest",
    "CampaignUpdateRequest",
    "CampaignRevisionRequest",
    "CampaignResponse",
    "CampaignMembersRequest",
    "CampaignRemoveMembersRequest",
    "CampaignMemberResponse",
    "CampaignSegmentAttachRequest",
    "CampaignSegmentSourceResponse",
    "CampaignAttributionRequest",
    "CampaignAttributionRemoveRequest",
    "CampaignAttributionResponse",
    "CampaignCommunicationLinkRequest",
    "CampaignCommunicationUnlinkRequest",
    "CampaignCommunicationLinkResponse",
]
