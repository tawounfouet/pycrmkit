"""Trusted Campaign request context for optional FastAPI endpoints.

Unlike the legacy CRMDependency, this Campaign-only bridge deliberately does
not read X-Actor-ID. It derives the actor from a host-authenticated principal.
"""

from __future__ import annotations

from collections.abc import Mapping
from uuid import uuid4

from fastapi import HTTPException, Request, status

from pycrmkit import CRM
from pycrmkit.integrations.campaign_security import (
    CampaignForbidden,
    CampaignSecurityBoundary,
    CampaignUnauthenticated,
    safe_campaign_correlation_id,
)
from pycrmkit.integrations.fastapi.dependencies import CRMFactory


class CampaignHTTPAccess:
    """Authorize a request before constructing an actor-bound CRM facade."""

    def __init__(
        self,
        factory: CRMFactory,
        security: CampaignSecurityBoundary,
    ) -> None:
        if not callable(factory):
            raise TypeError("Campaign HTTP access requires an application CRM factory")
        if not isinstance(security, CampaignSecurityBoundary):
            raise TypeError("Campaign HTTP access requires explicit security policies")
        self._factory = factory
        self._security = security

    def crm_for(
        self,
        request: Request,
        *,
        action: str,
        campaign_id: str | None = None,
        scope: Mapping[str, object] | None = None,
    ) -> CRM:
        """Authenticate then authorize before touching the CRM factory."""
        try:
            principal = self._security.require(
                request,
                action=action,
                campaign_id=campaign_id,
                scope=scope,
            )
        except CampaignUnauthenticated as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Campaign authentication required",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc
        except CampaignForbidden as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Campaign access denied",
            ) from exc

        correlation_id = safe_campaign_correlation_id(
            request.headers.get("X-Correlation-ID"),
            new_id=lambda: uuid4().hex,
        )
        return self._factory().with_context(
            actor_id=principal.actor_id,
            correlation_id=correlation_id,
        )


__all__ = ["CampaignHTTPAccess"]
