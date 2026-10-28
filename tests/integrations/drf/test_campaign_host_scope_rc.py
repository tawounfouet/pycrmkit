"""LOT-31-004 - DRF deny-before-factory and host-owned Campaign scopes.

The test uses DRF force_authenticate (host-provided identity test double), NOT
a real identity-provider integration. Tenant authorization is host-owned.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import SimpleNamespace
from uuid import uuid4

from django.test import override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from pycrmkit import CRM
from pycrmkit.core.ids import EntityId
from pycrmkit.integrations.campaign_security import (
    CampaignPrincipal,
    CampaignSecurityBoundary,
)
from pycrmkit.integrations.django.drf.campaign_security import authenticated_drf_principal
from pycrmkit.integrations.django.drf.campaign_views import CampaignViewSet


def _state() -> tuple[CRM, dict[str, str], list[str], CampaignSecurityBoundary]:
    crm = CRM.memory(webhook_auto_delivery=False)
    owners = {"alice": EntityId(uuid4()), "bob": EntityId(uuid4())}
    alice = crm.campaigns.create(
        key="drf-security-alice", name="Alice private", owner_id=owners["alice"]
    )
    bob = crm.campaigns.create(
        key="drf-security-bob", name="Bob private", owner_id=owners["bob"]
    )
    references = {
        "alice": str(alice.id), "bob": str(bob.id),
        "owner_alice": str(owners["alice"]), "owner_bob": str(owners["bob"]),
    }
    resources = {str(alice.id): "alice", str(bob.id): "bob"}
    factory_calls: list[str] = []

    def authorizer(
        principal: CampaignPrincipal,
        *,
        action: str,
        campaign_id: str | None,
        scope: Mapping[str, object] | None,
    ) -> bool:
        actor = principal.actor_id
        if actor not in owners:
            return False
        if action == "campaign.list":
            return (
                campaign_id is None
                and scope is not None
                and scope.get("owner_id") == str(owners[actor])
                and scope.get("include_archived") is False
            )
        if action in {"campaign.read", "campaign.update", "campaign.members.read",
                      "campaign.lifecycle"}:
            return campaign_id is not None and resources.get(campaign_id) == actor
        return False

    policy = CampaignSecurityBoundary(authenticated_drf_principal, authorizer)
    return crm, references, factory_calls, policy


def _request(
    method: str,
    action: str,
    url: str,
    *,
    actor: str | None = "alice",
    pk: str | None = None,
    data: dict[str, object] | None = None,
):
    factory = APIRequestFactory()
    request = getattr(factory, method)(
        url, data or {}, format="json", HTTP_X_ACTOR_ID="forged-administrator"
    )
    if actor is not None:
        force_authenticate(
            request,
            user=SimpleNamespace(is_authenticated=True, pk=actor),
        )
    kwargs = {"pk": pk} if pk is not None else {}
    response = CampaignViewSet.as_view({method: action})(request, **kwargs)
    response.render()
    return response


def test_drf_denies_wrong_principal_resource_scope_before_factory() -> None:
    crm, refs, calls, policy = _state()

    def factory() -> CRM:
        calls.append("crm")
        return crm

    attempts = [
        ("get", "retrieve", f"/crm/campaigns/{refs['bob']}/", "alice", refs["bob"], None, 403),
        ("get", "retrieve", f"/crm/campaigns/{refs['alice']}/", "bob", refs["alice"], None, 403),
        ("get", "retrieve", f"/crm/campaigns/{refs['bob']}/", None, refs["bob"], None, 401),
        ("get", "list", "/crm/campaigns/", "alice", None, None, 403),
        ("get", "list", f"/crm/campaigns/?owner_id={refs['owner_bob']}", "alice",
         None, None, 403),
        ("get", "audience_count", f"/crm/campaigns/{refs['bob']}/audience/count/",
         "alice", refs["bob"], None, 403),
        ("get", "members", f"/crm/campaigns/{refs['bob']}/members/",
         "alice", refs["bob"], None, 403),
        ("patch", "partial_update", f"/crm/campaigns/{refs['bob']}/",
         "alice", refs["bob"], {"expected_revision": 1, "name": "tampered"}, 403),
        ("post", "create", "/crm/campaigns/", "alice", None,
         {"key": "drf-forbidden-create", "name": "no"}, 403),
    ]
    with override_settings(
        PYCRMKIT_CRM_FACTORY=factory, PYCRMKIT_CAMPAIGN_SECURITY=policy
    ):
        for method, action, path, actor, pk, payload, expected in attempts:
            before = len(calls)
            result = _request(method, action, path, actor=actor, pk=pk, data=payload)
            assert result.status_code == expected, (method, action, result.data)
            assert len(calls) == before, (method, action)
            assert "Bob private" not in str(result.data)
            assert "total" not in result.data and "count" not in result.data

    assert crm.campaigns.get(crm.campaigns.list().items[1].id).revision == 1


def test_drf_verified_actor_approved_tenant_scope() -> None:
    crm, refs, calls, policy = _state()

    def factory() -> CRM:
        calls.append("crm")
        return crm

    with override_settings(
        PYCRMKIT_CRM_FACTORY=factory, PYCRMKIT_CAMPAIGN_SECURITY=policy
    ):
        own = _request(
            "get", "retrieve", f"/crm/campaigns/{refs['alice']}/",
            actor="alice", pk=refs["alice"],
        )
        assert own.status_code == 200, own.data
        assert own.data["name"] == "Alice private"
        assert len(calls) == 1

        own_list = _request(
            "get", "list", f"/crm/campaigns/?owner_id={refs['owner_alice']}&limit=1",
            actor="alice",
        )
        assert own_list.status_code == 200, own_list.data
        assert own_list.data["total"] == 1
        assert [str(row["id"]) for row in own_list.data["items"]] == [refs["alice"]]
        assert len(calls) == 2

        # X-Actor-ID is forged, but DRF principal identity is server-controlled.
        other = _request(
            "get", "retrieve", f"/crm/campaigns/{refs['bob']}/",
            actor="bob", pk=refs["bob"],
        )
        assert other.status_code == 200, other.data
        assert other.data["name"] == "Bob private"
        assert len(calls) == 3
