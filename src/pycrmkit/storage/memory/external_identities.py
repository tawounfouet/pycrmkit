"""In-memory ExternalIdentityRepository implementation."""

from __future__ import annotations

from copy import deepcopy

from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.core.references import EntityReference
from pycrmkit.exceptions import ConflictError, DuplicateError
from pycrmkit.external_identities import ExternalIdentity, same_entity
from pycrmkit.storage.memory._state import _MemoryState


class MemoryExternalIdentityRepository:
    """Copy-isolated external identity repository."""

    def __init__(self, state: _MemoryState | None = None) -> None:
        self._state = state or _MemoryState()

    def find(self, system: str, external_id: str) -> ExternalIdentity | None:
        identity = self._state.external_identities.get((system, external_id))
        return deepcopy(identity) if identity is not None else None

    def save(self, identity: ExternalIdentity) -> None:
        key = (identity.system, identity.external_id)
        existing = self._state.external_identities.get(key)
        if existing is not None and existing.id != identity.id:
            if not same_entity(existing, identity.entity):
                raise ConflictError(
                    "External identity is already attached to another entity",
                    code="external_identity.owner.conflict",
                    context={
                        "system": identity.system,
                        "external_id": identity.external_id,
                        "owner_type": existing.entity_type,
                        "owner_id": str(existing.entity_id),
                    },
                )
            raise DuplicateError(
                "External identity mapping already exists",
                code="external_identity.duplicate",
                context={
                    "system": identity.system,
                    "external_id": identity.external_id,
                },
            )
        self._state.external_identities[key] = deepcopy(identity)

    def list_for_entity(
        self,
        entity: EntityReference,
        page: OffsetPageRequest,
    ) -> Page[ExternalIdentity]:
        identities = [
            value
            for value in self._state.external_identities.values()
            if value.entity_type == entity.kind
            and str(value.entity_id) == str(entity.id)
        ]
        identities.sort(key=lambda value: (value.system, value.external_id, str(value.id)))
        total = len(identities)
        selected = identities[page.offset : page.offset + page.limit]
        return Page(
            items=tuple(deepcopy(selected)),
            limit=page.limit,
            offset=page.offset,
            total=total,
        )

    def remove(self, system: str, external_id: str) -> bool:
        return self._state.external_identities.pop((system, external_id), None) is not None


__all__ = ["MemoryExternalIdentityRepository"]
