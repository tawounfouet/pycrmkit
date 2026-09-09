"""Application service for pipeline definitions."""

from __future__ import annotations

from dataclasses import dataclass

from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.exceptions import DuplicateError
from pycrmkit.pipelines.entities import Pipeline
from pycrmkit.pipelines.repository import PipelineRepository
from pycrmkit.pipelines.stages import Stage
from pycrmkit.pipelines.transitions import StageTransition


@dataclass(slots=True)
class PipelineService:
    """Framework-agnostic service for defining and reading pipelines."""

    repository: PipelineRepository

    def define(
        self,
        *,
        id: str,
        name: str,
        stages: tuple[Stage, ...],
        transitions: tuple[StageTransition, ...] = (),
    ) -> Pipeline:
        pipeline = Pipeline(
            id=id,
            name=name,
            stages=stages,
            transitions=transitions,
        )
        if self.repository.find(pipeline.id) is not None:
            raise DuplicateError(
                "pipeline already exists",
                code="pipeline.duplicate",
                context={"pipeline_id": pipeline.id},
            )
        self.repository.save(pipeline)
        return pipeline

    def get(self, pipeline_id: str) -> Pipeline:
        return self.repository.get(pipeline_id)

    def list(self, page: OffsetPageRequest | None = None) -> Page[Pipeline]:
        return self.repository.list(page or OffsetPageRequest())
