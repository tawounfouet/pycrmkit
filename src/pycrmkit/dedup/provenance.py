"""Explainable provenance for duplicate candidate decisions."""

from __future__ import annotations

from dataclasses import dataclass

from pycrmkit.dedup.conflicts import DedupConflict
from pycrmkit.dedup.matchers import SignalMatch
from pycrmkit.dedup.scoring import DedupDecision, ScoreResult


@dataclass(frozen=True, slots=True)
class DedupProvenance:
    """Evidence retained for one candidate assessment."""

    candidate_entity_id: str
    score: int
    decision: DedupDecision
    matches: tuple[SignalMatch, ...]
    conflicts: tuple[DedupConflict, ...] = ()

    @classmethod
    def from_evaluation(
        cls,
        *,
        candidate_entity_id: str,
        result: ScoreResult,
        matches: tuple[SignalMatch, ...],
        conflicts: tuple[DedupConflict, ...],
    ) -> DedupProvenance:
        return cls(
            candidate_entity_id=candidate_entity_id,
            score=result.score,
            decision=result.decision,
            matches=matches,
            conflicts=conflicts,
        )

    def summary(self) -> str:
        """Return a compact deterministic explanation suitable for reports."""

        signals = sorted({match.signal.value for match in self.matches})
        signal_text = ",".join(signals) if signals else "none"
        return (
            f"dedup decision={self.decision.value} score={self.score} "
            f"signals={signal_text}"
        )

    def as_dict(self) -> dict[str, object]:
        """Return machine-readable evidence without application-specific objects."""

        return {
            "candidate_entity_id": self.candidate_entity_id,
            "score": self.score,
            "decision": self.decision.value,
            "matches": [
                {
                    "signal": match.signal.value,
                    "key": match.key,
                    "value": match.value,
                }
                for match in self.matches
            ],
            "conflicts": [
                {
                    "signal": conflict.signal.value,
                    "severity": conflict.severity.value,
                    "key": conflict.key,
                    "incoming_values": list(conflict.incoming_values),
                    "candidate_values": list(conflict.candidate_values),
                }
                for conflict in self.conflicts
            ],
        }


__all__ = ["DedupProvenance"]
