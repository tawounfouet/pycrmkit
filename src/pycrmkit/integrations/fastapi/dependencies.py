"""FastAPI dependency bridge for constructing request-scoped CRM facade views."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import Header

from pycrmkit import CRM

CRMFactory = Callable[[], CRM]


class CRMDependency:
    """Callable FastAPI dependency that adds request metadata to a CRM facade.

    The factory controls the underlying CRM wiring (Memory, SQLAlchemy, custom
    adapters). This bridge only applies optional HTTP actor/correlation headers
    through the stable CRM.with_context(...) API.
    """

    def __init__(self, factory: CRMFactory) -> None:
        self._factory = factory

    def __call__(
        self,
        actor_id: Annotated[
            str | None,
            Header(alias="X-Actor-ID", max_length=255),
        ] = None,
        correlation_id: Annotated[
            str | None,
            Header(alias="X-Correlation-ID", max_length=255),
        ] = None,
    ) -> CRM:
        crm = self._factory()
        context: dict[str, str] = {}
        if actor_id is not None:
            context["actor_id"] = actor_id
        if correlation_id is not None:
            context["correlation_id"] = correlation_id
        if not context:
            return crm
        return crm.with_context(**context)


__all__ = ["CRMDependency", "CRMFactory"]
