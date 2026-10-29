"""Shared Campaign contract tests across FastAPI, DRF, and the Memory facade.

The same domain state is read over both transports. This checks actual
wire-shaped payload parity, not two copies of hard-coded expected responses.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
from django.conf import settings
from django.test import override_settings
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
from pycrmkit.core.references import EntityReference
from pycrmkit.integrations.campaign_security import (
    CampaignPrincipal,
    CampaignSecurityBoundary,
)
from pycrmkit.integrations.fastapi import create_crm_router, install_error_handlers
from pycrmkit.integrations.fastapi.campaign_security import CampaignHTTPAccess
from pycrmkit.segments import SegmentMode

_ACTOR = "transport-test-principal"
_HEADERS = {
    "Authorization": "Bearer trusted-session",
    "X-Actor-ID": "untrusted-administrator",
}


@pytest.fixture(autouse=True)
def _isolated_campaign_drf_settings() -> Iterator[None]:
    """Make this dual-transport module runnable alone, independent of collection order."""
    import django

    if not settings.configured:
        settings.configure(
            SECRET_KEY="pycrmkit-cross-transport-tests",
            INSTALLED_APPS=[],
            DATABASES={"default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": ":memory:",
            }},
            USE_TZ=True,
            TIME_ZONE="UTC",
        )
    django.setup()
    with override_settings(
        REST_FRAMEWORK={
            "UNAUTHENTICATED_USER": None,
            "EXCEPTION_HANDLER": (
                "pycrmkit.integrations.django.drf.errors."
                "pycrmkit_exception_handler"
            ),
        },
    ):
        yield


def _drf_security_boundary() -> CampaignSecurityBoundary:
    from pycrmkit.integrations.django.drf.campaign_security import (
        authenticated_drf_principal,
    )

    return CampaignSecurityBoundary(authenticated_drf_principal, _allow)


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
    segment_id: str | None = None,
    body: dict[str, object] | None = None,
    authenticated: bool = True,
) -> tuple[int, Any]:
    from rest_framework.test import APIRequestFactory, force_authenticate

    from pycrmkit.integrations.django.drf.campaign_views import CampaignViewSet

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
    if segment_id is not None:
        kwargs["segment_id"] = segment_id
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
        PYCRMKIT_CAMPAIGN_SECURITY=_drf_security_boundary(),
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
        PYCRMKIT_CAMPAIGN_SECURITY=_drf_security_boundary(),
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
        PYCRMKIT_CAMPAIGN_SECURITY=_drf_security_boundary(),
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


def test_rc1_cross_transport_create_patch_and_full_lifecycle() -> None:
    """Alternate real HTTP writers/readers for two independent Campaigns."""
    crm = CRM.memory(webhook_auto_delivery=False)
    client = _fastapi_client(crm)
    _denied_action[0] = None
    with override_settings(
        PYCRMKIT_CRM_FACTORY=lambda: crm,
        PYCRMKIT_CAMPAIGN_SECURITY=_drf_security_boundary(),
    ):
        # FastAPI creates; DRF reads the very same object.
        created = client.post(
            "/crm/campaigns",
            headers=_HEADERS,
            json={"key": "lot-005-fast", "name": "Fast writer",
                  "description": "Clear me", "metadata": {"scenario": "rc1"}},
        )
        assert created.status_code == 201, created.text
        cid = created.json()["id"]
        status_code, drf_read = _drf(
            "get", "retrieve", f"/crm/campaigns/{cid}/", pk=cid
        )
        assert status_code == 200
        assert _canonical(created.json()) == _canonical(drf_read)

        # DRF creates another Campaign; FastAPI sees it without a sync step.
        status_code, drf_created = _drf(
            "post", "create", "/crm/campaigns/",
            body={"key": "lot-005-drf", "name": "DRF writer"},
        )
        assert status_code == 201, drf_created
        fast_read = client.get(
            f"/crm/campaigns/{drf_created['id']}", headers=_HEADERS
        )
        assert fast_read.status_code == 200
        assert _canonical(fast_read.json()) == _canonical(drf_created)

        # Omitted PATCH fields do not clear a previously populated field.
        omitted = client.patch(
            f"/crm/campaigns/{cid}",
            headers=_HEADERS, json={"expected_revision": 1},
        )
        assert omitted.status_code == 200, omitted.text
        assert omitted.json()["description"] == "Clear me"
        assert omitted.json()["revision"] == 1

        # Explicit null is an actual change, with revision increment.
        status_code, cleared = _drf(
            "patch", "partial_update", f"/crm/campaigns/{cid}/", pk=cid,
            body={"expected_revision": 1, "description": None},
        )
        assert status_code == 200, cleared
        assert cleared["description"] is None
        assert cleared["revision"] == 2
        read = client.get(f"/crm/campaigns/{cid}", headers=_HEADERS)
        assert read.status_code == 200
        assert _canonical(read.json()) == _canonical(cleared)

        # Both transports reject the same optimistic-lock violation.
        stale_fast = client.patch(
            f"/crm/campaigns/{cid}", headers=_HEADERS,
            json={"expected_revision": 1, "name": "should not persist"},
        )
        stale_status, stale_drf = _drf(
            "patch", "partial_update", f"/crm/campaigns/{cid}/", pk=cid,
            body={"expected_revision": 1, "name": "should not persist"},
        )
        assert stale_fast.status_code == stale_status == 409
        assert stale_fast.json()["code"] == stale_drf["code"]
        assert client.get(
            f"/crm/campaigns/{cid}", headers=_HEADERS
        ).json()["revision"] == 2

        # Lifecycle: DRF -> FastAPI -> DRF -> FastAPI, same persisted state.
        status_code, active = _drf(
            "post", "activate", f"/crm/campaigns/{cid}/activate/", pk=cid,
            body={"expected_revision": 2},
        )
        assert status_code == 200 and active["status"] == "active"
        assert active["revision"] == 3
        assert client.get(
            f"/crm/campaigns/{cid}", headers=_HEADERS
        ).json()["status"] == "active"

        completed = client.post(
            f"/crm/campaigns/{cid}/complete", headers=_HEADERS,
            json={"expected_revision": 3},
        )
        assert completed.status_code == 200, completed.text
        assert completed.json()["status"] == "completed"
        assert completed.json()["revision"] == 4
        status_code, drf_read = _drf(
            "get", "retrieve", f"/crm/campaigns/{cid}/", pk=cid
        )
        assert status_code == 200
        assert _canonical(drf_read) == _canonical(completed.json())

        status_code, archived = _drf(
            "post", "archive", f"/crm/campaigns/{cid}/archive/", pk=cid,
            body={"expected_revision": 4},
        )
        assert status_code == 200 and archived["status"] == "archived"
        assert archived["revision"] == 5
        final = client.get(f"/crm/campaigns/{cid}", headers=_HEADERS)
        assert final.status_code == 200
        assert _canonical(final.json()) == _canonical(archived)
    _denied_action[0] = None


def test_rc1_cross_transport_membership_mutations_and_read_parity() -> None:
    crm, cid, ada_id = _setup()
    client = _fastapi_client(crm)
    added = crm.contacts.create(display_name="Lin")
    reference = {"kind": "contact", "id": str(added.id)}
    _denied_action[0] = None
    with override_settings(
        PYCRMKIT_CRM_FACTORY=lambda: crm,
        PYCRMKIT_CAMPAIGN_SECURITY=_drf_security_boundary(),
    ):
        created = client.post(
            f"/crm/campaigns/{cid}/members", headers=_HEADERS,
            json={"members": [reference], "source": "campaign-rc1",
                  "metadata": {"lot": "005"}},
        )
        assert created.status_code == 200, created.text
        assert len(created.json()) == 1
        status_code, read = _drf(
            "get", "members", f"/crm/campaigns/{cid}/members/", pk=cid
        )
        assert status_code == 200 and read["total"] == 3
        assert any(item["entity"]["id"] == str(added.id) for item in read["items"])

        # Reverse direction: DRF removes, FastAPI reads, then FastAPI removes.
        status_code, removed = _drf(
            "post", "remove_members", f"/crm/campaigns/{cid}/members/remove/",
            pk=cid, body={"members": [{"kind": "contact", "id": ada_id}]},
        )
        assert status_code == 200 and removed == {"removed": 1}
        fast = client.get(f"/crm/campaigns/{cid}/members", headers=_HEADERS)
        assert fast.status_code == 200 and fast.json()["total"] == 2
        assert all(x["entity"]["id"] != ada_id for x in fast.json()["items"])

        removed_fast = client.post(
            f"/crm/campaigns/{cid}/members/remove", headers=_HEADERS,
            json={"members": [reference]},
        )
        assert removed_fast.status_code == 200
        assert removed_fast.json() == {"removed": 1}
        status_code, drf = _drf(
            "get", "members", f"/crm/campaigns/{cid}/members/", pk=cid
        )
        assert status_code == 200 and drf["total"] == 1
        assert _canonical(drf) == _canonical(
            client.get(f"/crm/campaigns/{cid}/members", headers=_HEADERS).json()
        )
    _denied_action[0] = None


def test_rc1_cross_transport_segment_attribution_and_communication_links() -> None:
    crm, cid, ada_id = _setup()
    client = _fastapi_client(crm)
    url = f"/crm/campaigns/{cid}"
    _denied_action[0] = None
    with override_settings(
        PYCRMKIT_CRM_FACTORY=lambda: crm,
        PYCRMKIT_CAMPAIGN_SECURITY=_drf_security_boundary(),
    ):
        # Start with an existing Segment source. DRF detaches; FastAPI sees zero.
        sources = client.get(url + "/segment-sources", headers=_HEADERS)
        assert sources.status_code == 200 and sources.json()["total"] == 1
        sid = sources.json()["items"][0]["segment_id"]
        status_code, detached = _drf(
            "post", "detach_segment_source",
            url + f"/segment-sources/{sid}/detach/",
            pk=cid, segment_id=sid,
        )
        assert status_code == 200 and detached == {"removed": True}
        assert client.get(
            url + "/segment-sources", headers=_HEADERS
        ).json()["total"] == 0

        # DRF attaches; FastAPI refreshes; both read the same snapshot metadata.
        status_code, attached = _drf(
            "post", "segment_sources", url + "/segment-sources/", pk=cid,
            body={"segment_id": sid, "metadata": {"lot": "005"}},
        )
        assert status_code == 201 and attached["segment_id"] == sid
        refreshed = client.post(
            url + f"/segment-sources/{sid}/refresh", headers=_HEADERS
        )
        assert refreshed.status_code == 200, refreshed.text
        status_code, drf_sources = _drf(
            "get", "segment_sources", url + "/segment-sources/", pk=cid
        )
        assert status_code == 200 and drf_sources["total"] == 1
        assert _canonical(drf_sources) == _canonical(
            client.get(url + "/segment-sources", headers=_HEADERS).json()
        )
        assert drf_sources["items"][0]["segment_id"] == sid

        # DRF removes the original attribution; FastAPI restores a new one.
        original = {"target": {"kind": "contact", "id": ada_id},
                    "source": "web", "external_ref": "campaign-parity"}
        status_code, removed = _drf(
            "post", "remove_attribution", url + "/attributions/remove/",
            pk=cid, body=original,
        )
        assert status_code == 200 and removed == {"removed": True}
        assert client.get(
            url + "/attributions", headers=_HEADERS
        ).json()["total"] == 0
        created = client.post(
            url + "/attributions", headers=_HEADERS,
            json={"target": original["target"], "source": "campaign-rc1",
                  "external_ref": "lot-005"},
        )
        assert created.status_code == 201, created.text
        status_code, drf_attribution = _drf(
            "get", "attributions", url + "/attributions/", pk=cid
        )
        assert status_code == 200 and drf_attribution["total"] == 1
        assert _canonical(drf_attribution) == _canonical(
            client.get(url + "/attributions", headers=_HEADERS).json()
        )

        # DRF unlinks; FastAPI relinks. No Communication body is exposed.
        links = client.get(url + "/communication-links", headers=_HEADERS)
        assert links.status_code == 200 and links.json()["total"] == 1
        comm_id = links.json()["items"][0]["communication_id"]
        status_code, unlinked = _drf(
            "post", "unlink_communication",
            url + "/communication-links/remove/", pk=cid,
            body={"communication_id": comm_id},
        )
        assert status_code == 200 and unlinked == {"removed": True}
        assert client.get(
            url + "/communication-links", headers=_HEADERS
        ).json()["total"] == 0
        relinked = client.post(
            url + "/communication-links", headers=_HEADERS,
            json={"communication_id": comm_id, "role": "touchpoint",
                  "metadata": {"lot": "005"}},
        )
        assert relinked.status_code == 201, relinked.text
        status_code, drf_links = _drf(
            "get", "communication_links", url + "/communication-links/",
            pk=cid,
        )
        assert status_code == 200 and drf_links["total"] == 1
        assert _canonical(drf_links) == _canonical(
            client.get(url + "/communication-links", headers=_HEADERS).json()
        )
        assert "Never exposed through Campaign linkage" not in str(drf_links)
        assert "ada@example.test" not in str(drf_links)
    _denied_action[0] = None


def test_rc1_cross_transport_pagination_edges_and_empty_pages() -> None:
    crm, cid, _ = _setup()
    client = _fastapi_client(crm)
    _denied_action[0] = None
    paths = (
        ("list", "/crm/campaigns", "/crm/campaigns/", None),
        ("members", f"/crm/campaigns/{cid}/members",
         f"/crm/campaigns/{cid}/members/", cid),
        ("audience", f"/crm/campaigns/{cid}/audience",
         f"/crm/campaigns/{cid}/audience/", cid),
        ("segment_sources", f"/crm/campaigns/{cid}/segment-sources",
         f"/crm/campaigns/{cid}/segment-sources/", cid),
        ("attributions", f"/crm/campaigns/{cid}/attributions",
         f"/crm/campaigns/{cid}/attributions/", cid),
        ("communication_links", f"/crm/campaigns/{cid}/communication-links",
         f"/crm/campaigns/{cid}/communication-links/", cid),
    )
    with override_settings(
        PYCRMKIT_CRM_FACTORY=lambda: crm,
        PYCRMKIT_CAMPAIGN_SECURITY=_drf_security_boundary(),
    ):
        for limit, offset in ((1, 0), (1, 1), (200, 0), (200, 250)):
            for action, fast_path, drf_path, pk in paths:
                query = f"?limit={limit}&offset={offset}"
                fast = client.get(fast_path + query, headers=_HEADERS)
                status_code, drf = _drf(
                    "get", action, drf_path + query, pk=pk
                )
                assert fast.status_code == status_code == 200, (
                    action, query, fast.text, drf
                )
                assert _canonical(fast.json()) == _canonical(drf), (
                    action, query, fast.json(), drf
                )
                assert fast.json()["limit"] == limit
                assert fast.json()["offset"] == offset
                if offset == 250:
                    assert fast.json()["items"] == []
                    assert fast.json()["has_next"] is False
                if action == "members" and limit == 1 and offset == 0:
                    assert fast.json()["total"] == 2
                    assert fast.json()["has_next"] is True
                if action == "members" and limit == 1 and offset == 1:
                    assert fast.json()["has_previous"] is True

        for query in ("?limit=0", "?limit=201", "?offset=-1"):
            for action, fast_path, drf_path, pk in paths:
                fast = client.get(fast_path + query, headers=_HEADERS)
                status_code, _ = _drf(
                    "get", action, drf_path + query, pk=pk
                )
                assert fast.status_code == status_code == 422, (
                    action, query, fast.text
                )
    _denied_action[0] = None
