"""Audit facade namespace."""

from __future__ import annotations

from pycrmkit.audit import AuditEntry, AuditEntryId
from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.facade._runtime import CRMRuntime


class AuditAPI:
    """Read-only facade namespace for append-only audit history."""

    def __init__(self, runtime: CRMRuntime) -> None:
        self._runtime = runtime

    def get(self, entry_id: AuditEntryId) -> AuditEntry:
        with self._runtime.uow_factory() as uow:
            return uow.audit.get(entry_id)

    def for_entity(
        self,
        entity_type: str,
        entity_id: object,
        page: OffsetPageRequest | None = None,
    ) -> Page[AuditEntry]:
        with self._runtime.uow_factory() as uow:
            return uow.audit.list_for_entity(
                entity_type,
                str(entity_id),
                page or OffsetPageRequest(),
            )

    def by_actor(
        self,
        actor_id: str,
        page: OffsetPageRequest | None = None,
    ) -> Page[AuditEntry]:
        with self._runtime.uow_factory() as uow:
            return uow.audit.list_by_actor(actor_id, page or OffsetPageRequest())

    def by_correlation(
        self,
        correlation_id: str,
        page: OffsetPageRequest | None = None,
    ) -> Page[AuditEntry]:
        with self._runtime.uow_factory() as uow:
            return uow.audit.list_by_correlation(
                correlation_id,
                page or OffsetPageRequest(),
            )
