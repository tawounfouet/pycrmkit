"""LOT-31-004 - Framework-neutral Campaign authorization fail-closed rules."""

from __future__ import annotations

import pytest

from pycrmkit.integrations.campaign_security import (
    CampaignForbidden,
    CampaignPrincipal,
    CampaignSecurityBoundary,
    CampaignUnauthenticated,
    safe_campaign_correlation_id,
)


@pytest.mark.parametrize("result", [None, False, 0, 1, "yes", []])
def test_campaign_host_authorizer_requires_literal_true(result: object) -> None:
    boundary = CampaignSecurityBoundary(
        lambda _request: CampaignPrincipal("trusted"),
        lambda _principal, *, action, campaign_id, scope: result,
    )
    with pytest.raises(CampaignForbidden):
        boundary.require(object(), action="campaign.read", campaign_id="owned")


def test_campaign_principal_missing_is_unauthenticated_not_authorized() -> None:
    authorizer_calls: list[str] = []

    def authorize(_principal: object, *, action: str, campaign_id: str | None,
                  scope: object) -> bool:
        authorizer_calls.append(action)
        return True

    boundary = CampaignSecurityBoundary(lambda _request: None, authorize)
    with pytest.raises(CampaignUnauthenticated):
        boundary.require(object(), action="campaign.read", campaign_id="private")
    assert not authorizer_calls


@pytest.mark.parametrize("actor", ["", "  ", "a\nb", "a\x00b"])
def test_campaign_principal_rejects_unsafe_identity(actor: str) -> None:
    with pytest.raises(ValueError):
        CampaignPrincipal(actor)


def test_campaign_resolver_must_return_typed_principal() -> None:
    boundary = CampaignSecurityBoundary(
        lambda _request: "unverified",
        lambda _principal, *, action, campaign_id, scope: True,
    )
    with pytest.raises(TypeError, match="CampaignPrincipal"):
        boundary.require(object(), action="campaign.read", campaign_id="private")


def test_campaign_invalid_correlation_id_is_replaced_not_reflected() -> None:
    result = safe_campaign_correlation_id(
        "secret=token /\n", new_id=lambda: "generated-rc1"
    )
    assert result == "generated-rc1"
    assert safe_campaign_correlation_id(
        "safe-trace:007", new_id=lambda: "unused"
    ) == "safe-trace:007"
