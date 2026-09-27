"""Deterministic scoring and threshold policy for duplicate candidates."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from pycrmkit.dedup.conflicts import ConflictSeverity, DedupConflict
from pycrmkit.dedup.matchers import DedupSignal, SignalMatch
from pycrmkit.exceptions import ValidationError


class DedupDecision(StrEnum):
    """Candidate classification before any merge operation."""

    NO_MATCH = "no_match"
    REVIEW = "review"
    DUPLICATE = "duplicate"
    CONFLICT = "conflict"


DEFAULT_SIGNAL_WEIGHTS: dict[DedupSignal, int] = {
    DedupSignal.EXTERNAL_IDENTITY: 100,
    DedupSignal.CUSTOM_IDENTIFIER: 100,
    DedupSignal.EMAIL: 70,
    DedupSignal.PHONE: 60,
    DedupSignal.FULL_NAME: 25,
    DedupSignal.ORGANIZATION: 15,
    DedupSignal.ADDRESS: 20,
}


@dataclass(frozen=True, slots=True)
class ScoreResult:
    """Score and classification for one candidate."""

    score: int
    decision: DedupDecision
    matched_signals: frozenset[DedupSignal]


@dataclass(frozen=True, slots=True)
class DedupScorePolicy:
    """Configurable, conservative additive scoring policy."""

    weights: Mapping[DedupSignal, int] = field(
        default_factory=lambda: dict(DEFAULT_SIGNAL_WEIGHTS)
    )
    review_threshold: int = 50
    duplicate_threshold: int = 100

    def __post_init__(self) -> None:
        if not 0 <= self.review_threshold <= self.duplicate_threshold <= 100:
            raise ValidationError(
                "dedup thresholds must satisfy 0 <= review <= duplicate <= 100",
                code="dedup.threshold.invalid",
            )
        if any(weight < 0 for weight in self.weights.values()):
            raise ValidationError(
                "dedup signal weights cannot be negative",
                code="dedup.weight.invalid",
            )

    def evaluate(
        self,
        matches: tuple[SignalMatch, ...],
        conflicts: tuple[DedupConflict, ...] = (),
    ) -> ScoreResult:
        signals = frozenset(match.signal for match in matches)
        score = min(
            100,
            sum(self.weights.get(signal, 0) for signal in signals),
        )

        if any(
            conflict.severity is ConflictSeverity.BLOCKING
            for conflict in conflicts
        ):
            decision = DedupDecision.CONFLICT
        elif score >= self.duplicate_threshold:
            decision = DedupDecision.DUPLICATE
        elif score >= self.review_threshold:
            decision = DedupDecision.REVIEW
        else:
            decision = DedupDecision.NO_MATCH

        return ScoreResult(
            score=score,
            decision=decision,
            matched_signals=signals,
        )


__all__ = [
    "DEFAULT_SIGNAL_WEIGHTS",
    "DedupDecision",
    "DedupScorePolicy",
    "ScoreResult",
]
