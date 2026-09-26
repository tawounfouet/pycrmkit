"""FastAPI router for the public Opportunities facade."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from pycrmkit import CRM
from pycrmkit.integrations.fastapi.dependencies import CRMDependency
from pycrmkit.integrations.fastapi.schemas import (
    OpportunityCreateRequest,
    OpportunityMoveRequest,
    OpportunityResponse,
)
from pycrmkit.opportunities import OpportunityId


def create_opportunities_router(dependency: CRMDependency) -> APIRouter:
    """Build the Opportunities router without exposing repository internals."""

    router = APIRouter(prefix="/opportunities", tags=["opportunities"])

    @router.post(
        "",
        response_model=OpportunityResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def create_opportunity(
        request: OpportunityCreateRequest,
        crm: Annotated[CRM, Depends(dependency)],
    ) -> OpportunityResponse:
        opportunity = crm.opportunities.create(**request.to_domain_kwargs())
        return OpportunityResponse.from_domain(opportunity)

    @router.post("/{opportunity_id}/move", response_model=OpportunityResponse)
    def move_opportunity(
        opportunity_id: UUID,
        request: OpportunityMoveRequest,
        crm: Annotated[CRM, Depends(dependency)],
    ) -> OpportunityResponse:
        opportunity = crm.opportunities.move(
            OpportunityId(opportunity_id),
            to=request.to,
        )
        return OpportunityResponse.from_domain(opportunity)

    return router


__all__ = ["create_opportunities_router"]
