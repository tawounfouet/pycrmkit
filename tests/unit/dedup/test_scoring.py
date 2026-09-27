"""Deduplication scoring and threshold policy."""

from __future__ import annotations

import pytest

from pycrmkit.dedup import (
    DedupDecision,
    DedupScorePolicy,
    DedupSignal,
    SignalMatch,
)
from pycrmkit.exceptions import ValidationError


def test_external_identity_is_high_confidence_duplicate_signal() -> None:
    result = DedupScorePolicy().evaluate(
        (
            SignalMatch(
                DedupSignal.EXTERNAL_IDENTITY,
                "42",
                key="hubspot",
            ),
        )
    )

    assert result.score == 100
    assert result.decision is DedupDecision.DUPLICATE


def test_email_alone_requires_review_but_combined_identity_reaches_duplicate() -> None:
    policy = DedupScorePolicy()

    email_only = policy.evaluate(
        (SignalMatch(DedupSignal.EMAIL, "ada@example.com"),)
    )
    combined = policy.evaluate(
        (
            SignalMatch(DedupSignal.EMAIL, "ada@example.com"),
            SignalMatch(DedupSignal.FULL_NAME, "ada lovelace"),
            SignalMatch(DedupSignal.ORGANIZATION, "analytical engines"),
        )
    )

    assert email_only.score == 70
    assert email_only.decision is DedupDecision.REVIEW
    assert combined.score == 100
    assert combined.decision is DedupDecision.DUPLICATE


def test_multiple_matches_of_same_signal_do_not_inflate_score() -> None:
    result = DedupScorePolicy().evaluate(
        (
            SignalMatch(DedupSignal.EMAIL, "a@example.com"),
            SignalMatch(DedupSignal.EMAIL, "b@example.com"),
        )
    )

    assert result.score == 70


def test_threshold_policy_is_configurable_and_validated() -> None:
    policy = DedupScorePolicy(review_threshold=60, duplicate_threshold=80)
    result = policy.evaluate(
        (
            SignalMatch(DedupSignal.PHONE, "+33612345678"),
            SignalMatch(DedupSignal.FULL_NAME, "ada lovelace"),
        )
    )

    assert result.score == 85
    assert result.decision is DedupDecision.DUPLICATE

    with pytest.raises(ValidationError) as error:
        DedupScorePolicy(review_threshold=90, duplicate_threshold=80)
    assert error.value.code == "dedup.threshold.invalid"
