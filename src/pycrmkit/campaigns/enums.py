"""Stable enums for CRM campaign metadata."""

from enum import StrEnum


class CampaignStatus(StrEnum):
    """Lifecycle state for a Campaign definition."""

    DRAFT = "draft"
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"


__all__ = ["CampaignStatus"]
