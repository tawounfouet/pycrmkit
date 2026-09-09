"""Pipeline stage-transition policies."""

from __future__ import annotations

from pycrmkit.pipelines.entities import Pipeline
from pycrmkit.pipelines.stages import Stage, normalize_stage_id
from pycrmkit.pipelines.transitions import InvalidStageTransition


class PipelineTransitionPolicy:
    """Validate one movement against a persisted pipeline definition."""

    @staticmethod
    def resolve(
        pipeline: Pipeline,
        *,
        from_stage: str | None,
        to_stage: str,
    ) -> Stage:
        target = pipeline.stage(to_stage)
        if from_stage is None:
            if target.id != pipeline.initial_stage.id:
                raise InvalidStageTransition(
                    pipeline_id=pipeline.id,
                    from_stage=None,
                    to_stage=target.id,
                    reason="an unassigned opportunity must enter the initial stage",
                )
            return target

        source_id = normalize_stage_id(from_stage)
        source = pipeline.stage(source_id)
        if source.terminal:
            raise InvalidStageTransition(
                pipeline_id=pipeline.id,
                from_stage=source.id,
                to_stage=target.id,
                reason="terminal stages cannot be exited",
            )
        if not pipeline.allows(source.id, target.id):
            raise InvalidStageTransition(
                pipeline_id=pipeline.id,
                from_stage=source.id,
                to_stage=target.id,
                reason="transition is not declared by the pipeline",
            )
        return target
