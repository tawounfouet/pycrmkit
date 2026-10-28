"""Framework-neutral, fail-closed authorization boundary for Campaign HTTP.

The application host owns authentication. A resolved principal must come from
a verified host authentication mechanism (JWT validation, session, etc), never
from an unsigned caller-provided X-Actor-ID header.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Protocol

_ACTOR_ID = re.compile(r"^[^\x00-\x1f\x7f]{1,255}$")
_CORRELATION_ID = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}$")


@dataclass(frozen=True, slots=True)
class CampaignPrincipal:
    """An identity already authenticated by the embedding application."""

    actor_id: str

    def __post_init__(self) -> None:
        if (
            not isinstance(self.actor_id, str)
            or not _ACTOR_ID.fullmatch(self.actor_id)
            or not self.actor_id.strip()
        ):
            raise ValueError("authenticated actor_id must be a nonempty safe string")


class CampaignUnauthenticated(PermissionError):
    """No verified host principal was supplied (HTTP 401)."""


class CampaignForbidden(PermissionError):
    """The verified principal has no permission for an operation (HTTP 403)."""


class CampaignPrincipalResolver(Protocol):
    """Host-provided authentication bridge. No implicit header identity."""

    def __call__(self, request: object) -> CampaignPrincipal | None:
        """Return an already verified principal or None for anonymous users."""


class CampaignAuthorizer(Protocol):
    """Check one action and resource/scope before any facade access."""

    def __call__(
        self,
        principal: CampaignPrincipal,
        *,
        action: str,
        campaign_id: str | None,
        scope: Mapping[str, object] | None,
    ) -> bool:
        """Return True to grant. False and None are denied."""


@dataclass(frozen=True, slots=True)
class CampaignSecurityBoundary:
    """Only explicit, injected policies enable the Campaign HTTP surface."""

    resolve_principal: CampaignPrincipalResolver
    authorize: CampaignAuthorizer

    def __post_init__(self) -> None:
        if not callable(self.resolve_principal) or not callable(self.authorize):
            raise TypeError("Campaign HTTP security requires both callable policies")

    def require(
        self,
        request: object,
        *,
        action: str,
        campaign_id: str | None = None,
        scope: Mapping[str, object] | None = None,
    ) -> CampaignPrincipal:
        """Authenticate and authorize. Denials never reach Campaign services."""
        principal = self.resolve_principal(request)
        if principal is None:
            raise CampaignUnauthenticated("authenticated principal required")
        if not isinstance(principal, CampaignPrincipal):
            raise TypeError("principal resolver must return CampaignPrincipal or None")
        if not action or not action.strip():
            raise ValueError("Campaign action is required")
        if self.authorize(
            principal,
            action=action,
            campaign_id=campaign_id,
            scope=scope,
        ) is not True:
            raise CampaignForbidden("Campaign operation is not authorized")
        return principal


def safe_campaign_correlation_id(
    supplied: str | None,
    *,
    new_id: Callable[[], str],
) -> str:
    """Keep only bounded trace IDs; replace malformed inputs with a server ID."""
    if supplied is not None and _CORRELATION_ID.fullmatch(supplied):
        return supplied
    generated = new_id()
    if not _CORRELATION_ID.fullmatch(generated):
        raise ValueError("server correlation ID generator produced invalid output")
    return generated


__all__ = [
    "CampaignPrincipal",
    "CampaignPrincipalResolver",
    "CampaignAuthorizer",
    "CampaignSecurityBoundary",
    "CampaignUnauthenticated",
    "CampaignForbidden",
    "safe_campaign_correlation_id",
]
