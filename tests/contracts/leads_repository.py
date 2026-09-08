"""Reusable LeadRepository behavioral contract suite."""

from __future__ import annotations

import pytest

from pycrmkit.core import OffsetPageRequest
from pycrmkit.exceptions import NotFoundError
from pycrmkit.leads import Lead, LeadQuery, LeadRepository, LeadStatus


class LeadRepositoryContract:
    """Assertions every LeadRepository adapter must satisfy."""

    def test_save_and_get(self, repository: LeadRepository, lead: Lead) -> None:
        repository.save(lead)
        assert repository.get(lead.id) == lead

    def test_missing_get_raises_and_find_returns_none(
        self,
        repository: LeadRepository,
        missing_lead_id,
    ) -> None:
        with pytest.raises(NotFoundError):
            repository.get(missing_lead_id)
        assert repository.find(missing_lead_id) is None

    def test_save_replaces_current_state(
        self,
        repository: LeadRepository,
        lead: Lead,
        later,
    ) -> None:
        repository.save(lead)
        lead.qualify(later)
        repository.save(lead)
        assert repository.get(lead.id).status is LeadStatus.QUALIFIED

    def test_list_is_creation_ordered_and_exactly_paginated(
        self,
        repository: LeadRepository,
        lead: Lead,
        second_lead: Lead,
    ) -> None:
        repository.save(lead)
        repository.save(second_lead)

        first = repository.list(LeadQuery(), OffsetPageRequest(limit=1, offset=0))
        second = repository.list(LeadQuery(), OffsetPageRequest(limit=1, offset=1))

        assert first.items == (second_lead,)
        assert second.items == (lead,)
        assert first.total == 2
        assert first.has_next is True
        assert second.has_previous is True

    def test_list_filters_status_contact_organization_and_source(
        self,
        repository: LeadRepository,
        lead: Lead,
        second_lead: Lead,
        later,
    ) -> None:
        lead.qualify(later)
        repository.save(lead)
        repository.save(second_lead)

        page = repository.list(
            LeadQuery(
                status=LeadStatus.QUALIFIED,
                contact_id=lead.contact_id,
                organization_id=lead.organization_id,
                source="WEBSITE",
            ),
            OffsetPageRequest(),
        )
        assert page.items == (lead,)

    def test_repository_preserves_disqualified_and_converted_states(
        self,
        repository: LeadRepository,
        disqualified_lead: Lead,
        converted_lead: Lead,
    ) -> None:
        repository.save(disqualified_lead)
        repository.save(converted_lead)
        assert repository.get(disqualified_lead.id).status is LeadStatus.DISQUALIFIED
        assert repository.get(converted_lead.id).status is LeadStatus.CONVERTED
