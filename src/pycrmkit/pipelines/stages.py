"""Pipeline stage definitions."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal

from pycrmkit.exceptions import ValidationError
from pycrmkit.opportunities.entities import OpportunityStatus

_STAGE_KEY = re.compile(r"^[a-z0-9][a-z0-9._-]{0,119}$")


def normalize_stage_id(value: str) -> str:
    """Normalize and validate a stable pipeline-stage key."""

    normalized = unicodedata.normalize("NFKC", value).strip().casefold()
    if not _STAGE_KEY.fullmatch(normalized):
        raise ValidationError(
            "stage id must be a lowercase slug-like key",
            code="pipeline.stage.id.invalid",
            context={"stage_id": value},
        )
    return normalized


def _normalize_name(value: str) -> str:
    normalized = " ".join(unicodedata.normalize("NFKC", value).strip().split())
    if not normalized:
        raise ValidationError(
            "stage name is required",
            code="pipeline.stage.name.required",
        )
    if len(normalized) > 160:
        raise ValidationError(
            "stage name must be at most 160 characters",
            code="pipeline.stage.name.too_long",
        )
    return normalized


def _normalize_probability(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    if type(value) is not Decimal:
        raise ValidationError(
            "stage default_probability must be a Decimal",
            code="pipeline.stage.probability.decimal_required",
        )
    if not value.is_finite() or value < Decimal("0") or value > Decimal("1"):
        raise ValidationError(
            "stage default_probability must be between 0 and 1",
            code="pipeline.stage.probability.out_of_range",
        )
    return value


@dataclass(frozen=True, slots=True)
class Stage:
    """One ordered stage inside a commercial pipeline."""

    id: str
    name: str
    position: int
    default_probability: Decimal | None = None
    terminal: bool = False
    outcome: OpportunityStatus | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", normalize_stage_id(self.id))
        object.__setattr__(self, "name", _normalize_name(self.name))
        if type(self.position) is not int or self.position < 0:
            raise ValidationError(
                "stage position must be a non-negative integer",
                code="pipeline.stage.position.invalid",
            )
        probability = _normalize_probability(self.default_probability)
        object.__setattr__(self, "default_probability", probability)

        outcome = self.outcome
        if outcome is not None:
            outcome = OpportunityStatus(outcome)
            if outcome is OpportunityStatus.OPEN:
                raise ValidationError(
                    "terminal stage outcome cannot be open",
                    code="pipeline.stage.outcome.invalid",
                )
            object.__setattr__(self, "outcome", outcome)
        if self.terminal and outcome is None:
            raise ValidationError(
                "terminal stage requires a closed opportunity outcome",
                code="pipeline.stage.outcome.required",
            )
        if not self.terminal and outcome is not None:
            raise ValidationError(
                "non-terminal stage cannot declare an opportunity outcome",
                code="pipeline.stage.outcome.non_terminal",
            )

        if outcome is not None:
            expected = Decimal("1") if outcome is OpportunityStatus.WON else Decimal("0")
            if probability is None:
                object.__setattr__(self, "default_probability", expected)
            elif probability != expected:
                raise ValidationError(
                    "terminal stage probability must match its opportunity outcome",
                    code="pipeline.stage.probability.terminal_mismatch",
                    context={
                        "outcome": outcome.value,
                        "probability": str(probability),
                        "expected": str(expected),
                    },
                )
