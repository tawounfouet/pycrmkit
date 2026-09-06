"""Backend-independent Organization query objects."""

from __future__ import annotations

from dataclasses import dataclass

from pycrmkit.core.ids import EntityId
from pycrmkit.organizations.entities import OrganizationStatus
from pycrmkit.organizations.policies import normalize_optional_text
from pycrmkit.organizations.value_objects import normalize_domain


@dataclass(frozen=True, slots=True)
class OrganizationQuery:
    """Normalized semantic filters understood by every OrganizationRepository adapter."""

    status: OrganizationStatus | None = None
    domain: str | None = None
    name: str | None = None
    registration_number: str | None = None
    owner_id: EntityId | None = None
    source: str | None = None
    include_archived: bool = False

    def __post_init__(self) -> None:
        if self.domain is not None:
            object.__setattr__(self, "domain", normalize_domain(self.domain))
        for attribute in ("name", "registration_number", "source"):
            value = getattr(self, attribute)
            if value is not None:
                object.__setattr__(self, attribute, normalize_optional_text(value))
