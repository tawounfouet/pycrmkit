"""Reusable Pipeline repository contract suite."""

import pytest

from pycrmkit.core.pagination import OffsetPageRequest
from pycrmkit.exceptions import NotFoundError


class PipelineRepositoryContract:
    def test_get_find_and_missing(self, repository, pipeline, missing_pipeline_id):
        repository.save(pipeline)
        assert repository.get(pipeline.id) == pipeline
        assert repository.find(pipeline.id) == pipeline
        assert repository.find(missing_pipeline_id) is None
        with pytest.raises(NotFoundError) as exc:
            repository.get(missing_pipeline_id)
        assert exc.value.code == "pipeline.not_found"

    def test_list_is_id_ordered_and_exactly_paginated(
        self,
        repository,
        pipeline,
        second_pipeline,
    ):
        repository.save(second_pipeline)
        repository.save(pipeline)
        page = repository.list(OffsetPageRequest(limit=1, offset=0))
        assert page.total == 2
        assert page.items == (pipeline,)
        assert page.has_next
        second_page = repository.list(OffsetPageRequest(limit=1, offset=1))
        assert second_page.items == (second_pipeline,)
        assert second_page.has_previous
