"""Fail-closed Campaign policy and trusted trace metadata contracts."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from pycrmkit.integrations.campaign_security import (
    CampaignForbidden,
    CampaignPrincipal,
    CampaignSecurityBoundary,
    CampaignUnauthenticated,
    safe_campaign_correlation_id,
)


def test_campaign_security_denies_anonymous_before_policy() -> None:
    calls: list[str] = []

    def authorize(principal: CampaignPrincipal, **kwargs: object) -> bool:
        calls.append("called")
        return True

    security = CampaignSecurityBoundary(lambda request: None, authorize)
    with pytest.raises(CampaignUnauthenticated):
        security.require(SimpleNamespace(), action="campaign.read")
    assert calls == []


def test_campaign_security_denies_missing_policy_permission() -> None:
    security = CampaignSecurityBoundary(
        lambda request: CampaignPrincipal("trusted-actor"),
        lambda principal, **kwargs: False,
    )
    with pytest.raises(CampaignForbidden):
        security.require(
            SimpleNamespace(),
            action="campaign.members.read",
            campaign_id="campaign-A",
        )


def test_campaign_security_denies_truthy_non_boolean_policy_result() -> None:
    security = CampaignSecurityBoundary(
        lambda request: CampaignPrincipal("trusted-actor"),
        lambda principal, **kwargs: 1,  # type: ignore[return-value]
    )
    with pytest.raises(CampaignForbidden):
        security.require(SimpleNamespace(), action="campaign.read")


def test_campaign_security_checks_exact_action_resource_and_scope() -> None:
    observed: list[tuple[str, str | None, object]] = []

    def authorize(
        principal: CampaignPrincipal,
        *,
        action: str,
        campaign_id: str | None,
        scope: object,
    ) -> bool:
        observed.append((action, campaign_id, scope))
        return (
            principal.actor_id == "trusted-actor"
            and action == "campaign.read"
            and campaign_id == "owned"
        )

    security = CampaignSecurityBoundary(
        lambda request: CampaignPrincipal("trusted-actor"),
        authorize,
    )
    scope = {"include_archived": False}
    principal = security.require(
        object(), action="campaign.read", campaign_id="owned", scope=scope
    )
    assert principal.actor_id == "trusted-actor"
    assert observed == [("campaign.read", "owned", scope)]
    with pytest.raises(CampaignForbidden):
        security.require(object(), action="campaign.read", campaign_id="other")


@pytest.mark.parametrize("actor", ["", "  ", "header\ninjection", "x" * 256])
def test_campaign_principal_rejects_invalid_actor(actor: str) -> None:
    with pytest.raises(ValueError):
        CampaignPrincipal(actor)


def test_campaign_security_rejects_miswired_principal() -> None:
    security = CampaignSecurityBoundary(
        lambda request: "unverified-actor",  # type: ignore[arg-type]
        lambda principal, **kwargs: True,
    )
    with pytest.raises(TypeError):
        security.require(object(), action="campaign.read")


def test_campaign_security_requires_explicit_callable_policies() -> None:
    with pytest.raises(TypeError):
        CampaignSecurityBoundary(None, None)  # type: ignore[arg-type]


def test_correlation_id_accepts_safe_metadata_and_replaces_unsafe() -> None:
    assert safe_campaign_correlation_id("trace-42", new_id=lambda: "new-id") == (
        "trace-42"
    )
    assert safe_campaign_correlation_id(
        "password=bearer secret /\n", new_id=lambda: "new-id"
    ) == "new-id"
    assert safe_campaign_correlation_id("x" * 129, new_id=lambda: "new-id") == (
        "new-id"
    )
