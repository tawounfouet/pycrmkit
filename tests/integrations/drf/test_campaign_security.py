"""DRF Campaign policy wiring, request identity and negative tests."""

from __future__ import annotations

from collections.abc import Mapping
from types import SimpleNamespace

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings
from rest_framework.exceptions import NotAuthenticated, PermissionDenied
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory, force_authenticate

from pycrmkit import CRM
from pycrmkit.integrations.campaign_security import (
    CampaignPrincipal,
    CampaignSecurityBoundary,
)
from pycrmkit.integrations.django.drf.campaign_security import (
    authenticated_drf_principal,
    get_campaign_crm,
    get_campaign_security,
)


def _request(user: object | None = None) -> Request:
    request = APIRequestFactory().get(
        "/crm/campaigns/campaign-A/",
        HTTP_X_ACTOR_ID="forged-admin",
        HTTP_X_CORRELATION_ID="trace-001",
    )
    if user is not None:
        force_authenticate(request, user=user)
    return Request(request)


def _security() -> CampaignSecurityBoundary:
    def authorize(
        principal: CampaignPrincipal,
        *,
        action: str,
        campaign_id: str | None,
        scope: Mapping[str, object] | None,
    ) -> bool:
        return (
            principal.actor_id == "verified-user"
            and action == "campaign.read"
            and campaign_id == "campaign-A"
        )

    return CampaignSecurityBoundary(
        resolve_principal=authenticated_drf_principal,
        authorize=authorize,
    )


def test_drf_campaign_policy_must_be_configured_explicitly() -> None:
    with override_settings(PYCRMKIT_CAMPAIGN_SECURITY=None):
        with pytest.raises(ImproperlyConfigured):
            get_campaign_security()


def test_drf_campaign_unsigned_header_does_not_authenticate() -> None:
    factory_calls: list[str] = []

    def factory() -> CRM:
        factory_calls.append("called")
        return CRM.memory(webhook_auto_delivery=False)

    with override_settings(
        PYCRMKIT_CRM_FACTORY=factory,
        PYCRMKIT_CAMPAIGN_SECURITY=_security(),
    ):
        with pytest.raises(NotAuthenticated):
            get_campaign_crm(
                _request(),
                action="campaign.read",
                campaign_id="campaign-A",
            )
    assert factory_calls == []


def test_drf_campaign_authenticated_user_cannot_access_other_campaign() -> None:
    factory_calls: list[str] = []

    def factory() -> CRM:
        factory_calls.append("called")
        return CRM.memory(webhook_auto_delivery=False)

    user = SimpleNamespace(is_authenticated=True, pk="verified-user")
    with override_settings(
        PYCRMKIT_CRM_FACTORY=factory,
        PYCRMKIT_CAMPAIGN_SECURITY=_security(),
    ):
        with pytest.raises(PermissionDenied):
            get_campaign_crm(
                _request(user),
                action="campaign.read",
                campaign_id="campaign-B",
            )
    assert factory_calls == []


def test_drf_campaign_actor_is_bound_to_authenticated_user() -> None:
    crm = CRM.memory(webhook_auto_delivery=False)
    user = SimpleNamespace(is_authenticated=True, pk="verified-user")
    with override_settings(
        PYCRMKIT_CRM_FACTORY=lambda: crm,
        PYCRMKIT_CAMPAIGN_SECURITY=_security(),
    ):
        bound = get_campaign_crm(
            _request(user),
            action="campaign.read",
            campaign_id="campaign-A",
        )
    assert bound.context.actor_id == "verified-user"
    assert bound.context.correlation_id == "trace-001"
    assert crm.context.actor_id != "forged-admin"


def test_drf_campaign_anonymous_principal_helper_returns_none() -> None:
    assert authenticated_drf_principal(_request()) is None
