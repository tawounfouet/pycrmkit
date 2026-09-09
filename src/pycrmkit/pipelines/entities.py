"""Commercial pipeline definition aggregate."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from pycrmkit.exceptions import NotFoundError, ValidationError
from pycrmkit.pipelines.stages import Stage, normalize_stage_id
from pycrmkit.pipelines.transitions import StageTransition

_PIPELINE_KEY = re.compile(r"^[a-z0-9][a-z0-9._-]{0,119}$")


def normalize_pipeline_id(value: str) -> str:
    """Normalize and validate a stable pipeline key."""
    normalized = unicodedata.normalize("NFKC", value).strip().casefold()
    if not _PIPELINE_KEY.fullmatch(normalized):
        raise ValidationError(
            "pipeline id must be a lowercase slug-like key",
            code="pipeline.id.invalid",
            context={"pipeline_id": value},
        )
    return normalized


def _normalize_name(value: str) -> str:
    normalized = " ".join(unicodedata.normalize("NFKC", value).strip().split())
    if not normalized:
        raise ValidationError("pipeline name is required", code="pipeline.name.required")
    if len(normalized) > 200:
        raise ValidationError(
            "pipeline name must be at most 200 characters",
            code="pipeline.name.too_long",
        )
    return normalized


@dataclass(frozen=True, slots=True)
class Pipeline:
    """Immutable ordered commercial process with explicit transition rules."""

    id: str
    name: str
    stages: tuple[Stage, ...]
    transitions: tuple[StageTransition, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", normalize_pipeline_id(self.id))
        object.__setattr__(self, "name", _normalize_name(self.name))
        stages = tuple(sorted(self.stages, key=lambda stage: (stage.position, stage.id)))
        if not stages:
            raise ValidationError(
                "pipeline requires at least one stage",
                code="pipeline.stages.required",
            )
        stage_ids = [stage.id for stage in stages]
        if len(stage_ids) != len(set(stage_ids)):
            raise ValidationError(
                "pipeline stage ids must be unique",
                code="pipeline.stages.duplicate_id",
            )
        positions = [stage.position for stage in stages]
        if len(positions) != len(set(positions)):
            raise ValidationError(
                "pipeline stage positions must be unique",
                code="pipeline.stages.duplicate_position",
            )
        object.__setattr__(self, "stages", stages)

        transitions = tuple(self.transitions)
        transition_pairs = {(item.from_stage, item.to_stage) for item in transitions}
        if len(transition_pairs) != len(transitions):
            raise ValidationError(
                "pipeline transitions must be unique",
                code="pipeline.transitions.duplicate",
            )
        known = set(stage_ids)
        for transition in transitions:
            if transition.from_stage not in known or transition.to_stage not in known:
                raise ValidationError(
                    "pipeline transition references an unknown stage",
                    code="pipeline.transition.stage_not_found",
                    context={
                        "from_stage": transition.from_stage,
                        "to_stage": transition.to_stage,
                    },
                )
            if self.stage(transition.from_stage).terminal:
                raise ValidationError(
                    "terminal stages cannot have outgoing transitions",
                    code="pipeline.transition.from_terminal",
                    context={"from_stage": transition.from_stage},
                )
        object.__setattr__(self, "transitions", transitions)

    @property
    def initial_stage(self) -> Stage:
        return self.stages[0]

    def stage(self, stage_id: str) -> Stage:
        key = normalize_stage_id(stage_id)
        for stage in self.stages:
            if stage.id == key:
                return stage
        raise NotFoundError(
            "pipeline stage not found",
            code="pipeline.stage.not_found",
            context={"pipeline_id": self.id, "stage_id": key},
        )

    def allows(self, from_stage: str | None, to_stage: str) -> bool:
        target = normalize_stage_id(to_stage)
        if from_stage is None:
            return target == self.initial_stage.id
        source = normalize_stage_id(from_stage)
        return any(
            item.from_stage == source and item.to_stage == target
            for item in self.transitions
        )
