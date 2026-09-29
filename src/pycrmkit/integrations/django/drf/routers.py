"""Router factory for the optional facade-backed DRF integration."""

from rest_framework.routers import SimpleRouter

from pycrmkit.integrations.django.drf.segmentation_views import (
    SavedQueryViewSet,
    SegmentViewSet,
)
from pycrmkit.integrations.django.drf.views import (
    ContactViewSet,
    OrganizationViewSet,
    RelationshipViewSet,
)


def create_drf_router() -> SimpleRouter:
    """Create a reusable DRF router for the currently supported Django CRM surface."""

    router = SimpleRouter()
    router.register("contacts", ContactViewSet, basename="contact")
    router.register("organizations", OrganizationViewSet, basename="organization")
    router.register("relationships", RelationshipViewSet, basename="relationship")
    router.register("segments", SegmentViewSet, basename="segment")
    router.register("saved-queries", SavedQueryViewSet, basename="saved-query")
    return router


__all__ = ["create_drf_router"]
