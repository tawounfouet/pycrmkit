"""Enums for reusable SavedQuery definitions."""

from enum import StrEnum


class SavedQueryVisibility(StrEnum):
    """Application-level visibility hint.

    Full authorization remains an application/IAM responsibility.
    """

    PRIVATE = "private"
    SHARED = "shared"


class SavedQueryStatus(StrEnum):
    """Lifecycle status for one SavedQuery definition."""

    ACTIVE = "active"
    ARCHIVED = "archived"


__all__ = ["SavedQueryStatus", "SavedQueryVisibility"]
