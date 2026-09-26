"""Django ORM repository implementations for PyCRMKit's core CRM aggregates."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import TypeVar

from django.db.models import Model, Q, QuerySet
from django.db.models.functions import Coalesce, Concat, Lower
from django.db.models import Value

from pycrmkit.contacts import (
    Address,
    Contact,
    ContactEmail,
    ContactId,
    ContactPhone,
    ContactQuery,
    ContactStatus,
    VerificationState,
)
from pycrmkit.core.ids import EntityId
from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.core.time import as_utc
from pycrmkit.exceptions import NotFoundError
from pycrmkit.organizations import (
    Organization,
    OrganizationAddress,
    OrganizationDomain,
    OrganizationId,
    OrganizationQuery,
    OrganizationStatus,
)
from pycrmkit.relationships import (
    Relationship,
    RelationshipEndpoint,
    RelationshipEntityKind,
    RelationshipId,
    RelationshipQuery,
    RelationshipType,
)

from pycrmkit.integrations.django.models import (
    ContactAddressModel,
    ContactEmailModel,
    ContactModel,
    ContactPhoneModel,
    OrganizationAddressModel,
    OrganizationDomainModel,
    OrganizationModel,
    RelationshipModel,
)

ModelT = TypeVar("ModelT", bound=Model)
DomainT = TypeVar("DomainT")


def _page(
    queryset: QuerySet[ModelT],
    page: OffsetPageRequest,
    mapper: Callable[[ModelT], DomainT],
) -> Page[DomainT]:
    total = queryset.count()
    rows = queryset[page.offset : page.offset + page.limit]
    return Page(
        items=tuple(mapper(row) for row in rows),
        limit=page.limit,
        offset=page.offset,
        total=total,
    )


def _relationship_endpoint(kind: str, identifier: str) -> RelationshipEndpoint:
    parsed_kind = RelationshipEntityKind(kind)
    if parsed_kind is RelationshipEntityKind.CONTACT:
        return RelationshipEndpoint.contact(ContactId.parse(identifier))
    return RelationshipEndpoint.organization(OrganizationId.parse(identifier))


class DjangoContactRepository:
    """Django ORM adapter for the backend-neutral ContactRepository contract."""

    def get(self, contact_id: ContactId) -> Contact:
        contact = self.find(contact_id)
        if contact is None:
            raise NotFoundError(
                "Contact not found",
                code="contact.not_found",
                context={"contact_id": str(contact_id)},
            )
        return contact

    def find(self, contact_id: ContactId) -> Contact | None:
        model = ContactModel.objects.filter(pk=str(contact_id)).first()
        return None if model is None else self._hydrate(model)

    def save(self, contact: Contact) -> None:
        key = str(contact.id)
        ContactModel.objects.update_or_create(
            pk=key,
            defaults={
                "first_name": contact.first_name,
                "last_name": contact.last_name,
                "display_name": contact.display_name,
                "status": contact.status.value,
                "owner_id": str(contact.owner_id) if contact.owner_id is not None else None,
                "source": contact.source,
                "metadata_json": dict(contact.metadata),
                "archived_at": contact.archived_at,
                "created_at": contact.created_at,
                "updated_at": contact.updated_at,
            },
        )
        ContactEmailModel.objects.filter(contact_id=key).delete()
        ContactPhoneModel.objects.filter(contact_id=key).delete()
        ContactAddressModel.objects.filter(contact_id=key).delete()
        ContactEmailModel.objects.bulk_create(
            [
                ContactEmailModel(
                    contact_id=key,
                    position=position,
                    value=value.value,
                    normalized=value.normalized,
                    is_primary=value.is_primary,
                    verification=value.verification.value,
                )
                for position, value in enumerate(contact.emails)
            ]
        )
        ContactPhoneModel.objects.bulk_create(
            [
                ContactPhoneModel(
                    contact_id=key,
                    position=position,
                    value=value.value,
                    normalized=value.normalized,
                    is_primary=value.is_primary,
                    verification=value.verification.value,
                )
                for position, value in enumerate(contact.phones)
            ]
        )
        ContactAddressModel.objects.bulk_create(
            [
                ContactAddressModel(
                    contact_id=key,
                    position=position,
                    line1=value.line1,
                    line2=value.line2,
                    city=value.city,
                    postal_code=value.postal_code,
                    region=value.region,
                    country_code=value.country_code,
                    is_primary=value.is_primary,
                )
                for position, value in enumerate(contact.addresses)
            ]
        )

    def archive(self, contact_id: ContactId, archived_at: datetime) -> Contact:
        contact = self.get(contact_id)
        contact.archive(archived_at)
        self.save(contact)
        return contact

    def search(self, query: ContactQuery, page: OffsetPageRequest) -> Page[Contact]:
        queryset = ContactModel.objects.all()
        if not query.include_archived:
            queryset = queryset.exclude(status=ContactStatus.ARCHIVED.value)
        if query.status is not None:
            queryset = queryset.filter(status=query.status.value)
        if query.email is not None:
            queryset = queryset.filter(email_rows__normalized=query.email)
        if query.phone is not None:
            queryset = queryset.filter(phone_rows__normalized=query.phone)
        if query.name is not None:
            queryset = queryset.annotate(
                _search_name=Lower(
                    Concat(
                        Coalesce("first_name", Value("")),
                        Value(" "),
                        Coalesce("last_name", Value("")),
                        Value(" "),
                        Coalesce("display_name", Value("")),
                    )
                )
            ).filter(_search_name__contains=query.name.casefold())
        if query.owner_id is not None:
            queryset = queryset.filter(owner_id=str(query.owner_id))
        if query.source is not None:
            queryset = queryset.filter(source__iexact=query.source)
        queryset = queryset.distinct().order_by("created_at", "id")
        return _page(queryset, page, self._hydrate)

    @staticmethod
    def _hydrate(model: ContactModel) -> Contact:
        emails = model.email_rows.all().order_by("position", "id")
        phones = model.phone_rows.all().order_by("position", "id")
        addresses = model.address_rows.all().order_by("position", "id")
        return Contact(
            id=ContactId.parse(model.id),
            created_at=as_utc(model.created_at),
            updated_at=as_utc(model.updated_at),
            first_name=model.first_name,
            last_name=model.last_name,
            display_name=model.display_name,
            status=ContactStatus(model.status),
            owner_id=EntityId.parse(model.owner_id) if model.owner_id is not None else None,
            source=model.source,
            emails=tuple(
                ContactEmail(
                    row.value,
                    is_primary=row.is_primary,
                    verification=VerificationState(row.verification),
                )
                for row in emails
            ),
            phones=tuple(
                ContactPhone(
                    row.value,
                    is_primary=row.is_primary,
                    verification=VerificationState(row.verification),
                )
                for row in phones
            ),
            addresses=tuple(
                Address(
                    line1=row.line1,
                    city=row.city,
                    postal_code=row.postal_code,
                    line2=row.line2,
                    region=row.region,
                    country_code=row.country_code,
                    is_primary=row.is_primary,
                )
                for row in addresses
            ),
            metadata=dict(model.metadata_json or {}),
            archived_at=as_utc(model.archived_at) if model.archived_at is not None else None,
        )


class DjangoOrganizationRepository:
    """Django ORM adapter for the backend-neutral OrganizationRepository contract."""

    def get(self, organization_id: OrganizationId) -> Organization:
        organization = self.find(organization_id)
        if organization is None:
            raise NotFoundError(
                "Organization not found",
                code="organization.not_found",
                context={"organization_id": str(organization_id)},
            )
        return organization

    def find(self, organization_id: OrganizationId) -> Organization | None:
        model = OrganizationModel.objects.filter(pk=str(organization_id)).first()
        return None if model is None else self._hydrate(model)

    def save(self, organization: Organization) -> None:
        key = str(organization.id)
        OrganizationModel.objects.update_or_create(
            pk=key,
            defaults={
                "legal_name": organization.legal_name,
                "trading_name": organization.trading_name,
                "display_name": organization.display_name,
                "registration_number": organization.registration_number,
                "tax_id": organization.tax_id,
                "status": organization.status.value,
                "owner_id": (
                    str(organization.owner_id)
                    if organization.owner_id is not None
                    else None
                ),
                "source": organization.source,
                "metadata_json": dict(organization.metadata),
                "archived_at": organization.archived_at,
                "created_at": organization.created_at,
                "updated_at": organization.updated_at,
            },
        )
        OrganizationDomainModel.objects.filter(organization_id=key).delete()
        OrganizationAddressModel.objects.filter(organization_id=key).delete()
        OrganizationDomainModel.objects.bulk_create(
            [
                OrganizationDomainModel(
                    organization_id=key,
                    position=position,
                    value=value.value,
                    normalized=value.normalized,
                    is_primary=value.is_primary,
                )
                for position, value in enumerate(organization.domains)
            ]
        )
        OrganizationAddressModel.objects.bulk_create(
            [
                OrganizationAddressModel(
                    organization_id=key,
                    position=position,
                    line1=value.line1,
                    line2=value.line2,
                    city=value.city,
                    postal_code=value.postal_code,
                    region=value.region,
                    country_code=value.country_code,
                    is_primary=value.is_primary,
                )
                for position, value in enumerate(organization.addresses)
            ]
        )

    def archive(
        self,
        organization_id: OrganizationId,
        archived_at: datetime,
    ) -> Organization:
        organization = self.get(organization_id)
        organization.archive(archived_at)
        self.save(organization)
        return organization

    def search(
        self,
        query: OrganizationQuery,
        page: OffsetPageRequest,
    ) -> Page[Organization]:
        queryset = OrganizationModel.objects.all()
        if not query.include_archived:
            queryset = queryset.exclude(status=OrganizationStatus.ARCHIVED.value)
        if query.status is not None:
            queryset = queryset.filter(status=query.status.value)
        if query.domain is not None:
            queryset = queryset.filter(domain_rows__normalized=query.domain)
        if query.name is not None:
            queryset = queryset.annotate(
                _search_name=Lower(
                    Concat(
                        Coalesce("legal_name", Value("")),
                        Value(" "),
                        Coalesce("trading_name", Value("")),
                        Value(" "),
                        Coalesce("display_name", Value("")),
                    )
                )
            ).filter(_search_name__contains=query.name.casefold())
        if query.registration_number is not None:
            queryset = queryset.filter(
                registration_number__iexact=query.registration_number
            )
        if query.owner_id is not None:
            queryset = queryset.filter(owner_id=str(query.owner_id))
        if query.source is not None:
            queryset = queryset.filter(source__iexact=query.source)
        queryset = queryset.distinct().order_by("created_at", "id")
        return _page(queryset, page, self._hydrate)

    @staticmethod
    def _hydrate(model: OrganizationModel) -> Organization:
        domains = model.domain_rows.all().order_by("position", "id")
        addresses = model.address_rows.all().order_by("position", "id")
        return Organization(
            id=OrganizationId.parse(model.id),
            created_at=as_utc(model.created_at),
            updated_at=as_utc(model.updated_at),
            legal_name=model.legal_name,
            trading_name=model.trading_name,
            display_name=model.display_name,
            registration_number=model.registration_number,
            tax_id=model.tax_id,
            status=OrganizationStatus(model.status),
            owner_id=EntityId.parse(model.owner_id) if model.owner_id is not None else None,
            source=model.source,
            domains=tuple(
                OrganizationDomain(row.value, is_primary=row.is_primary)
                for row in domains
            ),
            addresses=tuple(
                OrganizationAddress(
                    line1=row.line1,
                    city=row.city,
                    postal_code=row.postal_code,
                    line2=row.line2,
                    region=row.region,
                    country_code=row.country_code,
                    is_primary=row.is_primary,
                )
                for row in addresses
            ),
            metadata=dict(model.metadata_json or {}),
            archived_at=as_utc(model.archived_at) if model.archived_at is not None else None,
        )


class DjangoRelationshipRepository:
    """Django ORM adapter for the backend-neutral RelationshipRepository contract."""

    def get(self, relationship_id: RelationshipId) -> Relationship:
        relationship = self.find(relationship_id)
        if relationship is None:
            raise NotFoundError(
                "Relationship not found",
                code="relationship.not_found",
                context={"relationship_id": str(relationship_id)},
            )
        return relationship

    def find(self, relationship_id: RelationshipId) -> Relationship | None:
        model = RelationshipModel.objects.filter(pk=str(relationship_id)).first()
        return None if model is None else self._hydrate(model)

    def save(self, relationship: Relationship) -> None:
        RelationshipModel.objects.update_or_create(
            pk=str(relationship.id),
            defaults={
                "source_kind": relationship.source.kind.value,
                "source_id": str(relationship.source.id),
                "target_kind": relationship.target.kind.value,
                "target_id": str(relationship.target.id),
                "relationship_type": relationship.relationship_type.code,
                "valid_from": relationship.valid_from,
                "role": relationship.role,
                "title": relationship.title,
                "is_primary": relationship.is_primary,
                "valid_until": relationship.valid_until,
                "metadata_json": dict(relationship.metadata),
                "created_at": relationship.created_at,
                "updated_at": relationship.updated_at,
            },
        )

    def end(
        self,
        relationship_id: RelationshipId,
        ended_at: datetime,
    ) -> Relationship:
        relationship = self.get(relationship_id)
        relationship.end(ended_at)
        self.save(relationship)
        return relationship

    def search(
        self,
        query: RelationshipQuery,
        page: OffsetPageRequest,
    ) -> Page[Relationship]:
        queryset = RelationshipModel.objects.all()
        if query.active_at is not None:
            queryset = queryset.filter(valid_from__lte=query.active_at).filter(
                Q(valid_until__isnull=True) | Q(valid_until__gt=query.active_at)
            )
        elif not query.include_ended:
            queryset = queryset.filter(valid_until__isnull=True)
        if query.entity is not None:
            kind = query.entity.kind.value
            identifier = str(query.entity.id)
            queryset = queryset.filter(
                Q(source_kind=kind, source_id=identifier)
                | Q(target_kind=kind, target_id=identifier)
            )
        if query.source is not None:
            queryset = queryset.filter(
                source_kind=query.source.kind.value,
                source_id=str(query.source.id),
            )
        if query.target is not None:
            queryset = queryset.filter(
                target_kind=query.target.kind.value,
                target_id=str(query.target.id),
            )
        if query.relationship_type is not None:
            queryset = queryset.filter(
                relationship_type=query.relationship_type.code
            )
        if query.is_primary is not None:
            queryset = queryset.filter(is_primary=query.is_primary)
        queryset = queryset.order_by("created_at", "id")
        return _page(queryset, page, self._hydrate)

    @staticmethod
    def _hydrate(model: RelationshipModel) -> Relationship:
        return Relationship(
            id=RelationshipId.parse(model.id),
            created_at=as_utc(model.created_at),
            updated_at=as_utc(model.updated_at),
            source=_relationship_endpoint(model.source_kind, model.source_id),
            target=_relationship_endpoint(model.target_kind, model.target_id),
            relationship_type=RelationshipType(model.relationship_type),
            valid_from=as_utc(model.valid_from),
            role=model.role,
            title=model.title,
            is_primary=model.is_primary,
            valid_until=as_utc(model.valid_until) if model.valid_until is not None else None,
            metadata=dict(model.metadata_json or {}),
        )


__all__ = [
    "DjangoContactRepository",
    "DjangoOrganizationRepository",
    "DjangoRelationshipRepository",
]
