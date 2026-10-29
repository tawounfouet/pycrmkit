"""LOT-31-012: mathematical definitions and privacy gates for performance evidence."""
from __future__ import annotations

import json
import re

import pytest

from benchmarks.campaign_rc_performance import (
    GUARDRAIL_P95_MS,
    MAX_TRACED_EXPORT_PEAK_MIB,
    _metric,
    _percentile_nearest_rank,
)


def test_p95_is_nearest_rank_not_an_interpolated_value() -> None:
    assert _percentile_nearest_rank([1.0, 2.0, 3.0, 4.0, 5.0], 95) == 5.0
    assert _percentile_nearest_rank([1.0, 2.0, 3.0, 4.0, 5.0], 50) == 3.0
    with pytest.raises(ValueError):
        _percentile_nearest_rank([], 95)
    with pytest.raises(ValueError):
        _percentile_nearest_rank([1.0], 0)


def test_measurement_has_real_repeated_samples_and_explicit_guardrail() -> None:
    visited: list[int] = []

    def operation(index: int) -> None:
        visited.append(index)

    result = _metric("audience_count", operation, samples=5, warmups=1)
    assert visited == [-1, 0, 1, 2, 3, 4]
    assert result["samples"] == 5
    assert result["warmups"] == 1
    assert result["p50_ms"] >= 0
    assert result["p95_ms"] >= result["p50_ms"]
    assert result["min_ms"] <= result["max_ms"]
    assert result["passed"] is True


def test_regression_guardrails_are_not_accidentally_slas() -> None:
    assert set(GUARDRAIL_P95_MS) == {
        "audience_count", "direct_prescan_1000",
        "export_direct_1000", "import_fresh_1000",
    }
    assert GUARDRAIL_P95_MS["audience_count"] == 500
    assert GUARDRAIL_P95_MS["import_fresh_1000"] >= 60000
    assert MAX_TRACED_EXPORT_PEAK_MIB == 64.0


def test_public_evidence_fields_do_not_contain_row_or_secret_content() -> None:
    """Fail closed on any accidental identity, URL, SQL or credential in artifact."""
    from benchmarks.campaign_rc_performance import _metric

    metrics = [_metric("audience_count", lambda _: None, samples=5, warmups=1)]
    evidence = {
        "schema": "pycrmkit.rc1.campaign_performance.v1",
        "backend": "memory",
        "metrics": metrics,
        "sql_profile": None,
        "passed": True,
    }
    serialized = json.dumps(evidence)
    assert not re.search(r"[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}", serialized, re.I)
    assert not re.search(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        serialized, re.I,
    )
    assert all(token not in serialized.casefold() for token in (
        "password", "secret", "postgresql://", "select *", "localhost",
    ))
