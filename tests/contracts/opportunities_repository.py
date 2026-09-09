"""Reusable Opportunity repository contract suite."""

from datetime import date

import pytest

from pycrmkit.core.pagination import OffsetPageRequest
from pycrmkit.exceptions import NotFoundError
from pycrmkit.opportunities import OpportunityQuery, OpportunityStatus


class OpportunityRepositoryContract:
    def test_get_find_and_missing(self, repository, opportunity, missing_opportunity_id):
        repository.save(opportunity)
        assert repository.get(opportunity.id) == opportunity
        assert repository.find(opportunity.id) == opportunity
        assert repository.find(missing_opportunity_id) is None
        with pytest.raises(NotFoundError) as exc:
            repository.get(missing_opportunity_id)
        assert exc.value.code == "opportunity.not_found"

    def test_list_is_reverse_creation_ordered_and_paginated(
        self,
        repository,
        opportunity,
        second_opportunity,
    ):
        repository.save(opportunity)
        repository.save(second_opportunity)
        page = repository.list(OpportunityQuery(), OffsetPageRequest(limit=1))
        assert page.total == 2
        assert page.items == (second_opportunity,)
        assert page.has_next

    def test_filters_cover_persistence_contract(
        self,
        repository,
        opportunity,
        second_opportunity,
        closed_opportunity,
    ):
        for item in (opportunity, second_opportunity, closed_opportunity):
            repository.save(item)

        def only(query):
            return repository.list(query, OffsetPageRequest(limit=20)).items

        assert only(OpportunityQuery(status=OpportunityStatus.WON)) == (closed_opportunity,)
        assert only(OpportunityQuery(contact_id=opportunity.contact_id)) == (opportunity,)
        assert only(OpportunityQuery(organization_id=opportunity.organization_id)) == (opportunity,)
        assert only(OpportunityQuery(pipeline_id="sales")) == (opportunity,)
        assert only(OpportunityQuery(stage_id="proposal")) == (opportunity,)
        assert only(OpportunityQuery(owner_id="seller-1")) == (opportunity,)
        assert only(OpportunityQuery(currency="eur")) == (opportunity,)
        assert only(OpportunityQuery(expected_close_date=date(2026, 11, 30))) == (
            opportunity,
        )
