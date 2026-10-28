"""Composite router factory for embedding PyCRMKit into FastAPI applications."""

from fastapi import APIRouter

from pycrmkit.integrations.fastapi.campaign_security import CampaignHTTPAccess
from pycrmkit.integrations.fastapi.dependencies import CRMDependency, CRMFactory
from pycrmkit.integrations.fastapi.routers import (
    create_activities_router,
    create_campaigns_router,
    create_contacts_router,
    create_leads_router,
    create_opportunities_router,
    create_organizations_router,
    create_relationships_router,
    create_saved_queries_router,
    create_segments_router,
    create_tasks_router,
    create_timeline_router,
)


def create_crm_router(
    factory: CRMFactory, *, campaign_access: CampaignHTTPAccess | None = None
) -> APIRouter:
    """Build the complete reusable REST surface around a CRM factory.

    The factory owns storage and application wiring. Routers receive a
    request-scoped facade through CRMDependency and never reach through the
    facade to repositories or ORM objects.
    """

    dependency = CRMDependency(factory)
    router = APIRouter()
    router.include_router(create_contacts_router(dependency))
    router.include_router(create_organizations_router(dependency))
    router.include_router(create_relationships_router(dependency))
    router.include_router(create_activities_router(dependency))
    router.include_router(create_tasks_router(dependency))
    router.include_router(create_leads_router(dependency))
    router.include_router(create_opportunities_router(dependency))
    router.include_router(create_segments_router(dependency))
    router.include_router(create_saved_queries_router(dependency))
    router.include_router(create_timeline_router(dependency))
    if campaign_access is not None:
        router.include_router(create_campaigns_router(campaign_access))
    return router


__all__ = ["create_crm_router"]
