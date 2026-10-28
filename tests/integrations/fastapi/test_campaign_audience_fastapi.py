"""FastAPI Campaign Audience and Segment-source HTTP contract tests."""

from __future__ import annotations

from collections.abc import Mapping

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from pycrmkit import CRM
from pycrmkit.core.references import EntityReference
from pycrmkit.integrations.campaign_security import (
    CampaignPrincipal,
    CampaignSecurityBoundary,
)
from pycrmkit.integrations.fastapi import (
    create_crm_router,
    install_error_handlers,
)
from pycrmkit.integrations.fastapi.campaign_security import CampaignHTTPAccess
from pycrmkit.segments import SegmentMode


def _client(
    crm: CRM, *, forbidden_action: str | None = None,
    forbidden_campaign: str | None = None,
) -> TestClient:
    def principal(request: object) -> CampaignPrincipal | None:
        if (
            isinstance(request, Request)
            and request.headers.get("authorization") == "Bearer test-verified"
        ):
            return CampaignPrincipal("verified-user")
        return None

    def authorize(
        principal: CampaignPrincipal,
        *,
        action: str,
        campaign_id: str | None,
        scope: Mapping[str, object] | None,
    ) -> bool:
        return (
            principal.actor_id == "verified-user"
            and action != forbidden_action
            and campaign_id != forbidden_campaign
        )

    app = FastAPI()
    install_error_handlers(app)
    app.include_router(
        create_crm_router(
            lambda: crm,
            campaign_access=CampaignHTTPAccess(
                lambda: crm, CampaignSecurityBoundary(principal, authorize)
            ),
        ),
        prefix="/crm",
    )
    return TestClient(app)


def test_fastapi_campaign_direct_and_segment_audience_lifecycle() -> None:
    crm = CRM.memory(webhook_auto_delivery=False)
    ada = crm.contacts.create(display_name="Ada")
    grace = crm.contacts.create(display_name="Grace")
    lin = crm.contacts.create(display_name="Lin")
    campaign = crm.campaigns.create(key="autumn", name="Autumn")
    segment = crm.segments.create(
        key="seed", name="Seed", entity_kind="contact", mode=SegmentMode.STATIC
    )
    crm.segments.add_members(segment.id, (EntityReference("contact", ada.id),))
    client = _client(crm)
    cid = str(campaign.id)
    base = f"/crm/campaigns/{cid}"
    headers = {"Authorization": "Bearer test-verified"}

    added = client.post(
        f"{base}/members",
        headers=headers,
        json={
            "source": "web",
            "members": [
                {"kind": "contact", "id": str(ada.id)},
                {"kind": "contact", "id": str(grace.id)},
            ],
        },
    )
    assert added.status_code == 200, added.text
    assert len(added.json()) == 2
    assert set(added.json()[0]) == {
        "campaign_id", "entity", "added_at", "source", "metadata"
    }
    direct = client.get(f"{base}/members?limit=1&offset=0", headers=headers)
    assert direct.status_code == 200, direct.text
    assert direct.json()["total"] == 2
    assert direct.json()["has_next"] is True
    second = client.get(f"{base}/members?limit=1&offset=1", headers=headers)
    assert second.status_code == 200
    assert second.json()["has_previous"] is True

    attached = client.post(
        f"{base}/segment-sources",
        headers=headers,
        json={"segment_id": str(segment.id)},
    )
    assert attached.status_code == 201, attached.text
    assert attached.json()["member_count"] == 1
    sources = client.get(f"{base}/segment-sources", headers=headers)
    assert sources.status_code == 200, sources.text
    assert sources.json()["total"] == 1

    audience = client.get(f"{base}/audience", headers=headers)
    assert audience.status_code == 200, audience.text
    assert audience.json()["total"] == 2
    count = client.get(f"{base}/audience/count", headers=headers)
    assert count.status_code == 200
    assert count.json() == {"count": 2}

    # A materialized Segment source must not change until explicit refresh.
    crm.segments.add_members(segment.id, (EntityReference("contact", lin.id),))
    before_refresh = client.get(f"{base}/audience/count", headers=headers)
    assert before_refresh.json()["count"] == 2
    refreshed = client.post(
        f"{base}/segment-sources/{segment.id}/refresh",
        headers=headers,
    )
    assert refreshed.status_code == 200, refreshed.text
    assert refreshed.json()["member_count"] == 2
    assert client.get(
        f"{base}/audience/count", headers=headers
    ).json()["count"] == 3

    removed = client.post(
        f"{base}/members/remove",
        headers=headers,
        json={"members": [{"kind": "contact", "id": str(ada.id)}]},
    )
    assert removed.status_code == 200
    assert removed.json() == {"removed": 1}
    # Ada remains in the audience via Segment capture.
    assert client.get(f"{base}/audience/count", headers=headers).json() == {
        "count": 3
    }

    detached = client.post(
        f"{base}/segment-sources/{segment.id}/detach",
        headers=headers,
    )
    assert detached.status_code == 200, detached.text
    assert detached.json() == {"removed": True}
    assert client.get(f"{base}/audience/count", headers=headers).json() == {
        "count": 1
    }
    assert client.get(f"{base}/members", headers=headers).json()["total"] == 1


def test_fastapi_campaign_audience_permissions_fail_closed() -> None:
    crm = CRM.memory(webhook_auto_delivery=False)
    campaign = crm.campaigns.create(key="private", name="Private")
    cid = str(campaign.id)
    base = f"/crm/campaigns/{cid}"
    headers = {"Authorization": "Bearer test-verified", "X-Actor-ID": "admin"}

    unsigned = _client(crm).get(f"{base}/audience/count", headers={
        "X-Actor-ID": "admin"
    })
    assert unsigned.status_code == 401

    denied = _client(crm, forbidden_action="campaign.members.read")
    for suffix in ("/members", "/audience", "/audience/count"):
        resp = denied.get(base + suffix, headers=headers)
        assert resp.status_code == 403
        assert "total" not in resp.json()
        assert "count" not in resp.json()

    sources = _client(crm, forbidden_action="campaign.sources.read")
    assert sources.get(base + "/segment-sources", headers=headers).status_code == 403

    cannot_write = _client(crm, forbidden_action="campaign.members.write")
    resp = cannot_write.post(
        base + "/members", headers=headers,
        json={"members": [{"kind": "contact", "id": str(campaign.id)}]},
    )
    assert resp.status_code == 403
    assert crm.campaigns.members(campaign.id).total == 0

    foreign = _client(crm, forbidden_campaign=cid)
    assert foreign.get(base + "/audience/count", headers=headers).status_code == 403


def test_fastapi_campaign_bulk_validation_and_openapi() -> None:
    crm = CRM.memory(webhook_auto_delivery=False)
    cid = str(crm.campaigns.create(key="safe", name="Safe").id)
    base = f"/crm/campaigns/{cid}"
    client = _client(crm)
    headers = {"Authorization": "Bearer test-verified"}

    assert client.post(
        base + "/members", headers=headers, json={"members": []}
    ).status_code == 422
    ref = {"kind": "contact", "id": "00000000-0000-4000-8000-000000000001"}
    assert client.post(
        base + "/members", headers=headers, json={"members": [ref, ref]}
    ).status_code == 422
    assert client.get(base + "/members?limit=201", headers=headers).status_code == 422
    assert client.post(
        base + "/segment-sources",
        headers=headers, json={"segment_id": "not-a-uuid"}
    ).status_code == 422

    schema = client.get("/openapi.json").json()["paths"]
    for route in (
        f"/crm/campaigns/{{campaign_id}}/members",
        f"/crm/campaigns/{{campaign_id}}/audience",
        f"/crm/campaigns/{{campaign_id}}/audience/count",
        f"/crm/campaigns/{{campaign_id}}/segment-sources",
    ):
        assert route in schema
        for operation in schema[route].values():
            assert "401" in operation["responses"]
            assert "403" in operation["responses"]
