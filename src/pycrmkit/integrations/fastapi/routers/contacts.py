"""FastAPI router for the public Contacts facade."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from pycrmkit import CRM
from pycrmkit.contacts import ContactId
from pycrmkit.integrations.fastapi.dependencies import CRMDependency
from pycrmkit.integrations.fastapi.pagination import (
    PageResponse,
    PaginationParams,
    pagination_params,
)
from pycrmkit.integrations.fastapi.schemas import (
    ContactCreateRequest,
    ContactResponse,
    ContactUpdateRequest,
)


def create_contacts_router(dependency: CRMDependency) -> APIRouter:
    """Build the Contacts router against one request-scoped CRM dependency."""

    router = APIRouter(prefix="/contacts", tags=["contacts"])

    @router.post("", response_model=ContactResponse, status_code=status.HTTP_201_CREATED)
    def create_contact(
        request: ContactCreateRequest,
        crm: Annotated[CRM, Depends(dependency)],
    ) -> ContactResponse:
        contact = crm.contacts.create(**request.to_domain_kwargs())
        return ContactResponse.from_domain(contact)

    @router.get("", response_model=PageResponse[ContactResponse])
    def list_contacts(
        crm: Annotated[CRM, Depends(dependency)],
        page: Annotated[PaginationParams, Depends(pagination_params)],
    ) -> PageResponse[ContactResponse]:
        result = crm.contacts.search(page=page.to_domain())
        return PageResponse[ContactResponse].from_page(result, ContactResponse.from_domain)

    @router.get("/{contact_id}", response_model=ContactResponse)
    def get_contact(
        contact_id: UUID,
        crm: Annotated[CRM, Depends(dependency)],
    ) -> ContactResponse:
        contact = crm.contacts.get(ContactId(contact_id))
        return ContactResponse.from_domain(contact)

    @router.patch("/{contact_id}", response_model=ContactResponse)
    def update_contact(
        contact_id: UUID,
        request: ContactUpdateRequest,
        crm: Annotated[CRM, Depends(dependency)],
    ) -> ContactResponse:
        contact = crm.contacts.update(ContactId(contact_id), request.to_domain())
        return ContactResponse.from_domain(contact)

    @router.post("/{contact_id}/archive", response_model=ContactResponse)
    def archive_contact(
        contact_id: UUID,
        crm: Annotated[CRM, Depends(dependency)],
    ) -> ContactResponse:
        contact = crm.contacts.archive(ContactId(contact_id))
        return ContactResponse.from_domain(contact)

    return router


__all__ = ["create_contacts_router"]
