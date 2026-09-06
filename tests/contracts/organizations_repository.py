"""Reusable OrganizationRepository behavioral contract suite."""

from __future__ import annotations

from datetime import timedelta

import pytest

from pycrmkit.core import OffsetPageRequest
from pycrmkit.exceptions import NotFoundError
from pycrmkit.organizations import (
    Organization,
    OrganizationQuery,
    OrganizationRepository,
    OrganizationStatus,
)


class OrganizationRepositoryContract:
    """Assertions every OrganizationRepository adapter must satisfy."""

    def test_save_and_get(
        self,
        repository: OrganizationRepository,
        organization: Organization,
    ) -> None:
        repository.save(organization)
        loaded = repository.get(organization.id)
        assert loaded == organization
        assert loaded.display_name == organization.display_name

    def test_missing_get_raises_and_find_returns_none(
        self,
        repository: OrganizationRepository,
        missing_organization_id,
    ) -> None:
        with pytest.raises(NotFoundError):
            repository.get(missing_organization_id)
        assert repository.find(missing_organization_id) is None

    def test_save_replaces_current_domain_state(
        self,
        repository: OrganizationRepository,
        organization: Organization,
    ) -> None:
        repository.save(organization)
        organization.source = "updated-source"
        repository.save(organization)
        assert repository.get(organization.id).source == "updated-source"

    def test_search_is_deterministic_and_exactly_paginated(
        self,
        repository: OrganizationRepository,
        organization: Organization,
        second_organization: Organization,
    ) -> None:
        repository.save(second_organization)
        repository.save(organization)
        first = repository.search(OrganizationQuery(), OffsetPageRequest(limit=1, offset=0))
        second = repository.search(OrganizationQuery(), OffsetPageRequest(limit=1, offset=1))
        expected = sorted(
            (organization, second_organization),
            key=lambda item: (item.created_at, item.id),
        )
        assert first.items == (expected[0],)
        assert second.items == (expected[1],)
        assert first.total == 2
        assert first.has_next is True
        assert second.has_previous is True

    def test_search_filters_normalized_domain(
        self,
        repository: OrganizationRepository,
        organization: Organization,
    ) -> None:
        repository.save(organization)
        page = repository.search(
            OrganizationQuery(domain="EXAMPLE.COM."),
            OffsetPageRequest(),
        )
        assert page.items == (organization,)

    def test_archive_is_hidden_by_default_and_can_be_included(
        self,
        repository: OrganizationRepository,
        organization: Organization,
    ) -> None:
        repository.save(organization)
        archived = repository.archive(
            organization.id,
            organization.created_at + timedelta(hours=1),
        )
        default_page = repository.search(OrganizationQuery(), OffsetPageRequest())
        inclusive_page = repository.search(
            OrganizationQuery(include_archived=True),
            OffsetPageRequest(),
        )
        assert archived.status is OrganizationStatus.ARCHIVED
        assert default_page.items == ()
        assert inclusive_page.items == (archived,)
