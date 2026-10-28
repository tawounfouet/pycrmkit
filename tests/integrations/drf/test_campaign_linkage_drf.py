"""DRF Campaign attribution/linkage parity and access policy tests."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

from django.test import override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

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
from pycrmkit.integrations.django.drf.campaign_security import (
    authenticated_drf_principal,
)
from pycrmkit.integrations.django.drf.campaign_views import CampaignViewSet
from pycrmkit.integrations.django.drf.routers import create_drf_router


def _policy(*, deny: str | None = None) -> CampaignSecurityBoundary:
    def authorize(
        principal: CampaignPrincipal,
        *,
        action: str,
        campaign_id: str | None,
        scope: Mapping[str, object] | None,
    ) -> bool:
        return principal.actor_id == "verified-user" and action != deny

    return CampaignSecurityBoundary(authenticated_drf_principal, authorize)


def _send(
    method: str,
    action: str,
    path: str,
    *,
    pk: str,
    payload: dict[str, object] | None = None,
    authenticated: bool = True,
) -> Any:
    request = getattr(APIRequestFactory(), method)(
        path,
        payload or {},
        format="json",
        HTTP_X_ACTOR_ID="forged-admin",
    )
    if authenticated:
        force_authenticate(
            request,
            user=SimpleNamespace(is_authenticated=True, pk="verified-user"),
        )
    return CampaignViewSet.as_view({method: action})(request, pk=pk)


def _record(crm: CRM) -> CommunicationRecordId:
    now = datetime.now(UTC)
    identifier = CommunicationRecordId(uuid4())
    record = CommunicationRecord(
        id=identifier,
        created_at=now,
        updated_at=now,
        channel=CommunicationChannel.EMAIL,
        direction=CommunicationDirection.OUTBOUND,
        occurred_at=now,
        counterparties=(
            CommunicationAddress(CommunicationChannel.EMAIL, "ada@example.test"),
        ),
        subject="Private communication subject",
    )
    with crm._runtime.uow_factory() as uow:
        uow.communications.save_record(record)
        uow.commit()
    return identifier


def test_drf_campaign_attribution_roundtrip() -> None:
    crm = CRM.memory(webhook_auto_delivery=False)
    contact = crm.contacts.create(display_name="Ada")
    cid = str(crm.campaigns.create(key="spring", name="Spring").id)
    base = f"/crm/campaigns/{cid}/attributions/"
    payload = {
        "target": {"kind": "contact", "id": str(contact.id)},
        "source": " LinkedIn ",
        "external_ref": " utm-123 ",
    }
    with override_settings(
        PYCRMKIT_CRM_FACTORY=lambda: crm,
        PYCRMKIT_CAMPAIGN_SECURITY=_policy(),
    ):
        created = _send("post", "attributions", base, pk=cid, payload=payload)
        assert created.status_code == 201, created.data
        assert created.data["source"] == "linkedin"
        assert created.data["external_ref"] == "utm-123"
        assert set(created.data) == {
            "campaign_id", "target", "source", "external_ref",
            "recorded_at", "metadata",
        }

        listed = _send("get", "attributions", base, pk=cid)
        assert listed.status_code == 200, listed.data
        assert listed.data["total"] == 1
        assert str(listed.data["items"][0]["target"]["id"]) == str(contact.id)

        removed = _send(
            "post", "remove_attribution", base + "remove/",
            pk=cid,
            payload={
                "target": payload["target"],
                "source": "linkedin",
                "external_ref": "utm-123",
            },
        )
        assert removed.status_code == 200, removed.data
        assert removed.data == {"removed": True}
        assert _send("get", "attributions", base, pk=cid).data["total"] == 0


def test_drf_campaign_communication_link_metadata_only() -> None:
    crm = CRM.memory(webhook_auto_delivery=False)
    cid = str(crm.campaigns.create(key="comms", name="Comms").id)
    identifier = _record(crm)
    base = f"/crm/campaigns/{cid}/communication-links/"
    with override_settings(
        PYCRMKIT_CRM_FACTORY=lambda: crm,
        PYCRMKIT_CAMPAIGN_SECURITY=_policy(),
    ):
        created = _send(
            "post", "communication_links", base, pk=cid,
            payload={"communication_id": str(identifier), "role": " Follow Up "},
        )
        assert created.status_code == 201, created.data
        assert created.data["role"] == "follow up"
        assert set(created.data) == {
            "campaign_id", "communication_id", "linked_at", "role", "metadata"
        }
        assert "subject" not in created.data

        listed = _send("get", "communication_links", base, pk=cid)
        assert listed.status_code == 200, listed.data
        assert listed.data["total"] == 1
        assert "subject" not in listed.data["items"][0]

        removed = _send(
            "post", "unlink_communication", base + "remove/",
            pk=cid, payload={"communication_id": str(identifier)},
        )
        assert removed.status_code == 200
        assert removed.data == {"removed": True}
        assert _send("get", "communication_links", base, pk=cid).data[
            "total"
        ] == 0


def test_drf_campaign_missing_communication_and_invalid_ids() -> None:
    crm = CRM.memory(webhook_auto_delivery=False)
    cid = str(crm.campaigns.create(key="missing", name="Missing").id)
    path = f"/crm/campaigns/{cid}/communication-links/"
    with override_settings(
        PYCRMKIT_CRM_FACTORY=lambda: crm,
        PYCRMKIT_CAMPAIGN_SECURITY=_policy(),
    ):
        missing = _send(
            "post", "communication_links", path, pk=cid,
            payload={"communication_id": str(uuid4())},
        )
        assert missing.status_code == 404, missing.data
        invalid = _send(
            "post", "communication_links", path, pk=cid,
            payload={"communication_id": "invalid"},
        )
        assert invalid.status_code == 422, invalid.data
        assert _send("get", "communication_links", path, pk=cid).data[
            "total"
        ] == 0


def test_drf_campaign_linkage_denied_without_count_or_identity_leak() -> None:
    crm = CRM.memory(webhook_auto_delivery=False)
    cid = str(crm.campaigns.create(key="secure", name="Secure").id)
    base = f"/crm/campaigns/{cid}/"
    with override_settings(
        PYCRMKIT_CRM_FACTORY=lambda: crm,
        PYCRMKIT_CAMPAIGN_SECURITY=_policy(deny="campaign.attribution.read"),
    ):
        denied = _send(
            "get", "attributions", base + "attributions/", pk=cid
        )
        assert denied.status_code == 403
        assert "total" not in denied.data
    with override_settings(
        PYCRMKIT_CRM_FACTORY=lambda: crm,
        PYCRMKIT_CAMPAIGN_SECURITY=_policy(deny="campaign.communications.link"),
    ):
        denied_link = _send(
            "get", "communication_links",
            base + "communication-links/", pk=cid,
        )
        assert denied_link.status_code == 403
        assert "total" not in denied_link.data
    with override_settings(
        PYCRMKIT_CRM_FACTORY=lambda: crm,
        PYCRMKIT_CAMPAIGN_SECURITY=_policy(),
    ):
        unsigned = _send(
            "get", "attributions", base + "attributions/",
            pk=cid, authenticated=False,
        )
        assert unsigned.status_code == 401


def test_drf_campaign_linkage_routes_do_not_expose_record_body() -> None:
    with override_settings(PYCRMKIT_CAMPAIGN_SECURITY=_policy()):
        router = create_drf_router(include_campaigns=True)
        routes = [str(item.pattern) for item in router.urls]
    assert any("attributions" in item for item in routes)
    assert any("communication-links" in item for item in routes)
    assert not any(
        "communications/" in item and "communication-links" not in item
        for item in routes
    )
