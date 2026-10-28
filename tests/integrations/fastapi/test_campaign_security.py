"""FastAPI Campaign trust boundary tests without enabling HTTP routes."""

from __future__ import annotations

from collections.abc import Mapping
from uuid import UUID

import pytest
from fastapi import HTTPException, Request

from pycrmkit import CRM
from pycrmkit.integrations.campaign_security import (
    CampaignPrincipal,
    CampaignSecurityBoundary,
)
from pycrmkit.integrations.fastapi.campaign_security import CampaignHTTPAccess


def _request(
    *,
    actor_header: str | None = None,
    correlation_header: str | None = None,
) -> Request:
    headers: list[tuple[bytes, bytes]] = []
    if actor_header is not None:
        headers.append((b"x-actor-id", actor_header.encode("utf-8")))
    if correlation_header is not None:
        headers.append((b"x-correlation-id", correlation_header.encode("utf-8")))
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/campaigns/123",
            "headers": headers,
            "query_string": b"",
        }
    )


def _security(
    *,
    principal: CampaignPrincipal | None,
    permitted: bool,
) -> CampaignSecurityBoundary:
    def authorize(
        identity: CampaignPrincipal,
        *,
        action: str,
        campaign_id: str | None,
        scope: Mapping[str, object] | None,
    ) -> bool:
        return (
            permitted
            and identity.actor_id == "server-verified"
            and action == "campaign.read"
            and campaign_id == "owned"
        )

    return CampaignSecurityBoundary(
        lambda request: principal,
        authorize,
    )


def test_fastapi_forged_actor_header_is_not_authentication() -> None:
    factory_calls: list[str] = []

    def factory() -> CRM:
        factory_calls.append("called")
        return CRM.memory(webhook_auto_delivery=False)

    access = CampaignHTTPAccess(factory, _security(principal=None, permitted=True))
    with pytest.raises(HTTPException) as exc:
        access.crm_for(
            _request(actor_header="admin"),
            action="campaign.read",
            campaign_id="owned",
        )
    assert exc.value.status_code == 401
    assert factory_calls == []


def test_fastapi_denied_object_is_not_loaded() -> None:
    factory_calls: list[str] = []

    def factory() -> CRM:
        factory_calls.append("called")
        return CRM.memory(webhook_auto_delivery=False)

    access = CampaignHTTPAccess(
        factory,
        _security(principal=CampaignPrincipal("server-verified"), permitted=True),
    )
    with pytest.raises(HTTPException) as exc:
        access.crm_for(
            _request(actor_header="server-verified"),
            action="campaign.read",
            campaign_id="foreign",
        )
    assert exc.value.status_code == 403
    assert factory_calls == []


def test_fastapi_trusted_identity_overrides_forged_header() -> None:
    crm = CRM.memory(webhook_auto_delivery=False)
    access = CampaignHTTPAccess(
        lambda: crm,
        _security(principal=CampaignPrincipal("server-verified"), permitted=True),
    )
    authenticated = access.crm_for(
        _request(actor_header="admin", correlation_header="trace-123"),
        action="campaign.read",
        campaign_id="owned",
    )
    assert authenticated.context.actor_id == "server-verified"
    assert authenticated.context.correlation_id == "trace-123"
    assert crm.context.actor_id != "admin"


def test_fastapi_replaces_unsafe_correlation_header() -> None:
    crm = CRM.memory(webhook_auto_delivery=False)
    access = CampaignHTTPAccess(
        lambda: crm,
        _security(principal=CampaignPrincipal("server-verified"), permitted=True),
    )
    authenticated = access.crm_for(
        _request(correlation_header="password=secret /"),
        action="campaign.read",
        campaign_id="owned",
    )
    value = authenticated.context.correlation_id
    assert value is not None
    assert len(value) == 32
    UUID(value)
