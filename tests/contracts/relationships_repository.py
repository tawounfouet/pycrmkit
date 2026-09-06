"""Reusable RelationshipRepository behavioral contract suite."""

from __future__ import annotations

from datetime import timedelta

import pytest

from pycrmkit.core import OffsetPageRequest
from pycrmkit.exceptions import NotFoundError
from pycrmkit.relationships import (
    Relationship,
    RelationshipQuery,
    RelationshipRepository,
    RelationshipType,
)


class RelationshipRepositoryContract:
    """Assertions every RelationshipRepository adapter must satisfy."""

    def test_save_and_get(
        self,
        repository: RelationshipRepository,
        relationship: Relationship,
    ) -> None:
        repository.save(relationship)
        loaded = repository.get(relationship.id)
        assert loaded == relationship
        assert loaded.source == relationship.source
        assert loaded.target == relationship.target

    def test_missing_get_raises_and_find_returns_none(
        self,
        repository: RelationshipRepository,
        missing_relationship_id,
    ) -> None:
        with pytest.raises(NotFoundError):
            repository.get(missing_relationship_id)
        assert repository.find(missing_relationship_id) is None

    def test_save_replaces_current_domain_state(
        self,
        repository: RelationshipRepository,
        relationship: Relationship,
    ) -> None:
        repository.save(relationship)
        relationship.title = "Updated title"
        repository.save(relationship)
        assert repository.get(relationship.id).title == "Updated title"

    def test_search_is_deterministic_and_exactly_paginated(
        self,
        repository: RelationshipRepository,
        relationship: Relationship,
        second_relationship: Relationship,
    ) -> None:
        repository.save(second_relationship)
        repository.save(relationship)
        first = repository.search(RelationshipQuery(), OffsetPageRequest(limit=1, offset=0))
        second = repository.search(RelationshipQuery(), OffsetPageRequest(limit=1, offset=1))
        expected = sorted(
            (relationship, second_relationship),
            key=lambda item: (item.created_at, item.id),
        )
        assert first.items == (expected[0],)
        assert second.items == (expected[1],)
        assert first.total == 2
        assert first.has_next is True
        assert second.has_previous is True

    def test_search_filters_entity_and_type(
        self,
        repository: RelationshipRepository,
        relationship: Relationship,
    ) -> None:
        repository.save(relationship)
        page = repository.search(
            RelationshipQuery(
                entity=relationship.source,
                relationship_type=RelationshipType("EMPLOYMENT"),
            ),
            OffsetPageRequest(),
        )
        assert page.items == (relationship,)

    def test_end_is_hidden_by_default_and_historically_queryable(
        self,
        repository: RelationshipRepository,
        relationship: Relationship,
    ) -> None:
        repository.save(relationship)
        ended_at = relationship.valid_from + timedelta(hours=2)
        ended = repository.end(relationship.id, ended_at)
        default_page = repository.search(RelationshipQuery(), OffsetPageRequest())
        inclusive_page = repository.search(
            RelationshipQuery(include_ended=True),
            OffsetPageRequest(),
        )
        historical_page = repository.search(
            RelationshipQuery(active_at=relationship.valid_from + timedelta(hours=1)),
            OffsetPageRequest(),
        )
        assert ended.is_ended
        assert default_page.items == ()
        assert inclusive_page.items == (ended,)
        assert historical_page.items == (ended,)
