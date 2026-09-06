"""Backend-independent Tag queries."""

from __future__ import annotations

from dataclasses import dataclass

from pycrmkit.tags.value_objects import TagName


@dataclass(frozen=True, slots=True)
class TagQuery:
    """Portable filters for Tag repositories."""

    name: TagName | None = None
