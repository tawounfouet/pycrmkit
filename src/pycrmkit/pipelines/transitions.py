"""Pipeline transition declarations and explicit transition errors."""

from __future__ import annotations

from dataclasses import dataclass

from pycrmkit.exceptions import InvalidStateError
from pycrmkit.pipelines.stages import normalize_stage_id


@dataclass(frozen=True, slots=True)
class StageTransition:
    """Explicit directed transition between two pipeline stages."""

    from_stage: str
    to_stage: str

    def __post_init__(self) -> None:
        source = normalize_stage_id(self.from_stage)
        target = normalize_stage_id(self.to_stage)
        object.__setattr__(self, "from_stage", source)
        object.__setattr__(self, "to_stage", target)
        if source == target:
            raise InvalidStageTransition(
                pipeline_id=None,
                from_stage=source,
                to_stage=target,
                reason="self transition is not allowed",
            )


class InvalidStageTransition(InvalidStateError):
    """Raised when a pipeline does not permit a requested stage movement."""

    default_code = "pipeline.transition.invalid"

    def __init__(
        self,
        *,
        pipeline_id: str | None,
        from_stage: str | None,
        to_stage: str,
        reason: str | None = None,
    ) -> None:
        source = from_stage or "<unassigned>"
        message = f"invalid stage transition from {source} to {to_stage}"
        if reason:
            message = f"{message}: {reason}"
        super().__init__(
            message,
            context={
                "pipeline_id": pipeline_id,
                "from_stage": from_stage,
                "to_stage": to_stage,
                "reason": reason,
            },
        )
