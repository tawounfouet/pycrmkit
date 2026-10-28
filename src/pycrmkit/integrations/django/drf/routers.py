"""Router factory for the optional facade-backed DRF integration."""

from rest_framework.routers import SimpleRouter

from pycrmkit.integrations.django.drf.campaign_security import get_campaign_security
from pycrmkit.integrations.django.drf.campaign_views import CampaignViewSet
from pycrmkit.integrations.django.drf.segmentation_views import (
    SavedQueryViewSet,
    SegmentViewSet,
)
from pycrmkit.integrations.django.drf.views import (
    ContactViewSet,
    OrganizationViewSet,
    RelationshipViewSet,
)


def create_drf_router(*, include_campaigns: bool = False) -> SimpleRouter:
    """Create a reusable DRF router for the currently supported Django CRM surface."""

    router = SimpleRouter()
    router.register("contacts", ContactViewSet, basename="contact")
    router.register("organizations", OrganizationViewSet, basename="organization")
    router.register("relationships", RelationshipViewSet, basename="relationship")
    router.register("segments", SegmentViewSet, basename="segment")
    router.register("saved-queries", SavedQueryViewSet, basename="saved-query")
    if include_campaigns:
        get_campaign_security()  # Fail closed at route assembly, not first request.
        router.register("campaigns", CampaignViewSet, basename="campaign")
    return router


__all__ = ["create_drf_router"]
