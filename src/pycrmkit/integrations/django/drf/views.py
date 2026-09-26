"""Facade-backed DRF ViewSets for the initial Django CRM API surface."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from pycrmkit import CRM
from pycrmkit.contacts import ContactId
from pycrmkit.exceptions import PyCRMKitError
from pycrmkit.integrations.django.drf.errors import pycrmkit_exception_handler
from pycrmkit.integrations.django.drf.pagination import PaginationQuerySerializer, page_payload
from pycrmkit.integrations.django.drf.serializers import (
    ContactCreateSerializer,
    ContactResponseSerializer,
    ContactUpdateSerializer,
    OrganizationCreateSerializer,
    OrganizationResponseSerializer,
    OrganizationUpdateSerializer,
    RelationshipCreateSerializer,
    RelationshipResponseSerializer,
    RelationshipUpdateSerializer,
    contact_payload,
    organization_payload,
    relationship_payload,
)
from pycrmkit.integrations.django.drf.settings import get_crm_factory
from pycrmkit.organizations import OrganizationId
from pycrmkit.relationships import RelationshipId


def _uuid_pk(value: str | None) -> UUID:
    if value is None:
        raise DRFValidationError({"id": ["resource id is required"]})
    try:
        return UUID(value)
    except ValueError as exc:
        raise DRFValidationError({"id": ["must be a valid UUID"]}) from exc


class CRMViewSet(viewsets.ViewSet):
    """Base ViewSet resolving an application-owned CRM facade per request."""

    def get_crm(self, request: Request) -> CRM:
        crm = get_crm_factory()()
        actor_id = request.headers.get("X-Actor-ID")
        correlation_id = request.headers.get("X-Correlation-ID")
        if actor_id is None and correlation_id is None:
            return crm
        return crm.with_context(
            actor_id=crm.context.actor_id if actor_id is None else actor_id,
            correlation_id=(
                crm.context.correlation_id
                if correlation_id is None
                else correlation_id
            ),
        )

    def handle_exception(self, exc: Exception) -> Response:
        if isinstance(exc, PyCRMKitError | DRFValidationError):
            response = pycrmkit_exception_handler(
                exc,
                {"view": self, "request": self.request},
            )
            if response is not None:
                return response
        return super().handle_exception(exc)


class ContactViewSet(CRMViewSet):
    """CRUD/archive HTTP helper over the public Contacts facade namespace."""

    def list(self, request: Request) -> Response:
        pagination = PaginationQuerySerializer(data=request.query_params)
        pagination.is_valid(raise_exception=True)
        page = self.get_crm(request).contacts.search(page=pagination.to_domain())
        items = [
            dict(ContactResponseSerializer(contact_payload(item)).data)
            for item in page.items
        ]
        return Response(page_payload(page, items))

    def create(self, request: Request) -> Response:
        serializer = ContactCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        contact = self.get_crm(request).contacts.create(**serializer.to_domain_kwargs())
        return Response(
            ContactResponseSerializer(contact_payload(contact)).data,
            status=status.HTTP_201_CREATED,
        )

    def retrieve(self, request: Request, pk: str | None = None) -> Response:
        contact = self.get_crm(request).contacts.get(ContactId(_uuid_pk(pk)))
        return Response(ContactResponseSerializer(contact_payload(contact)).data)

    def partial_update(self, request: Request, pk: str | None = None) -> Response:
        serializer = ContactUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        contact = self.get_crm(request).contacts.update(
            ContactId(_uuid_pk(pk)),
            serializer.to_domain(),
        )
        return Response(ContactResponseSerializer(contact_payload(contact)).data)

    @action(detail=True, methods=["post"])
    def archive(self, request: Request, pk: str | None = None) -> Response:
        contact = self.get_crm(request).contacts.archive(ContactId(_uuid_pk(pk)))
        return Response(ContactResponseSerializer(contact_payload(contact)).data)


class OrganizationViewSet(CRMViewSet):
    """CRUD/archive HTTP helper over the public Organizations facade namespace."""

    def list(self, request: Request) -> Response:
        pagination = PaginationQuerySerializer(data=request.query_params)
        pagination.is_valid(raise_exception=True)
        page = self.get_crm(request).organizations.search(page=pagination.to_domain())
        items = [
            dict(OrganizationResponseSerializer(organization_payload(item)).data)
            for item in page.items
        ]
        return Response(page_payload(page, items))

    def create(self, request: Request) -> Response:
        serializer = OrganizationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        organization = self.get_crm(request).organizations.create(
            **serializer.to_domain_kwargs()
        )
        return Response(
            OrganizationResponseSerializer(organization_payload(organization)).data,
            status=status.HTTP_201_CREATED,
        )

    def retrieve(self, request: Request, pk: str | None = None) -> Response:
        organization = self.get_crm(request).organizations.get(
            OrganizationId(_uuid_pk(pk))
        )
        return Response(
            OrganizationResponseSerializer(organization_payload(organization)).data
        )

    def partial_update(self, request: Request, pk: str | None = None) -> Response:
        serializer = OrganizationUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        organization = self.get_crm(request).organizations.update(
            OrganizationId(_uuid_pk(pk)),
            serializer.to_domain(),
        )
        return Response(
            OrganizationResponseSerializer(organization_payload(organization)).data
        )

    @action(detail=True, methods=["post"])
    def archive(self, request: Request, pk: str | None = None) -> Response:
        organization = self.get_crm(request).organizations.archive(
            OrganizationId(_uuid_pk(pk))
        )
        return Response(
            OrganizationResponseSerializer(organization_payload(organization)).data
        )


class RelationshipViewSet(CRMViewSet):
    """CRUD/end HTTP helper over the public Relationships facade namespace."""

    def list(self, request: Request) -> Response:
        pagination = PaginationQuerySerializer(data=request.query_params)
        pagination.is_valid(raise_exception=True)
        page = self.get_crm(request).relationships.search(page=pagination.to_domain())
        items = [
            dict(RelationshipResponseSerializer(relationship_payload(item)).data)
            for item in page.items
        ]
        return Response(page_payload(page, items))

    def create(self, request: Request) -> Response:
        serializer = RelationshipCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        relationship = self.get_crm(request).relationships.create(
            **serializer.to_domain_kwargs()
        )
        return Response(
            RelationshipResponseSerializer(relationship_payload(relationship)).data,
            status=status.HTTP_201_CREATED,
        )

    def retrieve(self, request: Request, pk: str | None = None) -> Response:
        relationship = self.get_crm(request).relationships.get(
            RelationshipId(_uuid_pk(pk))
        )
        return Response(
            RelationshipResponseSerializer(relationship_payload(relationship)).data
        )

    def partial_update(self, request: Request, pk: str | None = None) -> Response:
        serializer = RelationshipUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        relationship = self.get_crm(request).relationships.update(
            RelationshipId(_uuid_pk(pk)),
            serializer.to_domain(),
        )
        return Response(
            RelationshipResponseSerializer(relationship_payload(relationship)).data
        )

    @action(detail=True, methods=["post"])
    def end(self, request: Request, pk: str | None = None) -> Response:
        relationship = self.get_crm(request).relationships.end(
            RelationshipId(_uuid_pk(pk))
        )
        return Response(
            RelationshipResponseSerializer(relationship_payload(relationship)).data
        )


__all__ = [
    "CRMViewSet",
    "ContactViewSet",
    "OrganizationViewSet",
    "RelationshipViewSet",
]
