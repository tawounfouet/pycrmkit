"""Official in-memory Pipeline repository."""

from __future__ import annotations

from copy import deepcopy

from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.exceptions import NotFoundError
from pycrmkit.pipelines import Pipeline, PipelineRepository, normalize_pipeline_id
from pycrmkit.storage.memory._state import _MemoryState


class MemoryPipelineRepository(PipelineRepository):
    """Copy-isolated pipeline repository backed by one memory snapshot."""

    def __init__(self, state: _MemoryState | None = None) -> None:
        self._state = state or _MemoryState()

    def get(self, pipeline_id: str) -> Pipeline:
        key = normalize_pipeline_id(pipeline_id)
        pipeline = self._state.pipelines.get(key)
        if pipeline is None:
            raise NotFoundError(
                "pipeline not found",
                code="pipeline.not_found",
                context={"pipeline_id": key},
            )
        return deepcopy(pipeline)

    def find(self, pipeline_id: str) -> Pipeline | None:
        pipeline = self._state.pipelines.get(normalize_pipeline_id(pipeline_id))
        return deepcopy(pipeline) if pipeline is not None else None

    def save(self, pipeline: Pipeline) -> None:
        self._state.pipelines[pipeline.id] = deepcopy(pipeline)

    def list(self, page: OffsetPageRequest) -> Page[Pipeline]:
        pipelines = sorted(self._state.pipelines.values(), key=lambda item: item.id)
        total = len(pipelines)
        selected = pipelines[page.offset : page.offset + page.limit]
        return Page(
            items=tuple(deepcopy(selected)),
            limit=page.limit,
            offset=page.offset,
            total=total,
        )
