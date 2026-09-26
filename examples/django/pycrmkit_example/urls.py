"""URL configuration for the PyCRMKit Django reference application."""

from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path

from pycrmkit.integrations.django.drf import create_drf_router

router = create_drf_router()


def health(_request):
    return JsonResponse({"status": "ok", "database": "postgresql"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", health),
    path("crm/", include(router.urls)),
]
