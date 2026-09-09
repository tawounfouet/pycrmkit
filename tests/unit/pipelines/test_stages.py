from decimal import Decimal

import pytest

from pycrmkit.exceptions import ValidationError
from pycrmkit.opportunities import OpportunityStatus
from pycrmkit.pipelines import Pipeline, Stage, StageTransition


def test_stage_normalization_probability_and_terminal_defaults() -> None:
    new = Stage(" NEW ", "  New   Business ", 0, Decimal("0.10"))
    won = Stage("won", "Won", 10, terminal=True, outcome=OpportunityStatus.WON)
    lost = Stage("lost", "Lost", 20, terminal=True, outcome=OpportunityStatus.LOST)
    assert new.id == "new"
    assert new.name == "New Business"
    assert won.default_probability == Decimal("1")
    assert lost.default_probability == Decimal("0")


def test_stage_probability_requires_decimal_and_closed_interval() -> None:
    with pytest.raises(ValidationError) as exc:
        Stage("new", "New", 0, 0.1)  # type: ignore[arg-type]
    assert exc.value.code == "pipeline.stage.probability.decimal_required"
    with pytest.raises(ValidationError) as exc:
        Stage("new", "New", 0, Decimal("1.01"))
    assert exc.value.code == "pipeline.stage.probability.out_of_range"


def test_terminal_stage_requires_outcome_and_consistent_probability() -> None:
    with pytest.raises(ValidationError) as exc:
        Stage("done", "Done", 0, terminal=True)
    assert exc.value.code == "pipeline.stage.outcome.required"
    with pytest.raises(ValidationError) as exc:
        Stage(
            "won",
            "Won",
            0,
            Decimal("0.8"),
            terminal=True,
            outcome=OpportunityStatus.WON,
        )
    assert exc.value.code == "pipeline.stage.probability.terminal_mismatch"


def test_pipeline_orders_stages_and_rejects_duplicate_ids_positions() -> None:
    pipeline = Pipeline(
        id=" SALES ",
        name="Enterprise Sales",
        stages=(Stage("proposal", "Proposal", 20), Stage("new", "New", 0)),
    )
    assert pipeline.id == "sales"
    assert tuple(stage.id for stage in pipeline.stages) == ("new", "proposal")
    assert pipeline.initial_stage.id == "new"

    with pytest.raises(ValidationError) as exc:
        Pipeline(
            id="sales",
            name="Sales",
            stages=(Stage("new", "New", 0), Stage("new", "Again", 1)),
        )
    assert exc.value.code == "pipeline.stages.duplicate_id"

    with pytest.raises(ValidationError) as exc:
        Pipeline(
            id="sales",
            name="Sales",
            stages=(Stage("new", "New", 0), Stage("proposal", "Proposal", 0)),
        )
    assert exc.value.code == "pipeline.stages.duplicate_position"


def test_pipeline_rejects_unknown_and_terminal_source_transitions() -> None:
    with pytest.raises(ValidationError) as exc:
        Pipeline(
            id="sales",
            name="Sales",
            stages=(Stage("new", "New", 0),),
            transitions=(StageTransition("new", "missing"),),
        )
    assert exc.value.code == "pipeline.transition.stage_not_found"

    with pytest.raises(ValidationError) as exc:
        Pipeline(
            id="sales",
            name="Sales",
            stages=(
                Stage("won", "Won", 0, terminal=True, outcome="won"),
                Stage("other", "Other", 1),
            ),
            transitions=(StageTransition("won", "other"),),
        )
    assert exc.value.code == "pipeline.transition.from_terminal"
