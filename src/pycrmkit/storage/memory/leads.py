"""Official in-memory Lead repository."""

from __future__ import annotations

from copy import deepcopy

from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.exceptions import NotFoundError
from pycrmkit.leads import Lead, LeadId, LeadQuery, LeadRepository
from pycrmkit.storage.memory._state import _MemoryState


class MemoryLeadRepository(LeadRepository):
    """Copy-isolated Lead repository backed by one memory state snapshot."""

    def __init__(self, state: _MemoryState | None = None) -> None:
        self._state = state or _MemoryState()

    def get(self, lead_id: LeadId) -> Lead:
        lead = self._state.leads.get(lead_id)
        if lead is None:
            raise NotFoundError(
                "lead not found",
                code="lead.not_found",
                context={"lead_id": str(lead_id)},
            )
        return deepcopy(lead)

    def find(self, lead_id: LeadId) -> Lead | None:
        lead = self._state.leads.get(lead_id)
        return deepcopy(lead) if lead is not None else None

    def save(self, lead: Lead) -> None:
        self._state.leads[lead.id] = deepcopy(lead)

    def list(self, query: LeadQuery, page: OffsetPageRequest) -> Page[Lead]:
        leads = list(self._state.leads.values())
        if query.status is not None:
            leads = [item for item in leads if item.status is query.status]
        if query.contact_id is not None:
            leads = [item for item in leads if item.contact_id == query.contact_id]
        if query.organization_id is not None:
            leads = [
                item for item in leads if item.organization_id == query.organization_id
            ]
        if query.source is not None:
            leads = [
                item
                for item in leads
                if item.source is not None and item.source.casefold() == query.source
            ]

        leads.sort(key=lambda item: item.id)
        leads.sort(key=lambda item: item.created_at, reverse=True)
        total = len(leads)
        selected = leads[page.offset : page.offset + page.limit]
        return Page(
            items=tuple(deepcopy(selected)),
            limit=page.limit,
            offset=page.offset,
            total=total,
        )
