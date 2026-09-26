"""Serializer helpers for the optional Django REST Framework bridge."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, TypedDict, cast
from uuid import UUID

from rest_framework import serializers

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
from pycrmkit.core.ids import EntityId
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

if TYPE_CHECKING:
    class _SerializerBase(serializers.Serializer[Any]):
        pass
else:
    _SerializerBase = serializers.Serializer


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
    metadata: dict[str, object]


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
    metadata: dict[str, object]


class _RelationshipCreateKwargs(TypedDict):
    source: RelationshipEndpoint
    target: RelationshipEndpoint
    relationship_type: RelationshipType
    role: str | None
    title: str | None
    is_primary: bool
    valid_from: datetime | None
    valid_until: datetime | None
    metadata: dict[str, object]


def _data(serializer: _SerializerBase) -> dict[str, Any]:
    return cast(dict[str, Any], serializer.validated_data)


def _email_from_data(data: dict[str, Any]) -> ContactEmail:
    return ContactEmail(
        cast(str, data["value"]),
        is_primary=cast(bool, data.get("is_primary", False)),
        verification=VerificationState(cast(str, data.get("verification", "unknown"))),
    )


def _phone_from_data(data: dict[str, Any]) -> ContactPhone:
    return ContactPhone(
        cast(str, data["value"]),
        is_primary=cast(bool, data.get("is_primary", False)),
        verification=VerificationState(cast(str, data.get("verification", "unknown"))),
    )


def _address_from_data(data: dict[str, Any]) -> Address:
    return Address(
        line1=cast(str, data["line1"]),
        city=cast(str, data["city"]),
        postal_code=cast(str | None, data.get("postal_code")),
        line2=cast(str | None, data.get("line2")),
        region=cast(str | None, data.get("region")),
        country_code=cast(str | None, data.get("country_code")),
        is_primary=cast(bool, data.get("is_primary", False)),
    )


def _organization_address_from_data(data: dict[str, Any]) -> OrganizationAddress:
    return OrganizationAddress(
        line1=cast(str, data["line1"]),
        city=cast(str, data["city"]),
        postal_code=cast(str | None, data.get("postal_code")),
        line2=cast(str | None, data.get("line2")),
        region=cast(str | None, data.get("region")),
        country_code=cast(str | None, data.get("country_code")),
        is_primary=cast(bool, data.get("is_primary", False)),
    )


def _endpoint_from_data(data: dict[str, Any]) -> RelationshipEndpoint:
    kind = RelationshipEntityKind(cast(str, data["kind"]))
    identifier = cast(UUID, data["id"])
    if kind is RelationshipEntityKind.CONTACT:
        return RelationshipEndpoint.contact(ContactId(identifier))
    return RelationshipEndpoint.organization(OrganizationId(identifier))


class ContactEmailSerializer(_SerializerBase):
    value = serializers.CharField(max_length=320)
    is_primary = serializers.BooleanField(required=False, default=False)
    verification = serializers.ChoiceField(
        choices=[item.value for item in VerificationState],
        required=False,
        default=VerificationState.UNKNOWN.value,
    )


class ContactPhoneSerializer(_SerializerBase):
    value = serializers.CharField(max_length=64)
    is_primary = serializers.BooleanField(required=False, default=False)
    verification = serializers.ChoiceField(
        choices=[item.value for item in VerificationState],
        required=False,
        default=VerificationState.UNKNOWN.value,
    )


class AddressSerializer(_SerializerBase):
    line1 = serializers.CharField(max_length=511)
    city = serializers.CharField(max_length=255)
    postal_code = serializers.CharField(max_length=64, required=False, allow_null=True, allow_blank=True)
    line2 = serializers.CharField(max_length=511, required=False, allow_null=True, allow_blank=True)
    region = serializers.CharField(max_length=255, required=False, allow_null=True, allow_blank=True)
    country_code = serializers.CharField(max_length=2, required=False, allow_null=True, allow_blank=True)
    is_primary = serializers.BooleanField(required=False, default=False)


class ContactCreateSerializer(_SerializerBase):
    first_name = serializers.CharField(max_length=255, required=False, allow_null=True, allow_blank=True)
    last_name = serializers.CharField(max_length=255, required=False, allow_null=True, allow_blank=True)
    display_name = serializers.CharField(max_length=511, required=False, allow_null=True, allow_blank=True)
    status = serializers.ChoiceField(
        choices=[item.value for item in ContactStatus],
        required=False,
        default=ContactStatus.ACTIVE.value,
    )
    owner_id = serializers.UUIDField(required=False, allow_null=True)
    source = serializers.CharField(max_length=255, required=False, allow_null=True, allow_blank=True)  # type: ignore[assignment]
    emails = ContactEmailSerializer(many=True, required=False, default=list)
    phones = ContactPhoneSerializer(many=True, required=False, default=list)
    addresses = AddressSerializer(many=True, required=False, default=list)
    metadata = serializers.JSONField(required=False, default=dict)

    def to_domain_kwargs(self) -> _ContactCreateKwargs:
        data = _data(self)
        owner_id = cast(UUID | None, data.get("owner_id"))
        return {
            "first_name": cast(str | None, data.get("first_name")),
            "last_name": cast(str | None, data.get("last_name")),
            "display_name": cast(str | None, data.get("display_name")),
            "status": ContactStatus(cast(str, data["status"])),
            "owner_id": EntityId(owner_id) if owner_id is not None else None,
            "source": cast(str | None, data.get("source")),
            "emails": tuple(
                _email_from_data(cast(dict[str, Any], item))
                for item in cast(list[Any], data.get("emails", []))
            ),
            "phones": tuple(
                _phone_from_data(cast(dict[str, Any], item))
                for item in cast(list[Any], data.get("phones", []))
            ),
            "addresses": tuple(
                _address_from_data(cast(dict[str, Any], item))
                for item in cast(list[Any], data.get("addresses", []))
            ),
            "metadata": cast(dict[str, object], dict(cast(dict[str, Any], data.get("metadata", {})))),
        }


class ContactUpdateSerializer(_SerializerBase):
    first_name = serializers.CharField(max_length=255, required=False, allow_null=True, allow_blank=True)
    last_name = serializers.CharField(max_length=255, required=False, allow_null=True, allow_blank=True)
    display_name = serializers.CharField(max_length=511, required=False, allow_null=True, allow_blank=True)
    status = serializers.ChoiceField(
        choices=[item.value for item in ContactStatus],
        required=False,
        allow_null=False,
    )
    owner_id = serializers.UUIDField(required=False, allow_null=True)
    source = serializers.CharField(max_length=255, required=False, allow_null=True, allow_blank=True)  # type: ignore[assignment]
    emails = ContactEmailSerializer(many=True, required=False, allow_null=False)
    phones = ContactPhoneSerializer(many=True, required=False, allow_null=False)
    addresses = AddressSerializer(many=True, required=False, allow_null=False)
    metadata = serializers.JSONField(required=False, allow_null=False)

    def to_domain(self) -> ContactUpdate:
        data = _data(self)
        owner_id = cast(UUID | None, data.get("owner_id"))
        return ContactUpdate(
            first_name=cast(str | None, data["first_name"]) if "first_name" in data else CONTACT_UNSET,
            last_name=cast(str | None, data["last_name"]) if "last_name" in data else CONTACT_UNSET,
            display_name=cast(str | None, data["display_name"]) if "display_name" in data else CONTACT_UNSET,
            status=ContactStatus(cast(str, data["status"])) if "status" in data else CONTACT_UNSET,
            owner_id=(EntityId(owner_id) if owner_id is not None else None) if "owner_id" in data else CONTACT_UNSET,
            source=cast(str | None, data["source"]) if "source" in data else CONTACT_UNSET,
            emails=tuple(
                _email_from_data(cast(dict[str, Any], item))
                for item in cast(list[Any], data["emails"])
            ) if "emails" in data else CONTACT_UNSET,
            phones=tuple(
                _phone_from_data(cast(dict[str, Any], item))
                for item in cast(list[Any], data["phones"])
            ) if "phones" in data else CONTACT_UNSET,
            addresses=tuple(
                _address_from_data(cast(dict[str, Any], item))
                for item in cast(list[Any], data["addresses"])
            ) if "addresses" in data else CONTACT_UNSET,
            metadata=cast(dict[str, object], dict(cast(dict[str, Any], data["metadata"]))) if "metadata" in data else CONTACT_UNSET,
        )


class ContactResponseSerializer(_SerializerBase):
    id = serializers.UUIDField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()
    first_name = serializers.CharField(allow_null=True)
    last_name = serializers.CharField(allow_null=True)
    display_name = serializers.CharField(allow_null=True)
    status = serializers.ChoiceField(choices=[item.value for item in ContactStatus])
    owner_id = serializers.UUIDField(allow_null=True)
    source = serializers.CharField(allow_null=True)  # type: ignore[assignment]
    emails = ContactEmailSerializer(many=True)
    phones = ContactPhoneSerializer(many=True)
    addresses = AddressSerializer(many=True)
    metadata = serializers.JSONField()
    archived_at = serializers.DateTimeField(allow_null=True)


class OrganizationDomainSerializer(_SerializerBase):
    value = serializers.CharField(max_length=253)
    is_primary = serializers.BooleanField(required=False, default=False)


class OrganizationAddressSerializer(_SerializerBase):
    line1 = serializers.CharField(max_length=511)
    city = serializers.CharField(max_length=255)
    postal_code = serializers.CharField(max_length=64, required=False, allow_null=True, allow_blank=True)
    line2 = serializers.CharField(max_length=511, required=False, allow_null=True, allow_blank=True)
    region = serializers.CharField(max_length=255, required=False, allow_null=True, allow_blank=True)
    country_code = serializers.CharField(max_length=2, required=False, allow_null=True, allow_blank=True)
    is_primary = serializers.BooleanField(required=False, default=False)


class OrganizationCreateSerializer(_SerializerBase):
    legal_name = serializers.CharField(max_length=511)
    trading_name = serializers.CharField(max_length=511, required=False, allow_null=True, allow_blank=True)
    display_name = serializers.CharField(max_length=511, required=False, allow_null=True, allow_blank=True)
    registration_number = serializers.CharField(max_length=255, required=False, allow_null=True, allow_blank=True)
    tax_id = serializers.CharField(max_length=255, required=False, allow_null=True, allow_blank=True)
    status = serializers.ChoiceField(
        choices=[item.value for item in OrganizationStatus],
        required=False,
        default=OrganizationStatus.ACTIVE.value,
    )
    owner_id = serializers.UUIDField(required=False, allow_null=True)
    source = serializers.CharField(max_length=255, required=False, allow_null=True, allow_blank=True)  # type: ignore[assignment]
    domains = OrganizationDomainSerializer(many=True, required=False, default=list)
    addresses = OrganizationAddressSerializer(many=True, required=False, default=list)
    metadata = serializers.JSONField(required=False, default=dict)

    def to_domain_kwargs(self) -> _OrganizationCreateKwargs:
        data = _data(self)
        owner_id = cast(UUID | None, data.get("owner_id"))
        return {
            "legal_name": cast(str, data["legal_name"]),
            "trading_name": cast(str | None, data.get("trading_name")),
            "display_name": cast(str | None, data.get("display_name")),
            "registration_number": cast(str | None, data.get("registration_number")),
            "tax_id": cast(str | None, data.get("tax_id")),
            "status": OrganizationStatus(cast(str, data["status"])),
            "owner_id": EntityId(owner_id) if owner_id is not None else None,
            "source": cast(str | None, data.get("source")),
            "domains": tuple(
                OrganizationDomain(
                    cast(str, cast(dict[str, Any], item)["value"]),
                    is_primary=cast(bool, cast(dict[str, Any], item).get("is_primary", False)),
                )
                for item in cast(list[Any], data.get("domains", []))
            ),
            "addresses": tuple(
                _organization_address_from_data(cast(dict[str, Any], item))
                for item in cast(list[Any], data.get("addresses", []))
            ),
            "metadata": cast(dict[str, object], dict(cast(dict[str, Any], data.get("metadata", {})))),
        }


class OrganizationUpdateSerializer(_SerializerBase):
    legal_name = serializers.CharField(max_length=511, required=False, allow_null=False)
    trading_name = serializers.CharField(max_length=511, required=False, allow_null=True, allow_blank=True)
    display_name = serializers.CharField(max_length=511, required=False, allow_null=True, allow_blank=True)
    registration_number = serializers.CharField(max_length=255, required=False, allow_null=True, allow_blank=True)
    tax_id = serializers.CharField(max_length=255, required=False, allow_null=True, allow_blank=True)
    status = serializers.ChoiceField(
        choices=[item.value for item in OrganizationStatus],
        required=False,
        allow_null=False,
    )
    owner_id = serializers.UUIDField(required=False, allow_null=True)
    source = serializers.CharField(max_length=255, required=False, allow_null=True, allow_blank=True)  # type: ignore[assignment]
    domains = OrganizationDomainSerializer(many=True, required=False, allow_null=False)
    addresses = OrganizationAddressSerializer(many=True, required=False, allow_null=False)
    metadata = serializers.JSONField(required=False, allow_null=False)

    def to_domain(self) -> OrganizationUpdate:
        data = _data(self)
        owner_id = cast(UUID | None, data.get("owner_id"))
        return OrganizationUpdate(
            legal_name=cast(str, data["legal_name"]) if "legal_name" in data else ORGANIZATION_UNSET,
            trading_name=cast(str | None, data["trading_name"]) if "trading_name" in data else ORGANIZATION_UNSET,
            display_name=cast(str | None, data["display_name"]) if "display_name" in data else ORGANIZATION_UNSET,
            registration_number=cast(str | None, data["registration_number"]) if "registration_number" in data else ORGANIZATION_UNSET,
            tax_id=cast(str | None, data["tax_id"]) if "tax_id" in data else ORGANIZATION_UNSET,
            status=OrganizationStatus(cast(str, data["status"])) if "status" in data else ORGANIZATION_UNSET,
            owner_id=(EntityId(owner_id) if owner_id is not None else None) if "owner_id" in data else ORGANIZATION_UNSET,
            source=cast(str | None, data["source"]) if "source" in data else ORGANIZATION_UNSET,
            domains=tuple(
                OrganizationDomain(
                    cast(str, cast(dict[str, Any], item)["value"]),
                    is_primary=cast(bool, cast(dict[str, Any], item).get("is_primary", False)),
                )
                for item in cast(list[Any], data["domains"])
            ) if "domains" in data else ORGANIZATION_UNSET,
            addresses=tuple(
                _organization_address_from_data(cast(dict[str, Any], item))
                for item in cast(list[Any], data["addresses"])
            ) if "addresses" in data else ORGANIZATION_UNSET,
            metadata=cast(dict[str, object], dict(cast(dict[str, Any], data["metadata"]))) if "metadata" in data else ORGANIZATION_UNSET,
        )


class OrganizationResponseSerializer(_SerializerBase):
    id = serializers.UUIDField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()
    legal_name = serializers.CharField()
    trading_name = serializers.CharField(allow_null=True)
    display_name = serializers.CharField(allow_null=True)
    registration_number = serializers.CharField(allow_null=True)
    tax_id = serializers.CharField(allow_null=True)
    status = serializers.ChoiceField(choices=[item.value for item in OrganizationStatus])
    owner_id = serializers.UUIDField(allow_null=True)
    source = serializers.CharField(allow_null=True)  # type: ignore[assignment]
    domains = OrganizationDomainSerializer(many=True)
    addresses = OrganizationAddressSerializer(many=True)
    metadata = serializers.JSONField()
    archived_at = serializers.DateTimeField(allow_null=True)


class RelationshipEndpointSerializer(_SerializerBase):
    kind = serializers.ChoiceField(choices=[item.value for item in RelationshipEntityKind])
    id = serializers.UUIDField()


class RelationshipCreateSerializer(_SerializerBase):
    source = RelationshipEndpointSerializer()  # type: ignore[assignment]
    target = RelationshipEndpointSerializer()
    relationship_type = serializers.CharField(max_length=80)
    role = serializers.CharField(max_length=255, required=False, allow_null=True, allow_blank=True)
    title = serializers.CharField(max_length=255, required=False, allow_null=True, allow_blank=True)
    is_primary = serializers.BooleanField(required=False, default=False)
    valid_from = serializers.DateTimeField(required=False, allow_null=True)
    valid_until = serializers.DateTimeField(required=False, allow_null=True)
    metadata = serializers.JSONField(required=False, default=dict)

    def to_domain_kwargs(self) -> _RelationshipCreateKwargs:
        data = _data(self)
        return {
            "source": _endpoint_from_data(cast(dict[str, Any], data["source"])),
            "target": _endpoint_from_data(cast(dict[str, Any], data["target"])),
            "relationship_type": RelationshipType(cast(str, data["relationship_type"])),
            "role": cast(str | None, data.get("role")),
            "title": cast(str | None, data.get("title")),
            "is_primary": cast(bool, data.get("is_primary", False)),
            "valid_from": cast(datetime | None, data.get("valid_from")),
            "valid_until": cast(datetime | None, data.get("valid_until")),
            "metadata": cast(dict[str, object], dict(cast(dict[str, Any], data.get("metadata", {})))),
        }


class RelationshipUpdateSerializer(_SerializerBase):
    source = RelationshipEndpointSerializer(required=False, allow_null=False)  # type: ignore[assignment]
    target = RelationshipEndpointSerializer(required=False, allow_null=False)
    relationship_type = serializers.CharField(max_length=80, required=False, allow_null=False)
    role = serializers.CharField(max_length=255, required=False, allow_null=True, allow_blank=True)
    title = serializers.CharField(max_length=255, required=False, allow_null=True, allow_blank=True)
    is_primary = serializers.BooleanField(required=False, allow_null=False)
    valid_from = serializers.DateTimeField(required=False, allow_null=False)
    metadata = serializers.JSONField(required=False, allow_null=False)

    def to_domain(self) -> RelationshipUpdate:
        data = _data(self)
        return RelationshipUpdate(
            source=_endpoint_from_data(cast(dict[str, Any], data["source"])) if "source" in data else RELATIONSHIP_UNSET,
            target=_endpoint_from_data(cast(dict[str, Any], data["target"])) if "target" in data else RELATIONSHIP_UNSET,
            relationship_type=RelationshipType(cast(str, data["relationship_type"])) if "relationship_type" in data else RELATIONSHIP_UNSET,
            role=cast(str | None, data["role"]) if "role" in data else RELATIONSHIP_UNSET,
            title=cast(str | None, data["title"]) if "title" in data else RELATIONSHIP_UNSET,
            is_primary=cast(bool, data["is_primary"]) if "is_primary" in data else RELATIONSHIP_UNSET,
            valid_from=cast(datetime, data["valid_from"]) if "valid_from" in data else RELATIONSHIP_UNSET,
            metadata=cast(dict[str, object], dict(cast(dict[str, Any], data["metadata"]))) if "metadata" in data else RELATIONSHIP_UNSET,
        )


class RelationshipResponseSerializer(_SerializerBase):
    id = serializers.UUIDField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()
    source = RelationshipEndpointSerializer()
    target = RelationshipEndpointSerializer()
    relationship_type = serializers.CharField()
    valid_from = serializers.DateTimeField()
    role = serializers.CharField(allow_null=True)
    title = serializers.CharField(allow_null=True)
    is_primary = serializers.BooleanField()
    valid_until = serializers.DateTimeField(allow_null=True)
    metadata = serializers.JSONField()
    is_ended = serializers.BooleanField()


def contact_payload(value: Contact) -> dict[str, Any]:
    return {
        "id": value.id.value,
        "created_at": value.created_at,
        "updated_at": value.updated_at,
        "first_name": value.first_name,
        "last_name": value.last_name,
        "display_name": value.display_name,
        "status": value.status.value,
        "owner_id": value.owner_id.value if value.owner_id is not None else None,
        "source": value.source,
        "emails": [
            {
                "value": item.value,
                "is_primary": item.is_primary,
                "verification": item.verification.value,
            }
            for item in value.emails
        ],
        "phones": [
            {
                "value": item.value,
                "is_primary": item.is_primary,
                "verification": item.verification.value,
            }
            for item in value.phones
        ],
        "addresses": [
            {
                "line1": item.line1,
                "city": item.city,
                "postal_code": item.postal_code,
                "line2": item.line2,
                "region": item.region,
                "country_code": item.country_code,
                "is_primary": item.is_primary,
            }
            for item in value.addresses
        ],
        "metadata": dict(value.metadata),
        "archived_at": value.archived_at,
    }


def organization_payload(value: Organization) -> dict[str, Any]:
    return {
        "id": value.id.value,
        "created_at": value.created_at,
        "updated_at": value.updated_at,
        "legal_name": value.legal_name,
        "trading_name": value.trading_name,
        "display_name": value.display_name,
        "registration_number": value.registration_number,
        "tax_id": value.tax_id,
        "status": value.status.value,
        "owner_id": value.owner_id.value if value.owner_id is not None else None,
        "source": value.source,
        "domains": [
            {"value": item.value, "is_primary": item.is_primary}
            for item in value.domains
        ],
        "addresses": [
            {
                "line1": item.line1,
                "city": item.city,
                "postal_code": item.postal_code,
                "line2": item.line2,
                "region": item.region,
                "country_code": item.country_code,
                "is_primary": item.is_primary,
            }
            for item in value.addresses
        ],
        "metadata": dict(value.metadata),
        "archived_at": value.archived_at,
    }


def relationship_payload(value: Relationship) -> dict[str, Any]:
    return {
        "id": value.id.value,
        "created_at": value.created_at,
        "updated_at": value.updated_at,
        "source": {"kind": value.source.kind.value, "id": value.source.id.value},
        "target": {"kind": value.target.kind.value, "id": value.target.id.value},
        "relationship_type": str(value.relationship_type),
        "valid_from": value.valid_from,
        "role": value.role,
        "title": value.title,
        "is_primary": value.is_primary,
        "valid_until": value.valid_until,
        "metadata": dict(value.metadata),
        "is_ended": value.is_ended,
    }


__all__ = [
    "AddressSerializer",
    "ContactCreateSerializer",
    "ContactEmailSerializer",
    "ContactPhoneSerializer",
    "ContactResponseSerializer",
    "ContactUpdateSerializer",
    "OrganizationAddressSerializer",
    "OrganizationCreateSerializer",
    "OrganizationDomainSerializer",
    "OrganizationResponseSerializer",
    "OrganizationUpdateSerializer",
    "RelationshipCreateSerializer",
    "RelationshipEndpointSerializer",
    "RelationshipResponseSerializer",
    "RelationshipUpdateSerializer",
    "contact_payload",
    "organization_payload",
    "relationship_payload",
]
