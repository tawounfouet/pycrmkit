"""Deduplication conflict handling."""

from __future__ import annotations

from pycrmkit.dedup import (
    ConflictSeverity,
    DedupDecision,
    DedupProfile,
    DedupScorePolicy,
    DedupSignal,
    StandardConflictDetector,
    StandardSignalMatcher,
)


def test_custom_identifier_disagreement_blocks_auto_duplicate() -> None:
    incoming = DedupProfile.from_mapping(
        {
            "email": "ada@example.com",
            "full_name": "Ada Lovelace",
            "organization": "Analytical Engines",
            "custom_identifiers": {"customer_number": "C-001"},
        }
    )
    candidate = DedupProfile.from_mapping(
        {
            "email": "ada@example.com",
            "full_name": "Ada Lovelace",
            "organization": "Analytical Engines",
            "custom_identifiers": {"customer_number": "C-999"},
        }
    )

    matches = StandardSignalMatcher().match(incoming, candidate)
    conflicts = StandardConflictDetector().detect(incoming, candidate)
    result = DedupScorePolicy().evaluate(matches, conflicts)

    assert result.score == 100
    assert result.decision is DedupDecision.CONFLICT
    assert any(
        conflict.signal is DedupSignal.CUSTOM_IDENTIFIER
        and conflict.severity is ConflictSeverity.BLOCKING
        for conflict in conflicts
    )


def test_external_identity_disagreement_is_recorded_as_warning() -> None:
    incoming = DedupProfile.from_mapping(
        {
            "external_identity": {"system": "hubspot", "external_id": "A"},
        }
    )
    candidate = DedupProfile.from_mapping(
        {
            "external_identity": {"system": "hubspot", "external_id": "B"},
        }
    )

    conflicts = StandardConflictDetector().detect(incoming, candidate)

    assert len(conflicts) == 1
    assert conflicts[0].signal is DedupSignal.EXTERNAL_IDENTITY
    assert conflicts[0].severity is ConflictSeverity.WARNING
    assert conflicts[0].key == "hubspot"
