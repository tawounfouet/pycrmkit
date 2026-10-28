"""Shared Campaign contract tests across FastAPI, DRF, and the Memory facade.

The same domain state is read over both transports. This checks actual
wire-shaped payload parity, not two copies of hard-coded expected responses.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

from django.test import override_settings
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from rest_framework.test import APIRequestFactory, force_authenticate

from pycrmkit import CRM
from pycrmkit.communication import (
    CommunicationAddress,
    CommunicationChannel,
    CommunicationDirection,
    CommunicationRecord,
    CommunicationRecordId,
)
from pycrmkit.core.references import EntityReference
from pycrmkit.integrations.campaign_security import (
    CampaignPrincipal,
    CampaignSecurityBoundary,
)
from pycrmkit.integrations.django.drf.campaign_security import (
    authenticated_drf_principal,
)
from pycrmkit.integrations.django.drf.campaign_views import CampaignViewSet
from pycrmkit.integrations.fastapi import create_crm_router, install_error_handlers
from pycrmkit.integrations.fastapi.campaign_security import CampaignHTTPAccess
from pycrmkit.segments import SegmentMode

_ACTOR = "transport-test-principal"
_HEADERS = {
    "Authorization": "Bearer trusted-session",
    "X-Actor-ID": "untrusted-administrator",
}


def _allow(
    principal: CampaignPrincipal,
    *,
    action: str,
    campaign_id: str | None,
    scope: Mapping[str, object] | None,
) -> bool:
    del campaign_id, scope
    return principal.actor_id == _ACTOR and action != _denied_action[0]


# Mutable test-local permission selector, updated before each request scenario.
_denied_action: list[str | None] = [None]


def _fastapi_client(crm: CRM) -> TestClient:
    def resolve(request: object) -> CampaignPrincipal | None:
        if (
            isinstance(request, Request)
            and request.headers.get("authorization") == "Bearer trusted-session"
        ):
            return CampaignPrincipal(_ACTOR)
        return None

    app = FastAPI()
    install_error_handlers(app)
    app.include_router(
        create_crm_router(
            lambda: crm,
            campaign_access=CampaignHTTPAccess(
                lambda: crm,
                CampaignSecurityBoundary(resolve, _allow),
            ),
        ),
        prefix="/crm",
    )
    return TestClient(app)


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
        path,
        body or {},
        format="json",
        HTTP_X_ACTOR_ID="untrusted-administrator",
    )
    if authenticated:
        force_authenticate(
            request,
            user=SimpleNamespace(is_authenticated=True, pk=_ACTOR),
        )
    kwargs = {"pk": pk} if pk is not None else {}
    response = CampaignViewSet.as_view({method: action})(request, **kwargs)
    response.render()
    return response.status_code, json.loads(response.content)


def _canonical(value: Any) -> Any:
    if isinstance(value, list):
        return [_canonical(item) for item in value]
    if isinstance(value, dict):
        return {key: _canonical(item) for key, item in value.items()}
    if isinstance(value, str) and "T" in value:
        try:
            timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value
        if timestamp.tzinfo is not None:
            return timestamp.astimezone(UTC).isoformat(timespec="microseconds")
    return value


def _setup() -> tuple[CRM, str, str]:
    crm = CRM.memory(webhook_auto_delivery=False)
    ada = crm.contacts.create(display_name="Ada")
    grace = crm.contacts.create(display_name="Grace")
    campaign = crm.campaigns.create(
        key="cross-transport",
        name="Cross Transport",
        description="Before patch",
        metadata={"purpose": "contract"},
    )
    crm.campaigns.add_members(
        campaign.id,
        (
            EntityReference("contact", ada.id),
            EntityReference("contact", grace.id),
        ),
    )
    segment = crm.segments.create(
        key="parity-segment",
        name="Parity Segment",
        entity_kind="contact",
        mode=SegmentMode.STATIC,
    )
    crm.segments.add_members(
        segment.id, (EntityReference("contact", ada.id),)
    )
    crm.campaigns.attach_segment_source(campaign.id, segment.id)
    crm.campaigns.add_attribution(
        campaign.id, EntityReference("contact", ada.id),
        source="web", external_ref="campaign-parity",
    )
    now = datetime.now(UTC)
    communication_id = CommunicationRecordId(uuid4())
    communication = CommunicationRecord(
        id=communication_id,
        created_at=now,
        updated_at=now,
        occurred_at=now,
        channel=CommunicationChannel.EMAIL,
        direction=CommunicationDirection.OUTBOUND,
        counterparties=(
            CommunicationAddress(
                CommunicationChannel.EMAIL, "ada@example.test"
            ),
        ),
        subject="Never exposed through Campaign linkage",
    )
    with crm._runtime.uow_factory() as uow:
        uow.communications.save_record(communication)
        uow.commit()
    crm.campaigns.link_communication(campaign.id, communication_id)
    return crm, str(campaign.id), str(ada.id)


def test_campaign_read_contracts_are_identical_on_both_transports() -> None:
    crm, cid, _ = _setup()
    client = _fastapi_client(crm)
    cases = (
        ("list", "/crm/campaigns", "/crm/campaigns/", None),
        ("retrieve", f"/crm/campaigns/{cid}", f"/crm/campaigns/{cid}/", cid),
        (
            "members",
            f"/crm/campaigns/{cid}/members?limit=1&offset=1",
            f"/crm/campaigns/{cid}/members/?limit=1&offset=1",
            cid,
        ),
        (
            "audience", f"/crm/campaigns/{cid}/audience?limit=1",
            f"/crm/campaigns/{cid}/audience/?limit=1", cid,
        ),
        (
            "audience_count", f"/crm/campaigns/{cid}/audience/count",
            f"/crm/campaigns/{cid}/audience/count/", cid,
        ),
        (
            "segment_sources", f"/crm/campaigns/{cid}/segment-sources",
            f"/crm/campaigns/{cid}/segment-sources/", cid,
        ),
        (
            "attributions", f"/crm/campaigns/{cid}/attributions",
            f"/crm/campaigns/{cid}/attributions/", cid,
        ),
        (
            "communication_links",
            f"/crm/campaigns/{cid}/communication-links",
            f"/crm/campaigns/{cid}/communication-links/", cid,
        ),
    )
    _denied_action[0] = None
    with override_settings(
        PYCRMKIT_CRM_FACTORY=lambda: crm,
        PYCRMKIT_CAMPAIGN_SECURITY=CampaignSecurityBoundary(
            authenticated_drf_principal, _allow
        ),
    ):
        for action, fast_path, drf_path, pk in cases:
            fast = client.get(fast_path, headers=_HEADERS)
            drf_status, drf_data = _drf(
                "get", action, drf_path, pk=pk
            )
            assert fast.status_code == drf_status == 200, (
                action, fast.text, drf_data
            )
            assert _canonical(fast.json()) == _canonical(drf_data), (
                action, fast.json(), drf_data
            )
    _denied_action[0] = None


def test_campaign_patch_roundtrips_between_frameworks() -> None:
    crm, cid, _ = _setup()
    client = _fastapi_client(crm)
    url = f"/crm/campaigns/{cid}"
    _denied_action[0] = None
    with override_settings(
        PYCRMKIT_CRM_FACTORY=lambda: crm,
        PYCRMKIT_CAMPAIGN_SECURITY=CampaignSecurityBoundary(
            authenticated_drf_principal, _allow
        ),
    ):
        unchanged = client.patch(
            url, headers=_HEADERS, json={"expected_revision": 1}
        )
        assert unchanged.status_code == 200, unchanged.text
        assert unchanged.json()["description"] == "Before patch"
        revision = unchanged.json()["revision"]
        status_code, cleared = _drf(
            "patch", "partial_update", url + "/", pk=cid,
            body={"expected_revision": revision, "description": None},
        )
        assert status_code == 200, cleared
        assert cleared["description"] is None
        cross_read = client.get(url, headers=_HEADERS)
        assert cross_read.status_code == 200
        assert _canonical(cross_read.json()) == _canonical(cleared)

        rejected = client.patch(
            url, headers=_HEADERS,
            json={"expected_revision": 1, "name": "Stale"},
        )
        assert rejected.status_code == 409
        code, _ = _drf(
            "patch", "partial_update", url + "/", pk=cid,
            body={"expected_revision": 1, "name": "Stale"},
        )
        assert code == 409
    _denied_action[0] = None


def test_campaign_authz_and_invalid_input_status_parity() -> None:
    crm, cid, _ = _setup()
    client = _fastapi_client(crm)
    path = f"/crm/campaigns/{cid}"
    with override_settings(
        PYCRMKIT_CRM_FACTORY=lambda: crm,
        PYCRMKIT_CAMPAIGN_SECURITY=CampaignSecurityBoundary(
            authenticated_drf_principal, _allow
        ),
    ):
        for action, suffix in (
            ("campaign.members.read", "audience/count"),
            ("campaign.attribution.read", "attributions"),
            ("campaign.communications.link", "communication-links"),
        ):
            _denied_action[0] = action
            fast = client.get(
                path + "/" + suffix, headers=_HEADERS
            )
            drf_action = {
                "audience/count": "audience_count",
                "attributions": "attributions",
                "communication-links": "communication_links",
            }[suffix]
            drf_status, drf_data = _drf(
                "get", drf_action, path + "/" + suffix + "/", pk=cid
            )
            assert fast.status_code == drf_status == 403
            assert "total" not in fast.json() and "total" not in drf_data
            assert "count" not in fast.json() and "count" not in drf_data
        _denied_action[0] = None
        fast_anon = client.get(
            path + "/audience/count", headers={"X-Actor-ID": "admin"}
        )
        drf_anon, _ = _drf(
            "get", "audience_count", path + "/audience/count/",
            pk=cid, authenticated=False,
        )
        assert fast_anon.status_code == drf_anon == 401

        fast_bad = client.patch(
            path, headers=_HEADERS,
            json={"expected_revision": 1, "status": "active"},
        )
        drf_bad, _ = _drf(
            "patch", "partial_update", path + "/", pk=cid,
            body={"expected_revision": 1, "status": "active"},
        )
        assert fast_bad.status_code == drf_bad == 422
    _denied_action[0] = None
