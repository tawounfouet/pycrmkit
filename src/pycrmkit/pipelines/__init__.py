"""Sales pipeline definitions and transition policies."""

from pycrmkit.pipelines.entities import Pipeline, normalize_pipeline_id
from pycrmkit.pipelines.policies import PipelineTransitionPolicy
from pycrmkit.pipelines.repository import PipelineRepository
from pycrmkit.pipelines.services import PipelineService
from pycrmkit.pipelines.stages import Stage, StageOutcome, normalize_stage_id
from pycrmkit.pipelines.transitions import InvalidStageTransition, StageTransition

__all__ = [
    "InvalidStageTransition",
    "Pipeline",
    "PipelineRepository",
    "PipelineService",
    "PipelineTransitionPolicy",
    "Stage",
    "StageOutcome",
    "StageTransition",
    "normalize_pipeline_id",
    "normalize_stage_id",
]
