"""Pipelines facade namespace."""

from __future__ import annotations

from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.facade._runtime import CRMRuntime
from pycrmkit.pipelines import Pipeline, PipelineService, Stage, StageTransition


class PipelinesAPI:
    """Transactional facade for commercial pipeline definitions."""

    def __init__(self, runtime: CRMRuntime) -> None:
        self._runtime = runtime

    def define(
        self,
        *,
        id: str,
        name: str,
        stages: tuple[Stage, ...],
        transitions: tuple[StageTransition, ...] = (),
    ) -> Pipeline:
        with self._runtime.uow_factory() as uow:
            pipeline = PipelineService(uow.pipelines).define(
                id=id,
                name=name,
                stages=stages,
                transitions=transitions,
            )
            self._runtime.record_change(
                uow,
                event_type="pipeline.created",
                aggregate_type="pipeline",
                aggregate_id=pipeline.id,
                changes={"fields": ["name", "stages", "transitions"]},
                payload={
                    "stage_count": len(pipeline.stages),
                    "transition_count": len(pipeline.transitions),
                },
            )
            uow.commit()
            return pipeline

    def get(self, pipeline_id: str) -> Pipeline:
        with self._runtime.uow_factory() as uow:
            return PipelineService(uow.pipelines).get(pipeline_id)

    def list(self, page: OffsetPageRequest | None = None) -> Page[Pipeline]:
        with self._runtime.uow_factory() as uow:
            return PipelineService(uow.pipelines).list(page)
