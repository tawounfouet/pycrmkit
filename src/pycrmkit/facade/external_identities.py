"""External identities facade namespace."""

from __future__ import annotations

from collections.abc import Mapping

from pycrmkit.contacts import Contact
from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.core.references import EntityReference
from pycrmkit.external_identities import (
    ExternalIdentity,
    ExternalIdentityService,
    normalize_external_id,
    normalize_external_system,
)
from pycrmkit.facade._runtime import CRMRuntime
from pycrmkit.organizations import Organization

ExternalIdentityTarget = EntityReference | Contact | Organization


def _reference(entity: ExternalIdentityTarget) -> EntityReference:
    if isinstance(entity, EntityReference):
        return entity
    if isinstance(entity, Contact):
        return EntityReference("contact", entity.id)
    if isinstance(entity, Organization):
        return EntityReference("organization", entity.id)
    raise TypeError("external identity target must be an EntityReference, Contact, or Organization")


class ExternalIdentitiesAPI:
    """Transactional facade for provider-neutral external record identifiers."""

    def __init__(self, runtime: CRMRuntime) -> None:
        self._runtime = runtime

    def attach(
        self,
        entity: ExternalIdentityTarget,
        *,
        system: str,
        external_id: str,
        metadata: Mapping[str, object] | None = None,
    ) -> ExternalIdentity:
        reference = _reference(entity)
        normalized_system = normalize_external_system(system)
        normalized_external_id = normalize_external_id(external_id)
        with self._runtime.uow_factory() as uow:
            service = ExternalIdentityService(
                uow.external_identities,
                id_factory=self._runtime.id_factory,
                clock=self._runtime.clock,
            )
            existing = service.find(normalized_system, normalized_external_id)
            identity = service.attach(
                reference,
                system=normalized_system,
                external_id=normalized_external_id,
                metadata=metadata,
            )
            if existing is None:
                self._runtime.record_change(
                    uow,
                    event_type="external_identity.attached",
                    aggregate_type=reference.kind,
                    aggregate_id=reference.id,
                    changes={"fields": ["external_identities"]},
                    payload={
                        "system": identity.system,
                        "external_id": identity.external_id,
                    },
                )
            uow.commit()
            return identity

    def resolve(self, system: str, external_id: str) -> ExternalIdentity:
        with self._runtime.uow_factory() as uow:
            return ExternalIdentityService(uow.external_identities).resolve(
                system,
                external_id,
            )

    def list_for_entity(
        self,
        entity: ExternalIdentityTarget,
        page: OffsetPageRequest | None = None,
    ) -> Page[ExternalIdentity]:
        reference = _reference(entity)
        with self._runtime.uow_factory() as uow:
            return ExternalIdentityService(uow.external_identities).list_for_entity(
                reference,
                page,
            )

    def detach(self, system: str, external_id: str) -> bool:
        normalized_system = normalize_external_system(system)
        normalized_external_id = normalize_external_id(external_id)
        with self._runtime.uow_factory() as uow:
            service = ExternalIdentityService(
                uow.external_identities,
                id_factory=self._runtime.id_factory,
                clock=self._runtime.clock,
            )
            existing = service.find(normalized_system, normalized_external_id)
            if existing is None:
                return False
            removed = service.detach(normalized_system, normalized_external_id)
            if removed:
                self._runtime.record_change(
                    uow,
                    event_type="external_identity.detached",
                    aggregate_type=existing.entity_type,
                    aggregate_id=existing.entity_id,
                    changes={"fields": ["external_identities"]},
                    payload={
                        "system": existing.system,
                        "external_id": existing.external_id,
                    },
                )
            uow.commit()
            return removed


__all__ = ["ExternalIdentitiesAPI", "ExternalIdentityTarget"]
