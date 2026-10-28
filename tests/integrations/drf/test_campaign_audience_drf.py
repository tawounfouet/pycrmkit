"""DRF opt-in Campaign audience contract and parity scenarios."""

from __future__ import annotations

from collections.abc import Mapping
from types import SimpleNamespace
from typing import Any

from django.test import override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from pycrmkit import CRM
from pycrmkit.core.references import EntityReference
from pycrmkit.integrations.campaign_security import (
    CampaignPrincipal,
    CampaignSecurityBoundary,
)
from pycrmkit.integrations.django.drf.campaign_security import (
    authenticated_drf_principal,
)
from pycrmkit.integrations.django.drf.campaign_views import CampaignViewSet
from pycrmkit.segments import SegmentMode


def _policy(*, denied: str | None = None) -> CampaignSecurityBoundary:
    def check(
        principal: CampaignPrincipal,
        *,
        action: str,
        campaign_id: str | None,
        scope: Mapping[str, object] | None,
    ) -> bool:
        return principal.actor_id == "verified" and action != denied

    return CampaignSecurityBoundary(authenticated_drf_principal, check)


def _send(
    method: str,
    action: str,
    path: str,
    *,
    payload: dict[str, object] | None = None,
    pk: str | None = None,
    segment_id: str | None = None,
    authenticated: bool = True,
) -> Any:
    factory = APIRequestFactory()
    request = getattr(factory, method)(
        path, payload or {}, format="json", HTTP_X_ACTOR_ID="spoofed-admin"
    )
    if authenticated:
        force_authenticate(
            request,
            user=SimpleNamespace(is_authenticated=True, pk="verified"),
        )
    kwargs: dict[str, str] = {}
    if pk is not None:
        kwargs["pk"] = pk
    if segment_id is not None:
        kwargs["segment_id"] = segment_id
    return CampaignViewSet.as_view({method: action})(request, **kwargs)


def test_drf_campaign_audience_segment_source_flow() -> None:
    crm = CRM.memory(webhook_auto_delivery=False)
    ada = crm.contacts.create(display_name="Ada")
    grace = crm.contacts.create(display_name="Grace")
    lin = crm.contacts.create(display_name="Lin")
    campaign = crm.campaigns.create(key="summer", name="Summer")
    cid = str(campaign.id)
    segment = crm.segments.create(
        key="seed", name="Seed", entity_kind="contact", mode=SegmentMode.STATIC
    )
    crm.segments.add_members(segment.id, (EntityReference("contact", ada.id),))
    base = f"/crm/campaigns/{cid}/"

    with override_settings(
        PYCRMKIT_CRM_FACTORY=lambda: crm,
        PYCRMKIT_CAMPAIGN_SECURITY=_policy(),
    ):
        added = _send(
            "post", "members", base + "members/",
            pk=cid,
            payload={
                "source": "web",
                "members": [
                    {"kind": "contact", "id": str(ada.id)},
                    {"kind": "contact", "id": str(grace.id)},
                ],
            },
        )
        assert added.status_code == 200, added.data
        assert len(added.data) == 2
        assert set(added.data[0]) == {
            "campaign_id", "entity", "added_at", "source", "metadata"
        }

        direct = _send("get", "members", base + "members/", pk=cid)
        assert direct.status_code == 200, direct.data
        assert direct.data["total"] == 2
        assert direct.data["has_next"] is False

        attached = _send(
            "post", "segment_sources", base + "segment-sources/",
            pk=cid, payload={"segment_id": str(segment.id)}
        )
        assert attached.status_code == 201, attached.data
        assert attached.data["member_count"] == 1
        sources = _send(
            "get", "segment_sources", base + "segment-sources/", pk=cid
        )
        assert sources.status_code == 200
        assert sources.data["total"] == 1

        audience = _send("get", "audience", base + "audience/", pk=cid)
        assert audience.status_code == 200, audience.data
        assert audience.data["total"] == 2
        count = _send(
            "get", "audience_count", base + "audience/count/", pk=cid
        )
        assert count.status_code == 200
        assert count.data == {"count": 2}

        crm.segments.add_members(segment.id, (EntityReference("contact", lin.id),))
        before = _send(
            "get", "audience_count", base + "audience/count/", pk=cid
        )
        assert before.data == {"count": 2}
        refreshed = _send(
            "post", "refresh_segment_source",
            base + f"segment-sources/{segment.id}/refresh/",
            pk=cid, segment_id=str(segment.id),
        )
        assert refreshed.status_code == 200, refreshed.data
        assert refreshed.data["member_count"] == 2
        assert _send(
            "get", "audience_count", base + "audience/count/", pk=cid
        ).data == {"count": 3}

        removed = _send(
            "post", "remove_members", base + "members/remove/",
            pk=cid,
            payload={"members": [{"kind": "contact", "id": str(ada.id)}]},
        )
        assert removed.status_code == 200
        assert removed.data == {"removed": 1}
        assert _send(
            "get", "audience_count", base + "audience/count/", pk=cid
        ).data == {"count": 3}

        detached = _send(
            "post", "detach_segment_source",
            base + f"segment-sources/{segment.id}/detach/",
            pk=cid, segment_id=str(segment.id),
        )
        assert detached.status_code == 200, detached.data
        assert detached.data == {"removed": True}
        assert _send(
            "get", "audience_count", base + "audience/count/", pk=cid
        ).data == {"count": 1}


def test_drf_campaign_audience_does_not_leak_cardinality_when_denied() -> None:
    crm = CRM.memory(webhook_auto_delivery=False)
    campaign = crm.campaigns.create(key="private", name="Private")
    cid = str(campaign.id)
    base = f"/crm/campaigns/{cid}/"

    with override_settings(
        PYCRMKIT_CRM_FACTORY=lambda: crm,
        PYCRMKIT_CAMPAIGN_SECURITY=_policy(denied="campaign.members.read"),
    ):
        for action, suffix in (
            ("members", "members/"),
            ("audience", "audience/"),
            ("audience_count", "audience/count/"),
        ):
            result = _send("get", action, base + suffix, pk=cid)
            assert result.status_code == 403
            assert "total" not in result.data
            assert "count" not in result.data

    with override_settings(
        PYCRMKIT_CRM_FACTORY=lambda: crm,
        PYCRMKIT_CAMPAIGN_SECURITY=_policy(denied="campaign.sources.read"),
    ):
        denied = _send(
            "get", "segment_sources", base + "segment-sources/", pk=cid
        )
        assert denied.status_code == 403

    with override_settings(
        PYCRMKIT_CRM_FACTORY=lambda: crm,
        PYCRMKIT_CAMPAIGN_SECURITY=_policy(),
    ):
        unauthorized = _send(
            "get", "audience_count", base + "audience/count/",
            pk=cid, authenticated=False,
        )
        assert unauthorized.status_code == 401


def test_drf_campaign_audience_validates_bulk_and_segment_ids() -> None:
    crm = CRM.memory(webhook_auto_delivery=False)
    cid = str(crm.campaigns.create(key="validation", name="Validation").id)
    base = f"/crm/campaigns/{cid}/"
    ref = {"kind": "contact", "id": "00000000-0000-4000-8000-000000000001"}

    with override_settings(
        PYCRMKIT_CRM_FACTORY=lambda: crm,
        PYCRMKIT_CAMPAIGN_SECURITY=_policy(),
    ):
        assert _send(
            "post", "members", base + "members/", pk=cid,
            payload={"members": []},
        ).status_code == 422
        assert _send(
            "post", "members", base + "members/", pk=cid,
            payload={"members": [ref, ref]},
        ).status_code == 422
        assert _send(
            "post", "segment_sources", base + "segment-sources/", pk=cid,
            payload={"segment_id": "invalid-id"},
        ).status_code == 422
        assert _send(
            "post", "refresh_segment_source",
            base + "segment-sources/invalid-id/refresh/",
            pk=cid, segment_id="invalid-id",
        ).status_code == 422
