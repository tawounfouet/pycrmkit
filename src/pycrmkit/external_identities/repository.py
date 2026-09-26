"""Persistence contract for external identity mappings."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.core.references import EntityReference
from pycrmkit.external_identities.entities import ExternalIdentity


@runtime_checkable
class ExternalIdentityRepository(Protocol):
    """Backend-neutral external identity persistence semantics."""

    def find(self, system: str, external_id: str) -> ExternalIdentity | None:
        """Resolve a normalized system/external-ID pair or return None."""

    def save(self, identity: ExternalIdentity) -> None:
        """Persist one mapping while enforcing unique external ownership."""

    def list_for_entity(
        self,
        entity: EntityReference,
        page: OffsetPageRequest,
    ) -> Page[ExternalIdentity]:
        """List mappings for one entity in deterministic order."""

    def remove(self, system: str, external_id: str) -> bool:
        """Detach one mapping idempotently."""


__all__ = ["ExternalIdentityRepository"]
