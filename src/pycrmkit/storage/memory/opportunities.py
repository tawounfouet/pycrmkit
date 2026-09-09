"""Official in-memory Opportunity repository."""

from __future__ import annotations

from copy import deepcopy

from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.exceptions import NotFoundError
from pycrmkit.opportunities import (
    Opportunity,
    OpportunityId,
    OpportunityQuery,
    OpportunityRepository,
)
from pycrmkit.storage.memory._state import _MemoryState


class MemoryOpportunityRepository(OpportunityRepository):
    """Copy-isolated Opportunity repository backed by one memory snapshot."""

    def __init__(self, state: _MemoryState | None = None) -> None:
        self._state = state or _MemoryState()

    def get(self, opportunity_id: OpportunityId) -> Opportunity:
        opportunity = self._state.opportunities.get(opportunity_id)
        if opportunity is None:
            raise NotFoundError(
                "opportunity not found",
                code="opportunity.not_found",
                context={"opportunity_id": str(opportunity_id)},
            )
        return deepcopy(opportunity)

    def find(self, opportunity_id: OpportunityId) -> Opportunity | None:
        opportunity = self._state.opportunities.get(opportunity_id)
        return deepcopy(opportunity) if opportunity is not None else None

    def save(self, opportunity: Opportunity) -> None:
        self._state.opportunities[opportunity.id] = deepcopy(opportunity)

    def list(
        self,
        query: OpportunityQuery,
        page: OffsetPageRequest,
    ) -> Page[Opportunity]:
        opportunities = list(self._state.opportunities.values())
        if query.status is not None:
            opportunities = [
                item for item in opportunities if item.status is query.status
            ]
        if query.contact_id is not None:
            opportunities = [
                item for item in opportunities if item.contact_id == query.contact_id
            ]
        if query.organization_id is not None:
            opportunities = [
                item
                for item in opportunities
                if item.organization_id == query.organization_id
            ]
        if query.pipeline_id is not None:
            opportunities = [
                item
                for item in opportunities
                if item.pipeline_id is not None
                and item.pipeline_id.casefold() == query.pipeline_id
            ]
        if query.stage_id is not None:
            opportunities = [
                item
                for item in opportunities
                if item.stage_id is not None and item.stage_id.casefold() == query.stage_id
            ]
        if query.owner_id is not None:
            opportunities = [
                item
                for item in opportunities
                if item.owner_id is not None and item.owner_id.casefold() == query.owner_id
            ]
        if query.currency is not None:
            opportunities = [
                item for item in opportunities if item.currency == query.currency
            ]
        if query.expected_close_date is not None:
            opportunities = [
                item
                for item in opportunities
                if item.expected_close_date == query.expected_close_date
            ]

        opportunities.sort(key=lambda item: item.id)
        opportunities.sort(key=lambda item: item.created_at, reverse=True)
        total = len(opportunities)
        selected = opportunities[page.offset : page.offset + page.limit]
        return Page(
            items=tuple(deepcopy(selected)),
            limit=page.limit,
            offset=page.offset,
            total=total,
        )
