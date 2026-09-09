from decimal import Decimal

import pytest

from pycrmkit.pipelines import (
    InvalidStageTransition,
    Pipeline,
    PipelineTransitionPolicy,
    Stage,
    StageTransition,
)


def pipeline() -> Pipeline:
    return Pipeline(
        id="sales",
        name="Sales",
        stages=(
            Stage("new", "New", 0, Decimal("0.10")),
            Stage("qualified", "Qualified", 10, Decimal("0.30")),
            Stage("proposal", "Proposal", 20, Decimal("0.60")),
            Stage("won", "Won", 30, terminal=True, outcome="won"),
        ),
        transitions=(
            StageTransition("new", "qualified"),
            StageTransition("qualified", "proposal"),
            StageTransition("proposal", "won"),
        ),
    )


def test_policy_allows_declared_transition() -> None:
    target = PipelineTransitionPolicy.resolve(
        pipeline(), from_stage="new", to_stage="qualified"
    )
    assert target.id == "qualified"
    assert target.default_probability == Decimal("0.30")


def test_policy_rejects_undeclared_transition_with_explicit_error() -> None:
    with pytest.raises(InvalidStageTransition) as exc:
        PipelineTransitionPolicy.resolve(pipeline(), from_stage="new", to_stage="won")
    assert exc.value.code == "pipeline.transition.invalid"
    assert exc.value.context["from_stage"] == "new"
    assert exc.value.context["to_stage"] == "won"


def test_unassigned_opportunity_can_only_enter_initial_stage() -> None:
    target = PipelineTransitionPolicy.resolve(
        pipeline(), from_stage=None, to_stage="new"
    )
    assert target.id == "new"
    with pytest.raises(InvalidStageTransition):
        PipelineTransitionPolicy.resolve(
            pipeline(), from_stage=None, to_stage="qualified"
        )
