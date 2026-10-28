"""Opt-in Campaign HTTP E2E contract with host-authenticated FastAPI access."""

from __future__ import annotations

from collections.abc import Mapping

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from pycrmkit import CRM
from pycrmkit.integrations.campaign_security import (
    CampaignPrincipal,
    CampaignSecurityBoundary,
)
from pycrmkit.integrations.fastapi import (
    create_crm_router,
    install_error_handlers,
)
from pycrmkit.integrations.fastapi.campaign_security import CampaignHTTPAccess


def _client(
    crm: CRM,
    *,
    allow_list: bool = True,
) -> TestClient:
    def verified_identity(request: object) -> CampaignPrincipal | None:
        if (
            isinstance(request, Request)
            and request.headers.get("authorization") == "Bearer verified"
        ):
            return CampaignPrincipal("trusted-user-id")
        return None

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

    security = CampaignSecurityBoundary(verified_identity, authorize)
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(
        create_crm_router(
            lambda: crm,
            campaign_access=CampaignHTTPAccess(lambda: crm, security),
        ),
        prefix="/crm",
    )
    return TestClient(app)


def test_campaign_routes_remain_opt_in_for_existing_fastapi_integrators() -> None:
    app = FastAPI()
    app.include_router(
        create_crm_router(
            lambda: CRM.memory(webhook_auto_delivery=False)
        ),
        prefix="/crm",
    )
    assert "/crm/campaigns" not in app.openapi()["paths"]


def test_campaign_api_rejects_forged_actor_header_without_verified_identity() -> None:
    client = _client(CRM.memory(webhook_auto_delivery=False))
    response = client.post(
        "/crm/campaigns",
        headers={"X-Actor-ID": "administrator"},
        json={"key": "q4-renewal", "name": "Q4 Renewal"},
    )
    assert response.status_code == 401


def test_campaign_create_read_patch_and_lifecycle_over_memory() -> None:
    client = _client(CRM.memory(webhook_auto_delivery=False))
    headers = {
        "Authorization": "Bearer verified",
        "X-Actor-ID": "forged-admin",
    }
    created = client.post(
        "/crm/campaigns",
        headers=headers,
        json={
            "key": "q4-renewal",
            "name": "Q4 Renewal",
            "description": "Original",
            "metadata": {"source": "web"},
        },
    )
    assert created.status_code == 201, created.text
    result = created.json()
    assert result["status"] == "draft"
    assert result["revision"] == 1
    cid = result["id"]

    listed = client.get("/crm/campaigns?limit=10", headers=headers)
    assert listed.status_code == 200, listed.text
    assert listed.json()["total"] == 1

    read = client.get(f"/crm/campaigns/{cid}", headers=headers)
    assert read.status_code == 200
    assert read.json()["id"] == cid

    omitted = client.patch(
        f"/crm/campaigns/{cid}",
        headers=headers,
        json={"expected_revision": 1},
    )
    assert omitted.status_code == 200, omitted.text
    assert omitted.json()["description"] == "Original"
    current_revision = omitted.json()["revision"]

    cleared = client.patch(
        f"/crm/campaigns/{cid}",
        headers=headers,
        json={"expected_revision": current_revision, "description": None},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["description"] is None
    revision = cleared.json()["revision"]

    stale = client.patch(
        f"/crm/campaigns/{cid}",
        headers=headers,
        json={"expected_revision": 1, "name": "Invalid overwrite"},
    )
    assert stale.status_code == 409

    activated = client.post(
        f"/crm/campaigns/{cid}/activate",
        headers=headers,
        json={"expected_revision": revision},
    )
    assert activated.status_code == 200, activated.text
    assert activated.json()["status"] == "active"

    completed = client.post(
        f"/crm/campaigns/{cid}/complete",
        headers=headers,
        json={"expected_revision": activated.json()["revision"]},
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"

    archived = client.post(
        f"/crm/campaigns/{cid}/archive",
        headers=headers,
        json={"expected_revision": completed.json()["revision"]},
    )
    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"


def test_campaign_list_policy_denies_before_returning_count() -> None:
    client = _client(CRM.memory(webhook_auto_delivery=False), allow_list=False)
    response = client.get(
        "/crm/campaigns",
        headers={"Authorization": "Bearer verified"},
    )
    assert response.status_code == 403
    assert "total" not in response.json()


def test_campaign_contract_rejects_invalid_patch_and_naive_datetimes() -> None:
    client = _client(CRM.memory(webhook_auto_delivery=False))
    headers = {"Authorization": "Bearer verified"}
    created = client.post(
        "/crm/campaigns",
        headers=headers,
        json={"key": "q4-renewal", "name": "Q4 Renewal"},
    )
    assert created.status_code == 201
    cid = created.json()["id"]

    assert client.patch(
        f"/crm/campaigns/{cid}",
        headers=headers,
        json={"expected_revision": 1, "status": "active"},
    ).status_code == 422
    assert client.post(
        "/crm/campaigns",
        headers=headers,
        json={
            "key": "invalid-date",
            "name": "Invalid",
            "starts_at": "2026-10-28T17:00:00",
        },
    ).status_code == 422


def test_campaign_openapi_documents_security_errors() -> None:
    schema = _client(CRM.memory(webhook_auto_delivery=False)).get(
        "/openapi.json"
    ).json()
    operation = schema["paths"]["/crm/campaigns"]["post"]
    assert "401" in operation["responses"]
    assert "403" in operation["responses"]
