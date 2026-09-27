"""Candidate sources and import-pipeline duplicate detection engine."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Protocol, runtime_checkable

from pycrmkit.dedup.conflicts import StandardConflictDetector
from pycrmkit.dedup.matchers import DedupProfile, StandardSignalMatcher
from pycrmkit.dedup.provenance import DedupProvenance
from pycrmkit.dedup.scoring import DedupDecision, DedupScorePolicy
from pycrmkit.exceptions import ValidationError
from pycrmkit.importers.base import DuplicateResult, ImportRow


@dataclass(frozen=True, slots=True)
class CandidateRecord:
    """Existing entity represented by fields available to deduplication."""

    entity_id: str
    values: Mapping[str, object]
    profile: DedupProfile = field(init=False, repr=False)

    def __post_init__(self) -> None:
        entity_id = self.entity_id.strip()
        if not entity_id:
            raise ValidationError(
                "dedup candidate entity_id cannot be empty",
                code="dedup.candidate.entity_id.empty",
            )
        values = MappingProxyType(dict(self.values))
        object.__setattr__(self, "entity_id", entity_id)
        object.__setattr__(self, "values", values)
        object.__setattr__(self, "profile", DedupProfile.from_mapping(values))


@runtime_checkable
class CandidateSource(Protocol):
    """Source of existing entities potentially matching one incoming row."""

    def candidates(self, row: ImportRow) -> Iterable[CandidateRecord]:
        """Return potential candidates; sources may pre-filter for scale."""


@dataclass(frozen=True, slots=True)
class InMemoryCandidateSource:
    """Simple deterministic candidate source for local use and tests."""

    records: tuple[CandidateRecord, ...]

    def candidates(self, row: ImportRow) -> Iterable[CandidateRecord]:
        del row
        return self.records


@dataclass(frozen=True, slots=True)
class CandidateAssessment:
    """One scored, explainable candidate result."""

    candidate: CandidateRecord
    provenance: DedupProvenance

    @property
    def score(self) -> int:
        return self.provenance.score

    @property
    def decision(self) -> DedupDecision:
        return self.provenance.decision


@dataclass(slots=True)
class DeduplicationEngine:
    """Evaluate candidates and implement the ImportDeduplicator protocol."""

    source: CandidateSource
    matcher: StandardSignalMatcher = field(default_factory=StandardSignalMatcher)
    conflict_detector: StandardConflictDetector = field(
        default_factory=StandardConflictDetector
    )
    score_policy: DedupScorePolicy = field(default_factory=DedupScorePolicy)

    def evaluate(self, row: ImportRow) -> tuple[CandidateAssessment, ...]:
        """Score all candidates with deterministic ordering and provenance."""

        incoming = DedupProfile.from_mapping(row.values)
        assessments: list[CandidateAssessment] = []

        for candidate in self.source.candidates(row):
            matches = self.matcher.match(incoming, candidate.profile)
            conflicts = self.conflict_detector.detect(incoming, candidate.profile)
            score = self.score_policy.evaluate(matches, conflicts)
            provenance = DedupProvenance.from_evaluation(
                candidate_entity_id=candidate.entity_id,
                result=score,
                matches=matches,
                conflicts=conflicts,
            )
            assessments.append(
                CandidateAssessment(
                    candidate=candidate,
                    provenance=provenance,
                )
            )

        assessments.sort(
            key=lambda item: (
                -item.score,
                item.candidate.entity_id,
            )
        )
        return tuple(assessments)

    def detect(self, row: ImportRow) -> DuplicateResult:
        """Auto-detect only one unambiguous high-confidence duplicate."""

        assessments = self.evaluate(row)
        duplicates = tuple(
            assessment
            for assessment in assessments
            if assessment.decision is DedupDecision.DUPLICATE
        )
        if len(duplicates) != 1:
            return DuplicateResult.no_match()

        match = duplicates[0]
        return DuplicateResult.match(
            existing_entity_id=match.candidate.entity_id,
            reason=match.provenance.summary(),
        )


__all__ = [
    "CandidateAssessment",
    "CandidateRecord",
    "CandidateSource",
    "DeduplicationEngine",
    "InMemoryCandidateSource",
]
