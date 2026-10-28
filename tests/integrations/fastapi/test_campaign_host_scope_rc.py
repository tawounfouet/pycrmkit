"""LOT-31-004 - FastAPI Campaign host-verified scope qualification.

This test uses a deliberately explicit host policy: a valid bearer *fixture*
identifies a tenant-scoped actor; arbitrary actor headers never authenticate.
It tests a host-owned authorization boundary, not built-in CRM tenancy/JWT.
"""

from __future__ import annotations

from collections.abc import Mapping
from uuid import UUID, uuid4

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from pycrmkit import CRM
from pycrmkit.campaigns import CampaignId
from pycrmkit.core.ids import EntityId
from pycrmkit.core.references import EntityReference
from pycrmkit.integrations.campaign_security import (
    CampaignPrincipal,
    CampaignSecurityBoundary,
)
from pycrmkit.integrations.fastapi import create_crm_router, install_error_handlers
from pycrmkit.integrations.fastapi.campaign_security import CampaignHTTPAccess


def _host() -> tuple[TestClient, CRM, dict[str, str], list[str]]:
    crm = CRM.memory(webhook_auto_delivery=False)
    owners = {"alice": EntityId(uuid4()), "bob": EntityId(uuid4())}
    a = crm.campaigns.create(key="security-alice", name="Alice private", owner_id=owners["alice"])
    b = crm.campaigns.create(key="security-bob", name="Bob private", owner_id=owners["bob"])
    contact = crm.contacts.create(display_name="Bob contact private")
    crm.campaigns.add_member(b.id, EntityReference("contact", contact.id))
    ids = {"alice": str(a.id), "bob": str(b.id)}
    resource_tenant = {str(a.id): "alice", str(b.id): "bob"}
    factory_calls: list[str] = []

    def factory() -> CRM:
        factory_calls.append("crm")
        return crm

    def principal(request: object) -> CampaignPrincipal | None:
        if not isinstance(request, Request):
            return None
        token = request.headers.get("authorization", "")
        actors = {
            "Bearer host-signed-alice-test": "alice",
            "Bearer host-signed-bob-test": "bob",
        }
        actor = actors.get(token)
        return CampaignPrincipal(actor) if actor else None

    def allowed(
        identity: CampaignPrincipal,
        *,
        action: str,
        campaign_id: str | None,
        scope: Mapping[str, object] | None,
    ) -> bool:
        actor = identity.actor_id
        if actor not in owners:
            return False
        if action == "campaign.list":
            # Owner-only prefilter must be explicitly requested and authorized.
            # An unscoped list must not be made safe by filtering after pagination.
            return (
                campaign_id is None
                and scope is not None
                and scope.get("owner_id") == str(owners[actor])
                and scope.get("include_archived") is False
            )
        if action in {"campaign.read", "campaign.update", "campaign.members.read",
                      "campaign.members.write", "campaign.lifecycle"}:
            return campaign_id is not None and resource_tenant.get(campaign_id) == actor
        # Creation, mutation of linkage, and any unrecognized actions are denied.
        return False

    security = CampaignSecurityBoundary(principal, allowed)
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(
        create_crm_router(factory, campaign_access=CampaignHTTPAccess(factory, security)),
        prefix="/crm",
    )
    return TestClient(app), crm, {**ids, **{f"owner_{k}": str(v) for k, v in owners.items()}}, factory_calls


def _headers(actor: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer host-signed-{actor}-test",
        "X-Actor-ID": "alice" if actor == "bob" else "administrator",
    }


def test_fastapi_host_denials_never_construct_crm_or_leak_counts() -> None:
    client, crm, refs, calls = _host()
    alice, bob = refs["alice"], refs["bob"]

    attempts = [
        ("get", f"/crm/campaigns/{bob}", {"X-Actor-ID": "bob"}, None, 401),
        ("get", f"/crm/campaigns/{bob}", _headers("alice"), None, 403),
        ("get", f"/crm/campaigns/{alice}", _headers("bob"), None, 403),
        ("get", "/crm/campaigns", _headers("alice"), None, 403),
        ("get", f"/crm/campaigns?owner_id={refs['owner_bob']}", _headers("alice"), None, 403),
        ("get", f"/crm/campaigns/{bob}/audience/count", _headers("alice"), None, 403),
        ("get", f"/crm/campaigns/{bob}/members", _headers("alice"), None, 403),
        ("patch", f"/crm/campaigns/{bob}", _headers("alice"),
         {"expected_revision": 1, "name": "tampered"}, 403),
        ("post", "/crm/campaigns", _headers("alice"),
         {"key": "unauthorized-create", "name": "Never permitted"}, 403),
    ]
    for method, path, headers, payload, status in attempts:
        before = len(calls)
        response = client.request(method.upper(), path, headers=headers, json=payload)
        assert response.status_code == status, (method, path, response.text)
        assert len(calls) == before, (method, path)
        assert "Bob private" not in response.text
        assert "Bob contact private" not in response.text
        assert "count" not in response.json() and "total" not in response.json()

    assert crm.campaigns.get(CampaignId(UUID(refs["bob"]))).revision == 1


def test_fastapi_host_approved_owner_scope_and_object_read() -> None:
    client, _, refs, calls = _host()
    own = client.get(f"/crm/campaigns/{refs['alice']}", headers=_headers("alice"))
    assert own.status_code == 200
    assert own.json()["name"] == "Alice private"
    assert len(calls) == 1

    page = client.get(
        "/crm/campaigns",
        params={"owner_id": refs["owner_alice"], "limit": 1, "offset": 0},
        headers=_headers("alice"),
    )
    assert page.status_code == 200, page.text
    assert page.json()["total"] == 1
    assert [item["id"] for item in page.json()["items"]] == [refs["alice"]]
    assert len(calls) == 2

    # A verified Bob principal remains Bob even with a forged Alice actor header.
    bob = client.get(f"/crm/campaigns/{refs['bob']}", headers=_headers("bob"))
    assert bob.status_code == 200
    assert bob.json()["name"] == "Bob private"
    assert len(calls) == 3
