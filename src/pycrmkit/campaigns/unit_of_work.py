"""Campaign persistence capability protocol."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pycrmkit.campaigns.repository import CampaignRepository


@runtime_checkable
class CampaignUnitOfWork(Protocol):
    """Optional UoW capability for Campaign-aware adapters."""

    @property
    def campaigns(self) -> CampaignRepository:
        """Campaign definitions participating in the current transaction."""


__all__ = ["CampaignUnitOfWork"]
