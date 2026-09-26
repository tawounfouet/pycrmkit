"""Optional Django REST Framework helpers for PyCRMKit."""

try:
    from rest_framework import serializers as _serializers  # noqa: F401
except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency guard
    raise ModuleNotFoundError(
        'Django REST Framework support requires: pip install "pycrmkit[drf]"'
    ) from exc

from pycrmkit.integrations.django.drf.errors import (
    ErrorResponseSerializer,
    pycrmkit_exception_handler,
    status_code_for_error,
)
from pycrmkit.integrations.django.drf.routers import create_drf_router
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
)
from pycrmkit.integrations.django.drf.views import (
    ContactViewSet,
    OrganizationViewSet,
    RelationshipViewSet,
)

__all__ = [
    "ContactCreateSerializer",
    "ContactResponseSerializer",
    "ContactUpdateSerializer",
    "ContactViewSet",
    "ErrorResponseSerializer",
    "OrganizationCreateSerializer",
    "OrganizationResponseSerializer",
    "OrganizationUpdateSerializer",
    "OrganizationViewSet",
    "RelationshipCreateSerializer",
    "RelationshipResponseSerializer",
    "RelationshipUpdateSerializer",
    "RelationshipViewSet",
    "create_drf_router",
    "pycrmkit_exception_handler",
    "status_code_for_error",
]
