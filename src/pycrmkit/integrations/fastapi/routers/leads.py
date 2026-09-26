"""FastAPI router for the public Leads facade."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from pycrmkit import CRM
from pycrmkit.integrations.fastapi.dependencies import CRMDependency
from pycrmkit.integrations.fastapi.schemas import (
    LeadConversionRequest,
    LeadCreateRequest,
    LeadResponse,
    OpportunityResponse,
)
from pycrmkit.leads import LeadId


def create_leads_router(dependency: CRMDependency) -> APIRouter:
    """Build the Leads router without bypassing the public CRM facade."""

    router = APIRouter(prefix="/leads", tags=["leads"])

    @router.post("", response_model=LeadResponse, status_code=status.HTTP_201_CREATED)
    def create_lead(
        request: LeadCreateRequest,
        crm: Annotated[CRM, Depends(dependency)],
    ) -> LeadResponse:
        lead = crm.leads.create(**request.to_domain_kwargs())
        return LeadResponse.from_domain(lead)

    @router.post("/{lead_id}/qualify", response_model=LeadResponse)
    def qualify_lead(
        lead_id: UUID,
        crm: Annotated[CRM, Depends(dependency)],
    ) -> LeadResponse:
        return LeadResponse.from_domain(crm.leads.qualify(LeadId(lead_id)))

    @router.post("/{lead_id}/disqualify", response_model=LeadResponse)
    def disqualify_lead(
        lead_id: UUID,
        crm: Annotated[CRM, Depends(dependency)],
    ) -> LeadResponse:
        return LeadResponse.from_domain(crm.leads.disqualify(LeadId(lead_id)))

    @router.post("/{lead_id}/convert", response_model=OpportunityResponse)
    def convert_lead(
        lead_id: UUID,
        request: LeadConversionRequest,
        crm: Annotated[CRM, Depends(dependency)],
    ) -> OpportunityResponse:
        opportunity = crm.leads.convert(
            LeadId(lead_id),
            **request.to_domain_kwargs(),
        )
        return OpportunityResponse.from_domain(opportunity)

    return router


__all__ = ["create_leads_router"]
