"""Tests for the RC-06 production release gate aggregator."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.v1_production_gate import (
    EXPECTED_IMPLEMENTED_GATES,
    EXPECTED_PENDING_GATES,
    REQUIRED_CONVERGENCE_LAYERS,
    assert_production_gate_contract,
)

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = json.loads(
    (ROOT / "tests/qualification/production_scenarios_v1.json").read_text(
        encoding="utf-8"
    )
)


def test_rc06_gate_contract_converges_rc01_through_rc05() -> None:
    result = assert_production_gate_contract()

    assert set(result["implemented_gates"]) == EXPECTED_IMPLEMENTED_GATES
    assert set(result["pending_gates"]) == EXPECTED_PENDING_GATES
    assert result["blocking_failures_allowed"] == 0
    assert result["promotion_ready"] is True
    assert str(result["package_version"]).startswith("1.")
    assert result["target_release"] == "1.0.0rc1"


def test_rc06_convergence_layers_cover_every_v1_release_dimension() -> None:
    rc06 = MANIFEST["rc06_production_release_gate"]

    assert rc06["status"] == "implemented"
    assert set(rc06["convergence_layers"]) == REQUIRED_CONVERGENCE_LAYERS
    assert rc06["blocking_failures_allowed"] == 0
    assert rc06["final_job"] == "production-release-gate"
