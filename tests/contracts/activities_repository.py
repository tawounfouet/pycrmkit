"""Reusable ActivityRepository behavioral contract suite."""

from __future__ import annotations

import pytest

from pycrmkit.activities import Activity, ActivityQuery, ActivityRepository, ActivityType
from pycrmkit.core import OffsetPageRequest
from pycrmkit.exceptions import NotFoundError


class ActivityRepositoryContract:
    """Assertions every ActivityRepository adapter must satisfy."""

    def test_save_and_get(
        self,
        repository: ActivityRepository,
        activity: Activity,
    ) -> None:
        repository.save(activity)

        assert repository.get(activity.id) == activity

    def test_missing_get_raises_and_find_returns_none(
        self,
        repository: ActivityRepository,
        missing_activity_id,
    ) -> None:
        with pytest.raises(NotFoundError):
            repository.get(missing_activity_id)
        assert repository.find(missing_activity_id) is None

    def test_save_replaces_current_state(
        self,
        repository: ActivityRepository,
        activity: Activity,
    ) -> None:
        repository.save(activity)
        activity.source = "updated"
        repository.save(activity)

        assert repository.get(activity.id).source == "updated"

    def test_list_is_reverse_chronological_and_exactly_paginated(
        self,
        repository: ActivityRepository,
        activity: Activity,
        second_activity: Activity,
    ) -> None:
        repository.save(activity)
        repository.save(second_activity)

        first = repository.list(ActivityQuery(), OffsetPageRequest(limit=1, offset=0))
        second = repository.list(ActivityQuery(), OffsetPageRequest(limit=1, offset=1))

        assert first.items == (second_activity,)
        assert second.items == (activity,)
        assert first.total == 2
        assert first.has_next is True
        assert second.has_previous is True

    def test_list_filters_by_type_and_participant(
        self,
        repository: ActivityRepository,
        activity: Activity,
        second_activity: Activity,
        participant_reference,
    ) -> None:
        repository.save(activity)
        repository.save(second_activity)

        page = repository.list(
            ActivityQuery(
                type=ActivityType.CALL,
                participant=participant_reference,
            ),
            OffsetPageRequest(),
        )

        assert page.items == (activity,)

    def test_list_filters_related_reference_and_interval(
        self,
        repository: ActivityRepository,
        activity: Activity,
        second_activity: Activity,
        related_reference,
    ) -> None:
        repository.save(activity)
        repository.save(second_activity)

        page = repository.list(
            ActivityQuery(
                reference=related_reference,
                occurred_from=activity.occurred_at,
                occurred_until=second_activity.occurred_at,
            ),
            OffsetPageRequest(),
        )

        assert page.items == (activity,)
