"""Authenticated Campaign request bridge for the optional Django REST Framework.

Application hosts must explicitly configure PYCRMKIT_CAMPAIGN_SECURITY. This
path never trusts an X-Actor-ID header, even if the legacy CRMViewSet does.
"""

from __future__ import annotations

from collections.abc import Mapping
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string
from rest_framework.exceptions import NotAuthenticated, PermissionDenied
from rest_framework.request import Request

from pycrmkit import CRM
from pycrmkit.integrations.campaign_security import (
    CampaignForbidden,
    CampaignPrincipal,
    CampaignSecurityBoundary,
    CampaignUnauthenticated,
    safe_campaign_correlation_id,
)
from pycrmkit.integrations.django.drf.settings import get_crm_factory

CAMPAIGN_SECURITY_SETTING = "PYCRMKIT_CAMPAIGN_SECURITY"


def authenticated_drf_principal(request: object) -> CampaignPrincipal | None:
    """Resolve the user *after* DRF authentication has evaluated request.user."""
    user = getattr(request, "user", None)
    if not getattr(user, "is_authenticated", False):
        return None
    identifier = getattr(user, "pk", None)
    if identifier is None:
        return None
    return CampaignPrincipal(actor_id=str(identifier))


def get_campaign_security() -> CampaignSecurityBoundary:
    """Require an explicit host policy; never fall back to allow-all."""
    config = getattr(settings, CAMPAIGN_SECURITY_SETTING, None)
    if isinstance(config, str):
        config = import_string(config)
    if not isinstance(config, CampaignSecurityBoundary):
        raise ImproperlyConfigured(
            f"{CAMPAIGN_SECURITY_SETTING} must be a CampaignSecurityBoundary "
            "with a verified principal resolver and authorizer"
        )
    return config


def get_campaign_crm(
    request: Request,
    *,
    action: str,
    campaign_id: str | None = None,
    scope: Mapping[str, object] | None = None,
) -> CRM:
    """Authorize an action/resource before constructing the CRM facade."""
    security = get_campaign_security()
    try:
        principal = security.require(
            request,
            action=action,
            campaign_id=campaign_id,
            scope=scope,
        )
    except CampaignUnauthenticated as exc:
        raise NotAuthenticated("Campaign authentication required") from exc
    except CampaignForbidden as exc:
        raise PermissionDenied("Campaign access denied") from exc

    correlation_id = safe_campaign_correlation_id(
        request.headers.get("X-Correlation-ID"),
        new_id=lambda: uuid4().hex,
    )
    return get_crm_factory()().with_context(
        actor_id=principal.actor_id,
        correlation_id=correlation_id,
    )


__all__ = [
    "CAMPAIGN_SECURITY_SETTING",
    "authenticated_drf_principal",
    "get_campaign_security",
    "get_campaign_crm",
]
