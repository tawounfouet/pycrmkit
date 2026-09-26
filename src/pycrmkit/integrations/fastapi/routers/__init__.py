"""Composable FastAPI routers for the public PyCRMKit facade."""

from pycrmkit.integrations.fastapi.routers.activities import create_activities_router
from pycrmkit.integrations.fastapi.routers.contacts import create_contacts_router
from pycrmkit.integrations.fastapi.routers.leads import create_leads_router
from pycrmkit.integrations.fastapi.routers.opportunities import (
    create_opportunities_router,
)
from pycrmkit.integrations.fastapi.routers.organizations import (
    create_organizations_router,
)
from pycrmkit.integrations.fastapi.routers.relationships import (
    create_relationships_router,
)
from pycrmkit.integrations.fastapi.routers.tasks import create_tasks_router
from pycrmkit.integrations.fastapi.routers.timeline import create_timeline_router

__all__ = [
    "create_activities_router",
    "create_contacts_router",
    "create_leads_router",
    "create_opportunities_router",
    "create_organizations_router",
    "create_relationships_router",
    "create_tasks_router",
    "create_timeline_router",
]
