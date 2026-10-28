"""LOT-31-003 - Real FastAPI/DRF Campaign JSON golden and error matrix.

This uses a shared Memory CRM and actual HTTP TestClient / rendered DRF JSON.
Dynamic UUID/timestamp *values* are normalized, never removed; no application
keys or stable values are discarded from golden comparisons.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import UUID

import pytest
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
# DRF-only extras stay importable: FastAPI is required only when executing this suite.
pytest.importorskip("fastapi.applications", reason="Cross-transport golden requires FastAPI")

GOLDEN = Path(__file__).parents[2] / "contracts/campaign_http/response_golden_v1_2.json"
_ACTOR = "rc1-actor"
_HEADERS = {"Authorization": "Bearer verified", "X-Actor-ID": "forged-admin"}


def _normalize(value: Any) -> Any:
    if isinstance(value, list):
        return [_normalize(item) for item in value]
    if not isinstance(value, dict):
        return value
    normalized: dict[str, Any] = {}
    for key, item in value.items():
        if key == "id" and isinstance(item, str):
            UUID(item)
            normalized[key] = "<uuid>"
        elif key in {"created_at", "updated_at"} and item is not None:
            assert isinstance(item, str)
            timestamp = datetime.fromisoformat(item.replace("Z", "+00:00"))
            assert timestamp.tzinfo is not None and timestamp.utcoffset() is not None
            normalized[key] = "<utc>"
        else:
            normalized[key] = _normalize(item)
    return normalized


def _client(crm: CRM, denied: list[str | None]) -> tuple[Any, CampaignSecurityBoundary]:
    from fastapi import FastAPI, Request
    from fastapi.testclient import TestClient

    from pycrmkit.integrations.fastapi import create_crm_router, install_error_handlers
    from pycrmkit.integrations.fastapi.campaign_security import CampaignHTTPAccess

    def authenticate(request: object) -> CampaignPrincipal | None:
        if isinstance(request, Request) and request.headers.get("authorization") == (
            "Bearer verified"
        ):
            return CampaignPrincipal(_ACTOR)
        return None

    def authorize(
        principal: CampaignPrincipal,
        *,
        action: str,
        campaign_id: str | None,
        scope: Mapping[str, object] | None,
    ) -> bool:
        del campaign_id, scope
        return principal.actor_id == _ACTOR and action != denied[0]

    fastapi_policy = CampaignSecurityBoundary(authenticate, authorize)
    drf_policy = CampaignSecurityBoundary(authenticated_drf_principal, authorize)
    app = FastAPI(title="Campaign RC1 HTTP Golden")
    install_error_handlers(app)
    app.include_router(
        create_crm_router(
            lambda: crm,
            campaign_access=CampaignHTTPAccess(lambda: crm, fastapi_policy),
        ),
        prefix="/crm",
    )
    return TestClient(app), drf_policy


def _drf(
    method: str,
    action: str,
    path: str,
    *,
    pk: str | None = None,
    body: dict[str, object] | None = None,
    authenticated: bool = True,
) -> tuple[int, Any]:
    request = getattr(APIRequestFactory(), method)(
        path, body or {}, format="json", HTTP_X_ACTOR_ID="forged-admin"
    )
    if authenticated:
        force_authenticate(request, user=SimpleNamespace(is_authenticated=True, pk=_ACTOR))
    kwargs = {"pk": pk} if pk is not None else {}
    response = CampaignViewSet.as_view({method: action})(request, **kwargs)
    response.render()
    return response.status_code, json.loads(response.content)


def _assert_error(value: Any, *, expected_code: str) -> None:
    assert isinstance(value, dict)
    assert set(value) == {"code", "message", "context"}, value
    assert value["code"] == expected_code
    assert isinstance(value["context"], dict)
    assert not {"total", "count", "subject", "counterparties"} & set(value)


def test_campaign_http_real_json_matches_reviewed_golden() -> None:
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    crm = CRM.memory(webhook_auto_delivery=False)
    denied: list[str | None] = [None]
    client, policy = _client(crm, denied)
    with override_settings(
        PYCRMKIT_CRM_FACTORY=lambda: crm,
        PYCRMKIT_CAMPAIGN_SECURITY=policy,
    ):
        created = client.post(
            "/crm/campaigns", headers=_HEADERS,
            json={
                "key": "rc1-http-golden",
                "name": "RC1 HTTP Golden",
                "description": "Before patch",
                "metadata": {"scenario": "lot-31-003"},
            },
        )
        assert created.status_code == 201, created.text
        assert _normalize(created.json()) == golden["campaign"]
        cid = created.json()["id"]

        fast_read = client.get(f"/crm/campaigns/{cid}", headers=_HEADERS)
        drf_status, drf_read = _drf(
            "get", "retrieve", f"/crm/campaigns/{cid}/", pk=cid
        )
        assert fast_read.status_code == drf_status == 200
        assert _normalize(fast_read.json()) == golden["campaign"]
        assert _normalize(drf_read) == golden["campaign"]

        fast_list = client.get("/crm/campaigns", headers=_HEADERS)
        drf_status, drf_list = _drf("get", "list", "/crm/campaigns/")
        assert fast_list.status_code == drf_status == 200
        assert _normalize(fast_list.json()) == golden["listing"]
        assert _normalize(drf_list) == golden["listing"]

        cleared_status, cleared = _drf(
            "patch", "partial_update", f"/crm/campaigns/{cid}/",
            pk=cid, body={"expected_revision": 1, "description": None},
        )
        assert cleared_status == 200, cleared
        assert _normalize(cleared) == golden["after_clear"]
        fast_after = client.get(f"/crm/campaigns/{cid}", headers=_HEADERS)
        assert fast_after.status_code == 200
        assert _normalize(fast_after.json()) == golden["after_clear"]


def test_campaign_http_error_status_and_code_matrix() -> None:
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    crm = CRM.memory(webhook_auto_delivery=False)
    campaign = crm.campaigns.create(key="rc1-error-golden", name="RC1 Errors")
    cid = str(campaign.id)
    missing_id = "00000000-0000-4000-8000-000000000099"
    denied: list[str | None] = [None]
    client, policy = _client(crm, denied)
    with override_settings(
        PYCRMKIT_CRM_FACTORY=lambda: crm,
        PYCRMKIT_CAMPAIGN_SECURITY=policy,
    ):
        # Forged X-Actor-ID is not a credential in either adapter.
        fast = client.get(
            f"/crm/campaigns/{cid}", headers={"X-Actor-ID": "administrator"}
        )
        drf_status, drf_data = _drf(
            "get", "retrieve", f"/crm/campaigns/{cid}/",
            pk=cid, authenticated=False,
        )
        assert fast.status_code == drf_status == golden["error_statuses"]["unauthenticated"]
        assert set(fast.json()) == set(drf_data) == {"detail"}

        denied[0] = "campaign.members.read"
        fast = client.get(f"/crm/campaigns/{cid}/audience/count", headers=_HEADERS)
        drf_status, drf_data = _drf(
            "get", "audience_count", f"/crm/campaigns/{cid}/audience/count/", pk=cid
        )
        assert fast.status_code == drf_status == golden["error_statuses"]["forbidden"]
        assert "total" not in fast.json() and "count" not in fast.json()
        assert "total" not in drf_data and "count" not in drf_data
        denied[0] = None

        fast = client.get(f"/crm/campaigns/{missing_id}", headers=_HEADERS)
        drf_status, drf_data = _drf(
            "get", "retrieve", f"/crm/campaigns/{missing_id}/", pk=missing_id
        )
        assert fast.status_code == drf_status == golden["error_statuses"]["missing"]
        for value in (fast.json(), drf_data):
            _assert_error(value, expected_code=golden["error_codes"]["missing"])

        fast = client.patch(
            f"/crm/campaigns/{cid}", headers=_HEADERS,
            json={"expected_revision": 99, "name": "Stale"},
        )
        drf_status, drf_data = _drf(
            "patch", "partial_update", f"/crm/campaigns/{cid}/", pk=cid,
            body={"expected_revision": 99, "name": "Stale"},
        )
        assert fast.status_code == drf_status == golden["error_statuses"]["stale_revision"]
        for value in (fast.json(), drf_data):
            _assert_error(value, expected_code=golden["error_codes"]["stale_revision"])

        fast = client.patch(
            f"/crm/campaigns/{cid}", headers=_HEADERS,
            json={"expected_revision": 1, "status": "active"},
        )
        drf_status, drf_data = _drf(
            "patch", "partial_update", f"/crm/campaigns/{cid}/", pk=cid,
            body={"expected_revision": 1, "status": "active"},
        )
        assert fast.status_code == drf_status == golden["error_statuses"]["invalid_patch"]
        for value in (fast.json(), drf_data):
            _assert_error(value, expected_code=golden["error_codes"]["invalid_patch"])
        assert crm.campaigns.get(campaign.id).status.value == "draft"
