"""FastAPI Campaign attribution and Communication-link contract tests."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from pycrmkit import CRM
from pycrmkit.communication import (
    CommunicationAddress,
    CommunicationChannel,
    CommunicationDirection,
    CommunicationRecord,
    CommunicationRecordId,
)
from pycrmkit.integrations.campaign_security import (
    CampaignPrincipal,
    CampaignSecurityBoundary,
)
from pycrmkit.integrations.fastapi import create_crm_router, install_error_handlers
from pycrmkit.integrations.fastapi.campaign_security import CampaignHTTPAccess


def _client(crm: CRM, *, denied: str | None = None) -> TestClient:
    def principal(request: object) -> CampaignPrincipal | None:
        if (
            isinstance(request, Request)
            and request.headers.get("authorization") == "Bearer verified-test"
        ):
            return CampaignPrincipal("trusted-user")
        return None

    def policy(
        principal: CampaignPrincipal,
        *,
        action: str,
        campaign_id: str | None,
        scope: Mapping[str, object] | None,
    ) -> bool:
        return principal.actor_id == "trusted-user" and action != denied

    app = FastAPI()
    install_error_handlers(app)
    app.include_router(
        create_crm_router(
            lambda: crm,
            campaign_access=CampaignHTTPAccess(
                lambda: crm,
                CampaignSecurityBoundary(principal, policy),
            ),
        ),
        prefix="/crm",
    )
    return TestClient(app)


def _communication(crm: CRM) -> CommunicationRecordId:
    now = datetime.now(UTC)
    identifier = CommunicationRecordId(uuid4())
    record = CommunicationRecord(
        id=identifier,
        created_at=now,
        updated_at=now,
        occurred_at=now,
        channel=CommunicationChannel.EMAIL,
        direction=CommunicationDirection.OUTBOUND,
        counterparties=(
            CommunicationAddress(CommunicationChannel.EMAIL, "ada@example.test"),
        ),
        subject="Confidential email body metadata",
    )
    with crm._runtime.uow_factory() as uow:
        uow.communications.save_record(record)
        uow.commit()
    return identifier


def test_fastapi_campaign_attribution_roundtrip_and_page() -> None:
    crm = CRM.memory(webhook_auto_delivery=False)
    contact = crm.contacts.create(display_name="Ada")
    campaign = crm.campaigns.create(key="spring", name="Spring")
    cid = str(campaign.id)
    base = f"/crm/campaigns/{cid}/attributions"
    headers = {"Authorization": "Bearer verified-test"}
    client = _client(crm)
    payload = {
        "target": {"kind": "contact", "id": str(contact.id)},
        "source": "LinkedIn",
        "external_ref": " utm-123 ",
        "metadata": {"channel": "social"},
    }
    created = client.post(base, headers=headers, json=payload)
    assert created.status_code == 201, created.text
    assert created.json()["source"] == "linkedin"
    assert created.json()["external_ref"] == "utm-123"
    assert set(created.json()) == {
        "campaign_id", "target", "source", "external_ref",
        "recorded_at", "metadata",
    }
    listed = client.get(base + "?limit=1&offset=0", headers=headers)
    assert listed.status_code == 200, listed.text
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["target"]["id"] == str(contact.id)

    removed = client.post(base + "/remove", headers=headers, json={
        "target": payload["target"],
        "source": "linkedin",
        "external_ref": "utm-123",
    })
    assert removed.status_code == 200, removed.text
    assert removed.json() == {"removed": True}
    assert client.get(base, headers=headers).json()["total"] == 0


def test_fastapi_campaign_links_existing_record_without_revealing_content() -> None:
    crm = CRM.memory(webhook_auto_delivery=False)
    cid = str(crm.campaigns.create(key="comms", name="Comms").id)
    communication = _communication(crm)
    base = f"/crm/campaigns/{cid}/communication-links"
    headers = {"Authorization": "Bearer verified-test"}
    client = _client(crm)

    created = client.post(base, headers=headers, json={
        "communication_id": str(communication), "role": "  Follow Up  "
    })
    assert created.status_code == 201, created.text
    assert created.json()["role"] == "follow up"
    assert set(created.json()) == {
        "campaign_id", "communication_id", "linked_at", "role", "metadata"
    }
    assert "subject" not in created.text
    assert "counterparties" not in created.text

    listed = client.get(base, headers=headers)
    assert listed.status_code == 200, listed.text
    assert listed.json()["total"] == 1
    assert "subject" not in listed.text

    removed = client.post(base + "/remove", headers=headers, json={
        "communication_id": str(communication)
    })
    assert removed.status_code == 200, removed.text
    assert removed.json() == {"removed": True}
    assert client.get(base, headers=headers).json()["total"] == 0


def test_fastapi_link_to_nonexistent_communication_is_not_created() -> None:
    crm = CRM.memory(webhook_auto_delivery=False)
    cid = str(crm.campaigns.create(key="missing", name="Missing").id)
    client = _client(crm)
    headers = {"Authorization": "Bearer verified-test"}
    path = f"/crm/campaigns/{cid}/communication-links"
    response = client.post(
        path, headers=headers, json={"communication_id": str(uuid4())}
    )
    assert response.status_code == 404, response.text
    assert client.get(path, headers=headers).json()["total"] == 0


def test_fastapi_linkage_permissions_and_inputs_fail_closed() -> None:
    crm = CRM.memory(webhook_auto_delivery=False)
    cid = str(crm.campaigns.create(key="secure", name="Secure").id)
    base = f"/crm/campaigns/{cid}"
    headers = {"Authorization": "Bearer verified-test"}
    unsigned = _client(crm).get(
        base + "/attributions", headers={"X-Actor-ID": "admin"}
    )
    assert unsigned.status_code == 401
    for suffix, action in (
        ("/attributions", "campaign.attribution.read"),
        ("/communication-links", "campaign.communications.link"),
    ):
        denied = _client(crm, denied=action).get(
            base + suffix, headers=headers
        )
        assert denied.status_code == 403
        assert "total" not in denied.json()
    denied_write = _client(crm, denied="campaign.attribution.write").post(
        base + "/attributions",
        headers=headers,
        json={
            "target": {"kind": "contact", "id": str(uuid4())},
            "source": "manual",
        },
    )
    assert denied_write.status_code == 403
    assert _client(crm).post(
        base + "/communication-links",
        headers=headers,
        json={"communication_id": "not-uuid"},
    ).status_code == 422
    assert _client(crm).get(
        base + "/attributions?limit=201", headers=headers
    ).status_code == 422

    schema = _client(crm).get("/openapi.json").json()["paths"]
    for suffix in ("attributions", "communication-links"):
        path = "/crm/campaigns/{campaign_id}/" + suffix
        assert "get" in schema[path] and "post" in schema[path]
        assert "401" in schema[path]["get"]["responses"]
        assert "403" in schema[path]["post"]["responses"]
    assert "/crm/campaigns/{campaign_id}/communications" not in schema
