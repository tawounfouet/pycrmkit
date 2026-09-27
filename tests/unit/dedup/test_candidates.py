"""Duplicate candidate detection and provenance."""

from __future__ import annotations

from pycrmkit.dedup import (
    CandidateRecord,
    DedupDecision,
    DeduplicationEngine,
    InMemoryCandidateSource,
)
from pycrmkit.importers import ImportRow


def _candidate(entity_id: str, email: str, name: str, organization: str) -> CandidateRecord:
    return CandidateRecord(
        entity_id,
        {
            "email": email,
            "full_name": name,
            "organization": organization,
        },
    )


def test_engine_returns_explainable_unique_duplicate() -> None:
    source = InMemoryCandidateSource(
        (
            _candidate(
                "contact-1",
                "ada@example.com",
                "Ada Lovelace",
                "Analytical Engines",
            ),
            _candidate(
                "contact-2",
                "grace@example.com",
                "Grace Hopper",
                "US Navy",
            ),
        )
    )
    engine = DeduplicationEngine(source)
    row = ImportRow(
        1,
        {
            "email": "ADA@EXAMPLE.COM",
            "display_name": "ada lovelace",
            "company": "analytical engines",
        },
    )

    assessments = engine.evaluate(row)
    duplicate = engine.detect(row)

    assert assessments[0].candidate.entity_id == "contact-1"
    assert assessments[0].decision is DedupDecision.DUPLICATE
    assert assessments[0].score == 100
    assert assessments[0].provenance.as_dict()["decision"] == "duplicate"
    assert duplicate.is_duplicate is True
    assert duplicate.existing_entity_id == "contact-1"
    assert "signals=email,full_name,organization" in (duplicate.reason or "")


def test_engine_does_not_auto_select_ambiguous_duplicate_candidates() -> None:
    record = {
        "email": "ada@example.com",
        "full_name": "Ada Lovelace",
        "organization": "Analytical Engines",
    }
    engine = DeduplicationEngine(
        InMemoryCandidateSource(
            (
                CandidateRecord("contact-1", record),
                CandidateRecord("contact-2", record),
            )
        )
    )

    result = engine.detect(ImportRow(1, record))

    assert result.is_duplicate is False
    assert result.existing_entity_id is None


def test_review_candidate_is_visible_but_not_auto_duplicate() -> None:
    engine = DeduplicationEngine(
        InMemoryCandidateSource(
            (
                CandidateRecord(
                    "contact-1",
                    {"email": "ada@example.com"},
                ),
            )
        )
    )
    row = ImportRow(1, {"email": "ADA@EXAMPLE.COM"})

    assessment = engine.evaluate(row)[0]
    result = engine.detect(row)

    assert assessment.decision is DedupDecision.REVIEW
    assert assessment.score == 70
    assert result.is_duplicate is False
