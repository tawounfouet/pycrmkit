"""Application service for external identity ownership and lookup."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from pycrmkit.core.ids import IDFactory, UUID4Factory
from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.core.references import EntityReference
from pycrmkit.core.time import Clock, SystemClock
from pycrmkit.exceptions import ConflictError, NotFoundError
from pycrmkit.external_identities.entities import (
    ExternalIdentity,
    ExternalIdentityId,
    normalize_external_id,
    normalize_external_system,
    same_entity,
)
from pycrmkit.external_identities.repository import ExternalIdentityRepository


@dataclass(slots=True)
class ExternalIdentityService:
    """Framework-agnostic external identity application service."""

    repository: ExternalIdentityRepository
    id_factory: IDFactory = field(default_factory=UUID4Factory)
    clock: Clock = field(default_factory=SystemClock)

    def find(self, system: str, external_id: str) -> ExternalIdentity | None:
        return self.repository.find(
            normalize_external_system(system),
            normalize_external_id(external_id),
        )

    def resolve(self, system: str, external_id: str) -> ExternalIdentity:
        identity = self.find(system, external_id)
        if identity is None:
            raise NotFoundError(
                "External identity not found",
                code="external_identity.not_found",
                context={
                    "system": normalize_external_system(system),
                    "external_id": normalize_external_id(external_id),
                },
            )
        return identity

    def attach(
        self,
        entity: EntityReference,
        *,
        system: str,
        external_id: str,
        metadata: Mapping[str, object] | None = None,
    ) -> ExternalIdentity:
        normalized_system = normalize_external_system(system)
        normalized_external_id = normalize_external_id(external_id)
        existing = self.repository.find(normalized_system, normalized_external_id)
        if existing is not None:
            if same_entity(existing, entity):
                return existing
            raise ConflictError(
                "External identity is already attached to another entity",
                code="external_identity.owner.conflict",
                context={
                    "system": normalized_system,
                    "external_id": normalized_external_id,
                    "owner_type": existing.entity_type,
                    "owner_id": str(existing.entity_id),
                },
            )

        now = self.clock.now()
        identity = ExternalIdentity(
            id=self.id_factory.new(ExternalIdentityId),
            created_at=now,
            updated_at=now,
            system=normalized_system,
            external_id=normalized_external_id,
            entity_type=entity.kind,
            entity_id=entity.id,
            metadata=dict(metadata or {}),
        )
        self.repository.save(identity)
        return identity

    def list_for_entity(
        self,
        entity: EntityReference,
        page: OffsetPageRequest | None = None,
    ) -> Page[ExternalIdentity]:
        return self.repository.list_for_entity(
            entity,
            page or OffsetPageRequest(),
        )

    def detach(self, system: str, external_id: str) -> bool:
        return self.repository.remove(
            normalize_external_system(system),
            normalize_external_id(external_id),
        )


__all__ = ["ExternalIdentityService"]
