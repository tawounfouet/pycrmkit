"""Portable Campaign repository filters."""

from __future__ import annotations

from dataclasses import dataclass

from pycrmkit.campaigns.enums import CampaignStatus
from pycrmkit.core.ids import EntityId


@dataclass(frozen=True, slots=True)
class CampaignQuery:
    """Backend-independent filters for Campaign definitions."""

    status: CampaignStatus | None = None
    owner_id: EntityId | None = None
    include_archived: bool = False

    def __post_init__(self) -> None:
        if self.status is not None:
            object.__setattr__(self, "status", CampaignStatus(self.status))


__all__ = ["CampaignQuery"]
