"""Pydantic transport schemas for the optional FastAPI integration."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, Self, TypedDict
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from pycrmkit.activities import UNSET as ACTIVITY_UNSET
from pycrmkit.activities import (
    Activity,
    ActivityDirection,
    ActivityId,
    ActivityParticipant,
    ActivityType,
    ActivityUpdate,
)
from pycrmkit.contacts import UNSET as CONTACT_UNSET
from pycrmkit.contacts import (
    Address,
    Contact,
    ContactEmail,
    ContactId,
    ContactPhone,
    ContactStatus,
    ContactUpdate,
    VerificationState,
)
from pycrmkit.core.ids import EntityId, UUIDId
from pycrmkit.core.references import EntityReference, normalize_entity_kind
from pycrmkit.leads import Lead, LeadId, LeadStatus
from pycrmkit.opportunities import Opportunity, OpportunityId, OpportunityStatus
from pycrmkit.organizations import UNSET as ORGANIZATION_UNSET
from pycrmkit.organizations import (
    Organization,
    OrganizationAddress,
    OrganizationDomain,
    OrganizationId,
    OrganizationStatus,
    OrganizationUpdate,
)
from pycrmkit.relationships import UNSET as RELATIONSHIP_UNSET
from pycrmkit.relationships import (
    Relationship,
    RelationshipEndpoint,
    RelationshipEntityKind,
    RelationshipType,
    RelationshipUpdate,
)
from pycrmkit.tasks import UNSET as TASK_UNSET
from pycrmkit.tasks import Task, TaskId, TaskPriority, TaskStatus, TaskUpdate
from pycrmkit.timeline import TimelineEntry, TimelineEntryId


class APIModel(BaseModel):
    """Strict base class for FastAPI request/response schemas."""

    model_config = ConfigDict(extra="forbid")


class _ContactCreateKwargs(TypedDict):
    first_name: str | None
    last_name: str | None
    display_name: str | None
    status: ContactStatus
    owner_id: EntityId | None
    source: str | None
    emails: tuple[ContactEmail, ...]
    phones: tuple[ContactPhone, ...]
    addresses: tuple[Address, ...]
    metadata: dict[str, Any]


class _OrganizationCreateKwargs(TypedDict):
    legal_name: str
    trading_name: str | None
    display_name: str | None
    registration_number: str | None
    tax_id: str | None
    status: OrganizationStatus
    owner_id: EntityId | None
    source: str | None
    domains: tuple[OrganizationDomain, ...]
    addresses: tuple[OrganizationAddress, ...]
    metadata: dict[str, Any]


class _RelationshipCreateKwargs(TypedDict):
    source: RelationshipEndpoint
    target: RelationshipEndpoint
    relationship_type: RelationshipType
    role: str | None
    title: str | None
    is_primary: bool
    valid_from: datetime | None
    valid_until: datetime | None
    metadata: dict[str, Any]


class _ActivityCreateKwargs(TypedDict):
    type: ActivityType
    occurred_at: datetime | None
    subject: str | None
    description: str | None
    direction: ActivityDirection | None
    duration_seconds: int | None
    participants: tuple[ActivityParticipant, ...]
    references: tuple[EntityReference, ...]
    source: str | None
    external_id: str | None
    metadata: dict[str, Any]


class _TaskCreateKwargs(TypedDict):
    title: str
    description: str | None
    priority: TaskPriority
    due_at: datetime | None
    owner_id: str | None
    assignee_id: str | None
    references: tuple[EntityReference, ...]
    source: str | None
    external_id: str | None
    metadata: dict[str, Any]


class _LeadCreateKwargs(TypedDict):
    contact_id: ContactId
    organization_id: OrganizationId | None
    source: str | None


class _LeadConversionKwargs(TypedDict):
    name: str | None
    estimated_value: Decimal | None
    currency: str | None
    pipeline_id: str | None
    expected_close_date: date | None
    owner_id: str | None
    idempotency_key: str | None


class _OpportunityCreateKwargs(TypedDict):
    name: str
    contact_id: ContactId
    organization_id: OrganizationId | None
    pipeline_id: str | None
    stage_id: str | None
    estimated_value: Decimal | None
    currency: str | None
    probability: Decimal | None
    expected_close_date: date | None
    owner_id: str | None


class EntityReferenceSchema(APIModel):
    """HTTP representation of a generic PyCRMKit entity reference."""

    kind: str
    id: UUID

    def to_domain(self) -> EntityReference:
        kind = normalize_entity_kind(self.kind)
        id_type: type[UUIDId] = {
            "contact": ContactId,
            "organization": OrganizationId,
            "activity": ActivityId,
            "task": TaskId,
            "lead": LeadId,
            "opportunity": OpportunityId,
            "timeline_entry": TimelineEntryId,
        }.get(kind, UUIDId)
        return EntityReference(kind=kind, id=id_type(self.id))

    @classmethod
    def from_domain(cls, value: EntityReference) -> EntityReferenceSchema:
        return cls(kind=value.kind, id=value.id.value)


class ContactEmailSchema(APIModel):
    value: str
    is_primary: bool = False
    verification: VerificationState = VerificationState.UNKNOWN

    def to_domain(self) -> ContactEmail:
        return ContactEmail(
            self.value,
            is_primary=self.is_primary,
            verification=self.verification,
        )

    @classmethod
    def from_domain(cls, value: ContactEmail) -> ContactEmailSchema:
        return cls(
            value=value.value,
            is_primary=value.is_primary,
            verification=value.verification,
        )


class ContactPhoneSchema(APIModel):
    value: str
    is_primary: bool = False
    verification: VerificationState = VerificationState.UNKNOWN

    def to_domain(self) -> ContactPhone:
        return ContactPhone(
            self.value,
            is_primary=self.is_primary,
            verification=self.verification,
        )

    @classmethod
    def from_domain(cls, value: ContactPhone) -> ContactPhoneSchema:
        return cls(
            value=value.value,
            is_primary=value.is_primary,
            verification=value.verification,
        )


class AddressSchema(APIModel):
    line1: str
    city: str
    postal_code: str | None = None
    line2: str | None = None
    region: str | None = None
    country_code: str | None = None
    is_primary: bool = False

    def to_domain(self) -> Address:
        return Address(**self.model_dump())

    @classmethod
    def from_domain(cls, value: Address) -> AddressSchema:
        return cls(
            line1=value.line1,
            city=value.city,
            postal_code=value.postal_code,
            line2=value.line2,
            region=value.region,
            country_code=value.country_code,
            is_primary=value.is_primary,
        )


class ContactCreateRequest(APIModel):
    first_name: str | None = None
    last_name: str | None = None
    display_name: str | None = None
    status: ContactStatus = ContactStatus.ACTIVE
    owner_id: UUID | None = None
    source: str | None = None
    emails: list[ContactEmailSchema] = Field(default_factory=list)
    phones: list[ContactPhoneSchema] = Field(default_factory=list)
    addresses: list[AddressSchema] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_domain_kwargs(self) -> _ContactCreateKwargs:
        return {
            "first_name": self.first_name,
            "last_name": self.last_name,
            "display_name": self.display_name,
            "status": self.status,
            "owner_id": EntityId(self.owner_id) if self.owner_id is not None else None,
            "source": self.source,
            "emails": tuple(item.to_domain() for item in self.emails),
            "phones": tuple(item.to_domain() for item in self.phones),
            "addresses": tuple(item.to_domain() for item in self.addresses),
            "metadata": dict(self.metadata),
        }


class ContactUpdateRequest(APIModel):
    first_name: str | None = None
    last_name: str | None = None
    display_name: str | None = None
    status: ContactStatus | None = None
    owner_id: UUID | None = None
    source: str | None = None
    emails: list[ContactEmailSchema] | None = None
    phones: list[ContactPhoneSchema] | None = None
    addresses: list[AddressSchema] | None = None
    metadata: dict[str, Any] | None = None

    @model_validator(mode="after")
    def _validate_non_nullable_fields(self) -> Self:
        if "status" in self.model_fields_set and self.status is None:
            raise ValueError("status cannot be null")
        return self

    def to_domain(self) -> ContactUpdate:
        fields = self.model_fields_set
        return ContactUpdate(
            first_name=self.first_name if "first_name" in fields else CONTACT_UNSET,
            last_name=self.last_name if "last_name" in fields else CONTACT_UNSET,
            display_name=(
                self.display_name if "display_name" in fields else CONTACT_UNSET
            ),
            status=self.status if self.status is not None else CONTACT_UNSET,
            owner_id=(
                EntityId(self.owner_id) if self.owner_id is not None else None
            )
            if "owner_id" in fields
            else CONTACT_UNSET,
            source=self.source if "source" in fields else CONTACT_UNSET,
            emails=(
                tuple(item.to_domain() for item in (self.emails or []))
                if "emails" in fields
                else CONTACT_UNSET
            ),
            phones=(
                tuple(item.to_domain() for item in (self.phones or []))
                if "phones" in fields
                else CONTACT_UNSET
            ),
            addresses=(
                tuple(item.to_domain() for item in (self.addresses or []))
                if "addresses" in fields
                else CONTACT_UNSET
            ),
            metadata=(
                dict(self.metadata or {})
                if "metadata" in fields
                else CONTACT_UNSET
            ),
        )


class ContactResponse(APIModel):
    id: UUID
    created_at: datetime
    updated_at: datetime
    first_name: str | None
    last_name: str | None
    display_name: str | None
    status: ContactStatus
    owner_id: UUID | None
    source: str | None
    emails: list[ContactEmailSchema]
    phones: list[ContactPhoneSchema]
    addresses: list[AddressSchema]
    metadata: dict[str, Any]
    archived_at: datetime | None

    @classmethod
    def from_domain(cls, value: Contact) -> ContactResponse:
        return cls(
            id=value.id.value,
            created_at=value.created_at,
            updated_at=value.updated_at,
            first_name=value.first_name,
            last_name=value.last_name,
            display_name=value.display_name,
            status=value.status,
            owner_id=value.owner_id.value if value.owner_id is not None else None,
            source=value.source,
            emails=[ContactEmailSchema.from_domain(item) for item in value.emails],
            phones=[ContactPhoneSchema.from_domain(item) for item in value.phones],
            addresses=[AddressSchema.from_domain(item) for item in value.addresses],
            metadata=dict(value.metadata),
            archived_at=value.archived_at,
        )


class OrganizationDomainSchema(APIModel):
    value: str
    is_primary: bool = False

    def to_domain(self) -> OrganizationDomain:
        return OrganizationDomain(self.value, is_primary=self.is_primary)

    @classmethod
    def from_domain(cls, value: OrganizationDomain) -> OrganizationDomainSchema:
        return cls(value=value.value, is_primary=value.is_primary)


class OrganizationAddressSchema(APIModel):
    line1: str
    city: str
    postal_code: str | None = None
    line2: str | None = None
    region: str | None = None
    country_code: str | None = None
    is_primary: bool = False

    def to_domain(self) -> OrganizationAddress:
        return OrganizationAddress(**self.model_dump())

    @classmethod
    def from_domain(cls, value: OrganizationAddress) -> OrganizationAddressSchema:
        return cls(
            line1=value.line1,
            city=value.city,
            postal_code=value.postal_code,
            line2=value.line2,
            region=value.region,
            country_code=value.country_code,
            is_primary=value.is_primary,
        )


class OrganizationCreateRequest(APIModel):
    legal_name: str
    trading_name: str | None = None
    display_name: str | None = None
    registration_number: str | None = None
    tax_id: str | None = None
    status: OrganizationStatus = OrganizationStatus.ACTIVE
    owner_id: UUID | None = None
    source: str | None = None
    domains: list[OrganizationDomainSchema] = Field(default_factory=list)
    addresses: list[OrganizationAddressSchema] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_domain_kwargs(self) -> _OrganizationCreateKwargs:
        return {
            "legal_name": self.legal_name,
            "trading_name": self.trading_name,
            "display_name": self.display_name,
            "registration_number": self.registration_number,
            "tax_id": self.tax_id,
            "status": self.status,
            "owner_id": EntityId(self.owner_id) if self.owner_id is not None else None,
            "source": self.source,
            "domains": tuple(item.to_domain() for item in self.domains),
            "addresses": tuple(item.to_domain() for item in self.addresses),
            "metadata": dict(self.metadata),
        }


class OrganizationUpdateRequest(APIModel):
    legal_name: str | None = None
    trading_name: str | None = None
    display_name: str | None = None
    registration_number: str | None = None
    tax_id: str | None = None
    status: OrganizationStatus | None = None
    owner_id: UUID | None = None
    source: str | None = None
    domains: list[OrganizationDomainSchema] | None = None
    addresses: list[OrganizationAddressSchema] | None = None
    metadata: dict[str, Any] | None = None

    @model_validator(mode="after")
    def _validate_non_nullable_fields(self) -> Self:
        for name in ("legal_name", "status"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self

    def to_domain(self) -> OrganizationUpdate:
        fields = self.model_fields_set
        return OrganizationUpdate(
            legal_name=(
                self.legal_name if self.legal_name is not None else ORGANIZATION_UNSET
            ),
            trading_name=(
                self.trading_name if "trading_name" in fields else ORGANIZATION_UNSET
            ),
            display_name=(
                self.display_name if "display_name" in fields else ORGANIZATION_UNSET
            ),
            registration_number=(
                self.registration_number
                if "registration_number" in fields
                else ORGANIZATION_UNSET
            ),
            tax_id=self.tax_id if "tax_id" in fields else ORGANIZATION_UNSET,
            status=self.status if self.status is not None else ORGANIZATION_UNSET,
            owner_id=(
                EntityId(self.owner_id) if self.owner_id is not None else None
            )
            if "owner_id" in fields
            else ORGANIZATION_UNSET,
            source=self.source if "source" in fields else ORGANIZATION_UNSET,
            domains=(
                tuple(item.to_domain() for item in (self.domains or []))
                if "domains" in fields
                else ORGANIZATION_UNSET
            ),
            addresses=(
                tuple(item.to_domain() for item in (self.addresses or []))
                if "addresses" in fields
                else ORGANIZATION_UNSET
            ),
            metadata=(
                dict(self.metadata or {})
                if "metadata" in fields
                else ORGANIZATION_UNSET
            ),
        )


class OrganizationResponse(APIModel):
    id: UUID
    created_at: datetime
    updated_at: datetime
    legal_name: str
    trading_name: str | None
    display_name: str | None
    registration_number: str | None
    tax_id: str | None
    status: OrganizationStatus
    owner_id: UUID | None
    source: str | None
    domains: list[OrganizationDomainSchema]
    addresses: list[OrganizationAddressSchema]
    metadata: dict[str, Any]
    archived_at: datetime | None

    @classmethod
    def from_domain(cls, value: Organization) -> OrganizationResponse:
        return cls(
            id=value.id.value,
            created_at=value.created_at,
            updated_at=value.updated_at,
            legal_name=value.legal_name,
            trading_name=value.trading_name,
            display_name=value.display_name,
            registration_number=value.registration_number,
            tax_id=value.tax_id,
            status=value.status,
            owner_id=value.owner_id.value if value.owner_id is not None else None,
            source=value.source,
            domains=[OrganizationDomainSchema.from_domain(item) for item in value.domains],
            addresses=[
                OrganizationAddressSchema.from_domain(item) for item in value.addresses
            ],
            metadata=dict(value.metadata),
            archived_at=value.archived_at,
        )


class RelationshipEndpointSchema(APIModel):
    kind: RelationshipEntityKind
    id: UUID

    def to_domain(self) -> RelationshipEndpoint:
        if self.kind is RelationshipEntityKind.CONTACT:
            return RelationshipEndpoint.contact(ContactId(self.id))
        return RelationshipEndpoint.organization(OrganizationId(self.id))

    @classmethod
    def from_domain(cls, value: RelationshipEndpoint) -> RelationshipEndpointSchema:
        return cls(kind=value.kind, id=value.id.value)


class RelationshipCreateRequest(APIModel):
    source: RelationshipEndpointSchema
    target: RelationshipEndpointSchema
    relationship_type: str
    role: str | None = None
    title: str | None = None
    is_primary: bool = False
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_domain_kwargs(self) -> _RelationshipCreateKwargs:
        return {
            "source": self.source.to_domain(),
            "target": self.target.to_domain(),
            "relationship_type": RelationshipType(self.relationship_type),
            "role": self.role,
            "title": self.title,
            "is_primary": self.is_primary,
            "valid_from": self.valid_from,
            "valid_until": self.valid_until,
            "metadata": dict(self.metadata),
        }


class RelationshipUpdateRequest(APIModel):
    source: RelationshipEndpointSchema | None = None
    target: RelationshipEndpointSchema | None = None
    relationship_type: str | None = None
    role: str | None = None
    title: str | None = None
    is_primary: bool | None = None
    valid_from: datetime | None = None
    metadata: dict[str, Any] | None = None

    @model_validator(mode="after")
    def _validate_non_nullable_fields(self) -> Self:
        for name in (
            "source",
            "target",
            "relationship_type",
            "is_primary",
            "valid_from",
        ):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self

    def to_domain(self) -> RelationshipUpdate:
        fields = self.model_fields_set
        return RelationshipUpdate(
            source=(
                self.source.to_domain()
                if self.source is not None
                else RELATIONSHIP_UNSET
            ),
            target=(
                self.target.to_domain()
                if self.target is not None
                else RELATIONSHIP_UNSET
            ),
            relationship_type=(
                RelationshipType(self.relationship_type)
                if self.relationship_type is not None
                else RELATIONSHIP_UNSET
            ),
            role=self.role if "role" in fields else RELATIONSHIP_UNSET,
            title=self.title if "title" in fields else RELATIONSHIP_UNSET,
            is_primary=(
                self.is_primary if self.is_primary is not None else RELATIONSHIP_UNSET
            ),
            valid_from=(
                self.valid_from if self.valid_from is not None else RELATIONSHIP_UNSET
            ),
            metadata=(
                dict(self.metadata or {})
                if "metadata" in fields
                else RELATIONSHIP_UNSET
            ),
        )


class RelationshipResponse(APIModel):
    id: UUID
    created_at: datetime
    updated_at: datetime
    source: RelationshipEndpointSchema
    target: RelationshipEndpointSchema
    relationship_type: str
    valid_from: datetime
    role: str | None
    title: str | None
    is_primary: bool
    valid_until: datetime | None
    metadata: dict[str, Any]
    is_ended: bool

    @classmethod
    def from_domain(cls, value: Relationship) -> RelationshipResponse:
        return cls(
            id=value.id.value,
            created_at=value.created_at,
            updated_at=value.updated_at,
            source=RelationshipEndpointSchema.from_domain(value.source),
            target=RelationshipEndpointSchema.from_domain(value.target),
            relationship_type=str(value.relationship_type),
            valid_from=value.valid_from,
            role=value.role,
            title=value.title,
            is_primary=value.is_primary,
            valid_until=value.valid_until,
            metadata=dict(value.metadata),
            is_ended=value.is_ended,
        )


class ActivityParticipantSchema(APIModel):
    reference: EntityReferenceSchema
    role: str | None = None
    is_primary: bool = False

    def to_domain(self) -> ActivityParticipant:
        return ActivityParticipant(
            reference=self.reference.to_domain(),
            role=self.role,
            is_primary=self.is_primary,
        )

    @classmethod
    def from_domain(cls, value: ActivityParticipant) -> ActivityParticipantSchema:
        return cls(
            reference=EntityReferenceSchema.from_domain(value.reference),
            role=value.role,
            is_primary=value.is_primary,
        )


class ActivityCreateRequest(APIModel):
    type: ActivityType
    occurred_at: datetime | None = None
    subject: str | None = None
    description: str | None = None
    direction: ActivityDirection | None = None
    duration_seconds: int | None = Field(default=None, ge=0)
    participants: list[ActivityParticipantSchema] = Field(default_factory=list)
    references: list[EntityReferenceSchema] = Field(default_factory=list)
    source: str | None = None
    external_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_domain_kwargs(self) -> _ActivityCreateKwargs:
        return {
            "type": self.type,
            "occurred_at": self.occurred_at,
            "subject": self.subject,
            "description": self.description,
            "direction": self.direction,
            "duration_seconds": self.duration_seconds,
            "participants": tuple(item.to_domain() for item in self.participants),
            "references": tuple(item.to_domain() for item in self.references),
            "source": self.source,
            "external_id": self.external_id,
            "metadata": dict(self.metadata),
        }


class ActivityUpdateRequest(APIModel):
    type: ActivityType | None = None
    occurred_at: datetime | None = None
    subject: str | None = None
    description: str | None = None
    direction: ActivityDirection | None = None
    duration_seconds: int | None = Field(default=None, ge=0)
    participants: list[ActivityParticipantSchema] | None = None
    references: list[EntityReferenceSchema] | None = None
    source: str | None = None
    external_id: str | None = None
    metadata: dict[str, Any] | None = None

    @model_validator(mode="after")
    def _validate_non_nullable_fields(self) -> Self:
        for name in ("type", "occurred_at"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self

    def to_domain(self) -> ActivityUpdate:
        fields = self.model_fields_set
        return ActivityUpdate(
            type=self.type if self.type is not None else ACTIVITY_UNSET,
            occurred_at=(
                self.occurred_at if self.occurred_at is not None else ACTIVITY_UNSET
            ),
            subject=self.subject if "subject" in fields else ACTIVITY_UNSET,
            description=(
                self.description if "description" in fields else ACTIVITY_UNSET
            ),
            direction=(
                self.direction if "direction" in fields else ACTIVITY_UNSET
            ),
            duration_seconds=(
                self.duration_seconds
                if "duration_seconds" in fields
                else ACTIVITY_UNSET
            ),
            participants=(
                tuple(item.to_domain() for item in (self.participants or []))
                if "participants" in fields
                else ACTIVITY_UNSET
            ),
            references=(
                tuple(item.to_domain() for item in (self.references or []))
                if "references" in fields
                else ACTIVITY_UNSET
            ),
            source=self.source if "source" in fields else ACTIVITY_UNSET,
            external_id=(
                self.external_id if "external_id" in fields else ACTIVITY_UNSET
            ),
            metadata=(
                dict(self.metadata or {})
                if "metadata" in fields
                else ACTIVITY_UNSET
            ),
        )


class ActivityResponse(APIModel):
    id: UUID
    created_at: datetime
    updated_at: datetime
    type: ActivityType
    occurred_at: datetime
    subject: str | None
    description: str | None
    direction: ActivityDirection | None
    duration_seconds: int | None
    participants: list[ActivityParticipantSchema]
    references: list[EntityReferenceSchema]
    source: str | None
    external_id: str | None
    metadata: dict[str, Any]

    @classmethod
    def from_domain(cls, value: Activity) -> ActivityResponse:
        return cls(
            id=value.id.value,
            created_at=value.created_at,
            updated_at=value.updated_at,
            type=value.type,
            occurred_at=value.occurred_at,
            subject=value.subject,
            description=value.description,
            direction=value.direction,
            duration_seconds=value.duration_seconds,
            participants=[
                ActivityParticipantSchema.from_domain(item) for item in value.participants
            ],
            references=[
                EntityReferenceSchema.from_domain(item) for item in value.references
            ],
            source=value.source,
            external_id=value.external_id,
            metadata=dict(value.metadata),
        )


class TaskPriorityName(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"

    def to_domain(self) -> TaskPriority:
        return {
            TaskPriorityName.LOW: TaskPriority.LOW,
            TaskPriorityName.NORMAL: TaskPriority.NORMAL,
            TaskPriorityName.HIGH: TaskPriority.HIGH,
            TaskPriorityName.URGENT: TaskPriority.URGENT,
        }[self]

    @classmethod
    def from_domain(cls, value: TaskPriority) -> TaskPriorityName:
        return cls(value.name.lower())


class TaskCreateRequest(APIModel):
    title: str
    description: str | None = None
    priority: TaskPriorityName = TaskPriorityName.NORMAL
    due_at: datetime | None = None
    owner_id: str | None = None
    assignee_id: str | None = None
    references: list[EntityReferenceSchema] = Field(default_factory=list)
    source: str | None = None
    external_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_domain_kwargs(self) -> _TaskCreateKwargs:
        return {
            "title": self.title,
            "description": self.description,
            "priority": self.priority.to_domain(),
            "due_at": self.due_at,
            "owner_id": self.owner_id,
            "assignee_id": self.assignee_id,
            "references": tuple(item.to_domain() for item in self.references),
            "source": self.source,
            "external_id": self.external_id,
            "metadata": dict(self.metadata),
        }


class TaskUpdateRequest(APIModel):
    title: str | None = None
    description: str | None = None
    priority: TaskPriorityName | None = None
    due_at: datetime | None = None
    owner_id: str | None = None
    assignee_id: str | None = None
    references: list[EntityReferenceSchema] | None = None
    source: str | None = None
    external_id: str | None = None
    metadata: dict[str, Any] | None = None

    @model_validator(mode="after")
    def _validate_non_nullable_fields(self) -> Self:
        for name in ("title", "priority"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self

    def to_domain(self) -> TaskUpdate:
        fields = self.model_fields_set
        return TaskUpdate(
            title=self.title if self.title is not None else TASK_UNSET,
            description=(
                self.description if "description" in fields else TASK_UNSET
            ),
            priority=(
                self.priority.to_domain()
                if self.priority is not None
                else TASK_UNSET
            ),
            due_at=self.due_at if "due_at" in fields else TASK_UNSET,
            owner_id=self.owner_id if "owner_id" in fields else TASK_UNSET,
            assignee_id=(
                self.assignee_id if "assignee_id" in fields else TASK_UNSET
            ),
            references=(
                tuple(item.to_domain() for item in (self.references or []))
                if "references" in fields
                else TASK_UNSET
            ),
            source=self.source if "source" in fields else TASK_UNSET,
            external_id=(
                self.external_id if "external_id" in fields else TASK_UNSET
            ),
            metadata=(
                dict(self.metadata or {})
                if "metadata" in fields
                else TASK_UNSET
            ),
        )


class TaskResponse(APIModel):
    id: UUID
    created_at: datetime
    updated_at: datetime
    title: str
    status: TaskStatus
    priority: TaskPriorityName
    description: str | None
    due_at: datetime | None
    owner_id: str | None
    assignee_id: str | None
    references: list[EntityReferenceSchema]
    source: str | None
    external_id: str | None
    metadata: dict[str, Any]
    started_at: datetime | None
    completed_at: datetime | None
    cancelled_at: datetime | None
    is_terminal: bool

    @classmethod
    def from_domain(cls, value: Task) -> TaskResponse:
        return cls(
            id=value.id.value,
            created_at=value.created_at,
            updated_at=value.updated_at,
            title=value.title,
            status=value.status,
            priority=TaskPriorityName.from_domain(value.priority),
            description=value.description,
            due_at=value.due_at,
            owner_id=value.owner_id,
            assignee_id=value.assignee_id,
            references=[
                EntityReferenceSchema.from_domain(item) for item in value.references
            ],
            source=value.source,
            external_id=value.external_id,
            metadata=dict(value.metadata),
            started_at=value.started_at,
            completed_at=value.completed_at,
            cancelled_at=value.cancelled_at,
            is_terminal=value.is_terminal,
        )


class LeadCreateRequest(APIModel):
    contact_id: UUID
    organization_id: UUID | None = None
    source: str | None = None

    def to_domain_kwargs(self) -> _LeadCreateKwargs:
        return {
            "contact_id": ContactId(self.contact_id),
            "organization_id": (
                OrganizationId(self.organization_id)
                if self.organization_id is not None
                else None
            ),
            "source": self.source,
        }


class LeadConversionRequest(APIModel):
    name: str | None = None
    estimated_value: Decimal | None = None
    currency: str | None = None
    pipeline_id: str | None = None
    expected_close_date: date | None = None
    owner_id: str | None = None
    idempotency_key: str | None = None

    def to_domain_kwargs(self) -> _LeadConversionKwargs:
        return {
            "name": self.name,
            "estimated_value": self.estimated_value,
            "currency": self.currency,
            "pipeline_id": self.pipeline_id,
            "expected_close_date": self.expected_close_date,
            "owner_id": self.owner_id,
            "idempotency_key": self.idempotency_key,
        }


class LeadResponse(APIModel):
    id: UUID
    created_at: datetime
    updated_at: datetime
    contact_id: UUID
    organization_id: UUID | None
    source: str | None
    status: LeadStatus
    converted_opportunity_id: UUID | None

    @classmethod
    def from_domain(cls, value: Lead) -> LeadResponse:
        return cls(
            id=value.id.value,
            created_at=value.created_at,
            updated_at=value.updated_at,
            contact_id=value.contact_id.value,
            organization_id=(
                value.organization_id.value
                if value.organization_id is not None
                else None
            ),
            source=value.source,
            status=value.status,
            converted_opportunity_id=(
                value.converted_opportunity_id.value
                if value.converted_opportunity_id is not None
                else None
            ),
        )


class OpportunityCreateRequest(APIModel):
    name: str
    contact_id: UUID
    organization_id: UUID | None = None
    pipeline_id: str | None = None
    stage_id: str | None = None
    estimated_value: Decimal | None = None
    currency: str | None = None
    probability: Decimal | None = None
    expected_close_date: date | None = None
    owner_id: str | None = None

    def to_domain_kwargs(self) -> _OpportunityCreateKwargs:
        return {
            "name": self.name,
            "contact_id": ContactId(self.contact_id),
            "organization_id": (
                OrganizationId(self.organization_id)
                if self.organization_id is not None
                else None
            ),
            "pipeline_id": self.pipeline_id,
            "stage_id": self.stage_id,
            "estimated_value": self.estimated_value,
            "currency": self.currency,
            "probability": self.probability,
            "expected_close_date": self.expected_close_date,
            "owner_id": self.owner_id,
        }


class OpportunityMoveRequest(APIModel):
    to: str


class OpportunityResponse(APIModel):
    id: UUID
    created_at: datetime
    updated_at: datetime
    name: str
    contact_id: UUID
    organization_id: UUID | None
    pipeline_id: str | None
    stage_id: str | None
    stage_entered_at: datetime | None
    estimated_value: Decimal | None
    currency: str | None
    probability: Decimal | None
    expected_close_date: date | None
    owner_id: str | None
    status: OpportunityStatus
    is_terminal: bool

    @classmethod
    def from_domain(cls, value: Opportunity) -> OpportunityResponse:
        return cls(
            id=value.id.value,
            created_at=value.created_at,
            updated_at=value.updated_at,
            name=value.name,
            contact_id=value.contact_id.value,
            organization_id=(
                value.organization_id.value
                if value.organization_id is not None
                else None
            ),
            pipeline_id=value.pipeline_id,
            stage_id=value.stage_id,
            stage_entered_at=value.stage_entered_at,
            estimated_value=value.estimated_value,
            currency=value.currency,
            probability=value.probability,
            expected_close_date=value.expected_close_date,
            owner_id=value.owner_id,
            status=value.status,
            is_terminal=value.is_terminal,
        )


class TimelineEntryResponse(APIModel):
    id: UUID
    kind: str
    event_type: str
    source_event_id: UUID
    entity: EntityReferenceSchema
    occurred_at: datetime
    title: str
    summary: str | None
    references: list[EntityReferenceSchema]
    actor_id: str | None
    correlation_id: str | None
    metadata: dict[str, Any]

    @classmethod
    def from_domain(cls, value: TimelineEntry) -> TimelineEntryResponse:
        return cls(
            id=value.id.value,
            kind=value.kind.value,
            event_type=str(value.event_type),
            source_event_id=value.source_event_id.value,
            entity=EntityReferenceSchema.from_domain(value.entity),
            occurred_at=value.occurred_at,
            title=value.title,
            summary=value.summary,
            references=[
                EntityReferenceSchema.from_domain(item) for item in value.references
            ],
            actor_id=value.actor_id,
            correlation_id=value.correlation_id,
            metadata=dict(value.metadata),
        )


__all__ = [
    "ActivityCreateRequest",
    "ActivityParticipantSchema",
    "ActivityResponse",
    "ActivityUpdateRequest",
    "AddressSchema",
    "ContactCreateRequest",
    "ContactEmailSchema",
    "ContactPhoneSchema",
    "ContactResponse",
    "ContactUpdateRequest",
    "EntityReferenceSchema",
    "LeadConversionRequest",
    "LeadCreateRequest",
    "LeadResponse",
    "OpportunityCreateRequest",
    "OpportunityMoveRequest",
    "OpportunityResponse",
    "OrganizationAddressSchema",
    "OrganizationCreateRequest",
    "OrganizationDomainSchema",
    "OrganizationResponse",
    "OrganizationUpdateRequest",
    "RelationshipCreateRequest",
    "RelationshipEndpointSchema",
    "RelationshipResponse",
    "RelationshipUpdateRequest",
    "TaskCreateRequest",
    "TaskPriorityName",
    "TaskResponse",
    "TaskUpdateRequest",
    "TimelineEntryResponse",
]
