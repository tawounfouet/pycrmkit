"""Explainable, conservative duplicate detection."""

from pycrmkit.dedup.candidates import (
    CandidateAssessment,
    CandidateRecord,
    CandidateSource,
    DeduplicationEngine,
    InMemoryCandidateSource,
)
from pycrmkit.dedup.conflicts import (
    ConflictSeverity,
    DedupConflict,
    StandardConflictDetector,
)
from pycrmkit.dedup.matchers import (
    DedupProfile,
    DedupSignal,
    SignalMatch,
    StandardSignalMatcher,
    normalize_text,
)
from pycrmkit.dedup.merge import (
    MergePolicy,
    MergeResolution,
    MergeResult,
    MergeStatistics,
    merge_contact_profile,
)
from pycrmkit.dedup.provenance import DedupProvenance
from pycrmkit.dedup.scoring import (
    DEFAULT_SIGNAL_WEIGHTS,
    DedupDecision,
    DedupScorePolicy,
    ScoreResult,
)
from pycrmkit.dedup.services import MergeService

__all__ = [
    "DEFAULT_SIGNAL_WEIGHTS",
    "CandidateAssessment",
    "CandidateRecord",
    "CandidateSource",
    "ConflictSeverity",
    "DedupConflict",
    "DedupDecision",
    "DedupProfile",
    "DedupProvenance",
    "DedupScorePolicy",
    "DedupSignal",
    "DeduplicationEngine",
    "InMemoryCandidateSource",
    "MergePolicy",
    "MergeResolution",
    "MergeResult",
    "MergeService",
    "MergeStatistics",
    "ScoreResult",
    "SignalMatch",
    "StandardConflictDetector",
    "StandardSignalMatcher",
    "merge_contact_profile",
    "normalize_text",
]
