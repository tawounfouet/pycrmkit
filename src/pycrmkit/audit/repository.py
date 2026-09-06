"""Persistence contract for append-only audit history."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pycrmkit.audit.entries import AuditEntry, AuditEntryId
from pycrmkit.core.pagination import OffsetPageRequest, Page


@runtime_checkable
class AuditRepository(Protocol):
    """Backend-neutral append-oriented audit repository contract."""

    def get(self, entry_id: AuditEntryId) -> AuditEntry:
        """Return one audit entry or raise NotFoundError."""

    def find(self, entry_id: AuditEntryId) -> AuditEntry | None:
        """Return one audit entry or None."""

    def append(self, entry: AuditEntry) -> None:
        """Append one immutable audit entry, rejecting duplicate IDs."""

    def list_for_entity(
        self,
        entity_type: str,
        entity_id: str,
        page: OffsetPageRequest,
    ) -> Page[AuditEntry]:
        """Return entity history ordered by occurred_at then ID."""

    def list_by_actor(self, actor_id: str, page: OffsetPageRequest) -> Page[AuditEntry]:
        """Return audit entries produced by one actor."""

    def list_by_correlation(
        self,
        correlation_id: str,
        page: OffsetPageRequest,
    ) -> Page[AuditEntry]:
        """Return audit entries belonging to one correlation context."""
