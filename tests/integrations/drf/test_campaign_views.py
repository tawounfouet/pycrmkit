"""Direct DRF HTTP dispatch contracts for opt-in Campaign metadata."""

from __future__ import annotations

from collections.abc import Mapping
from types import SimpleNamespace
from typing import Any

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from pycrmkit import CRM
from pycrmkit.integrations.campaign_security import (
    CampaignPrincipal,
    CampaignSecurityBoundary,
)
from pycrmkit.integrations.django.drf.campaign_security import (
    authenticated_drf_principal,
)
from pycrmkit.integrations.django.drf.campaign_views import CampaignViewSet
from pycrmkit.integrations.django.drf.routers import create_drf_router


def _policy(*, allow_list: bool = True) -> CampaignSecurityBoundary:
    def authorize(
        principal: CampaignPrincipal,
        *,
        action: str,
        campaign_id: str | None,
        scope: Mapping[str, object] | None,
    ) -> bool:
        return principal.actor_id == "trusted-user-id" and (
            allow_list or action != "campaign.list"
        )

    return CampaignSecurityBoundary(authenticated_drf_principal, authorize)


def _send(
    method: str,
    action: str,
    path: str,
    *,
    payload: dict[str, object] | None = None,
    pk: str | None = None,
    authenticated: bool = True,
) -> Any:
    factory = APIRequestFactory()
    request = getattr(factory, method)(
        path,
        payload or {},
        format="json",
        HTTP_X_ACTOR_ID="spoofed-administrator",
        HTTP_X_CORRELATION_ID="trace-drf-123",
    )
    if authenticated:
        force_authenticate(
            request,
            user=SimpleNamespace(is_authenticated=True, pk="trusted-user-id"),
        )
    mapping = {method: action}
    if pk is None:
        return CampaignViewSet.as_view(mapping)(request)
    return CampaignViewSet.as_view(mapping)(request, pk=pk)


def test_drf_campaign_registration_remains_explicit() -> None:
    router = create_drf_router()
    assert all("campaigns" not in str(url.pattern) for url in router.urls)

    with override_settings(PYCRMKIT_CAMPAIGN_SECURITY=None):
        with pytest.raises(ImproperlyConfigured):
            create_drf_router(include_campaigns=True)

    with override_settings(PYCRMKIT_CAMPAIGN_SECURITY=_policy()):
        secured = create_drf_router(include_campaigns=True)
        assert any("campaigns" in str(url.pattern) for url in secured.urls)


def test_drf_campaign_create_read_patch_and_lifecycle() -> None:
    crm = CRM.memory(webhook_auto_delivery=False)
    with override_settings(
        PYCRMKIT_CRM_FACTORY=lambda: crm,
        PYCRMKIT_CAMPAIGN_SECURITY=_policy(),
    ):
        created = _send(
            "post",
            "create",
            "/crm/campaigns/",
            payload={
                "key": "q4-renewal",
                "name": "Q4 Renewal",
                "description": "Original",
            },
        )
        assert created.status_code == 201, created.data
        cid = str(created.data["id"])

        listed = _send("get", "list", "/crm/campaigns/")
        assert listed.status_code == 200
        assert listed.data["total"] == 1

        read = _send("get", "retrieve", f"/crm/campaigns/{cid}/", pk=cid)
        assert read.status_code == 200
        assert read.data["name"] == "Q4 Renewal"

        omitted = _send(
            "patch",
            "partial_update",
            f"/crm/campaigns/{cid}/",
            pk=cid,
            payload={"expected_revision": 1},
        )
        assert omitted.status_code == 200, omitted.data
        assert omitted.data["description"] == "Original"

        cleared = _send(
            "patch",
            "partial_update",
            f"/crm/campaigns/{cid}/",
            pk=cid,
            payload={
                "expected_revision": omitted.data["revision"],
                "description": None,
            },
        )
        assert cleared.status_code == 200, cleared.data
        assert cleared.data["description"] is None

        stale = _send(
            "patch",
            "partial_update",
            f"/crm/campaigns/{cid}/",
            pk=cid,
            payload={"expected_revision": 1, "name": "Not allowed"},
        )
        assert stale.status_code == 409, stale.data

        activated = _send(
            "post",
            "activate",
            f"/crm/campaigns/{cid}/activate/",
            pk=cid,
            payload={"expected_revision": cleared.data["revision"]},
        )
        assert activated.status_code == 200, activated.data
        assert activated.data["status"] == "active"

        completed = _send(
            "post",
            "complete",
            f"/crm/campaigns/{cid}/complete/",
            pk=cid,
            payload={"expected_revision": activated.data["revision"]},
        )
        assert completed.status_code == 200, completed.data
        assert completed.data["status"] == "completed"

        archived = _send(
            "post",
            "archive",
            f"/crm/campaigns/{cid}/archive/",
            pk=cid,
            payload={"expected_revision": completed.data["revision"]},
        )
        assert archived.status_code == 200, archived.data
        assert archived.data["status"] == "archived"


def test_drf_campaign_forged_header_denied_without_authenticated_user() -> None:
    with override_settings(
        PYCRMKIT_CRM_FACTORY=lambda: CRM.memory(webhook_auto_delivery=False),
        PYCRMKIT_CAMPAIGN_SECURITY=_policy(),
    ):
        denied = _send(
            "post",
            "create",
            "/crm/campaigns/",
            payload={"key": "q4-renewal", "name": "Renewal"},
            authenticated=False,
        )
        assert denied.status_code == 401


def test_drf_campaign_denies_list_before_count_disclosure() -> None:
    with override_settings(
        PYCRMKIT_CRM_FACTORY=lambda: CRM.memory(webhook_auto_delivery=False),
        PYCRMKIT_CAMPAIGN_SECURITY=_policy(allow_list=False),
    ):
        denied = _send("get", "list", "/crm/campaigns/")
        assert denied.status_code == 403
        assert "total" not in denied.data


def test_drf_campaign_validation_matches_fastapi_422_contract() -> None:
    crm = CRM.memory(webhook_auto_delivery=False)
    with override_settings(
        PYCRMKIT_CRM_FACTORY=lambda: crm,
        PYCRMKIT_CAMPAIGN_SECURITY=_policy(),
    ):
        created = _send(
            "post",
            "create",
            "/crm/campaigns/",
            payload={"key": "q4-renewal", "name": "Renewal"},
        )
        cid = str(created.data["id"])
        invalid = _send(
            "patch",
            "partial_update",
            f"/crm/campaigns/{cid}/",
            pk=cid,
            payload={"expected_revision": 1, "status": "active"},
        )
        assert invalid.status_code == 422, invalid.data
        missing_revision = _send(
            "post",
            "activate",
            f"/crm/campaigns/{cid}/activate/",
            pk=cid,
            payload={},
        )
        assert missing_revision.status_code == 422
