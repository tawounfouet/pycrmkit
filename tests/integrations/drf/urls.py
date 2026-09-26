"""URL configuration used by DRF integration tests."""

from django.urls import include, path

from pycrmkit.integrations.django.drf import create_drf_router

router = create_drf_router()

urlpatterns = [
    path("crm/", include(router.urls)),
]
