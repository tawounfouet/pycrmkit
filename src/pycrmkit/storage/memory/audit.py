"""In-memory AuditRepository implementation."""

from __future__ import annotations

from pycrmkit.audit.entries import AuditEntry, AuditEntryId
from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.exceptions import DuplicateError, NotFoundError
from pycrmkit.storage.memory._state import _MemoryState


class MemoryAuditRepository:
    """Append-only, deterministic in-memory audit history."""

    def __init__(self, state: _MemoryState | None = None) -> None:
        self._state = state or _MemoryState()

    def get(self, entry_id: AuditEntryId) -> AuditEntry:
        entry = self.find(entry_id)
        if entry is None:
            raise NotFoundError(
                "Audit entry not found",
                code="audit.not_found",
                context={"audit_entry_id": str(entry_id)},
            )
        return entry

    def find(self, entry_id: AuditEntryId) -> AuditEntry | None:
        return self._state.audit_entries.get(entry_id)

    def append(self, entry: AuditEntry) -> None:
        if entry.id in self._state.audit_entries:
            raise DuplicateError(
                "Audit entry already exists",
                code="audit.duplicate",
                context={"audit_entry_id": str(entry.id)},
            )
        self._state.audit_entries[entry.id] = entry

    def list_for_entity(
        self,
        entity_type: str,
        entity_id: str,
        page: OffsetPageRequest,
    ) -> Page[AuditEntry]:
        entity_kind = entity_type.strip().casefold()
        entity_key = entity_id.strip()
        entries = [
            entry
            for entry in self._state.audit_entries.values()
            if entry.entity_type == entity_kind and entry.entity_id == entity_key
        ]
        return self._page(entries, page)

    def list_by_actor(self, actor_id: str, page: OffsetPageRequest) -> Page[AuditEntry]:
        actor = actor_id.strip()
        entries = [
            entry for entry in self._state.audit_entries.values() if entry.actor_id == actor
        ]
        return self._page(entries, page)

    def list_by_correlation(
        self,
        correlation_id: str,
        page: OffsetPageRequest,
    ) -> Page[AuditEntry]:
        correlation = correlation_id.strip()
        entries = [
            entry
            for entry in self._state.audit_entries.values()
            if entry.correlation_id == correlation
        ]
        return self._page(entries, page)

    @staticmethod
    def _page(entries: list[AuditEntry], page: OffsetPageRequest) -> Page[AuditEntry]:
        entries.sort(key=lambda item: (item.occurred_at, item.id))
        total = len(entries)
        selected = entries[page.offset : page.offset + page.limit]
        return Page(items=tuple(selected), limit=page.limit, offset=page.offset, total=total)
