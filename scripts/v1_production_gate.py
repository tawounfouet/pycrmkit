"""Executable RC-06 production release gate contract."""

from __future__ import annotations

import json
from pathlib import Path

import pycrmkit

ROOT = Path(__file__).resolve().parents[1]
QUALIFICATION = ROOT / "tests" / "qualification"
GATE_PATH = QUALIFICATION / "production_release_gate_v1.json"
SCENARIOS_PATH = QUALIFICATION / "production_scenarios_v1.json"

EXPECTED_IMPLEMENTED_GATES = {
    "RC-01",
    "RC-02",
    "RC-03",
    "RC-04",
    "RC-05",
    "RC-06",
    "RC-07",
}
EXPECTED_PENDING_GATES: set[str] = set()
EXPECTED_WORKFLOW = ".github/workflows/production-qualification.yml"

REQUIRED_CONVERGENCE_LAYERS = {
    "contract",
    "cross-layer-e2e",
    "persistence-migrations",
    "framework-integrations",
    "installed-artifacts",
    "public-api-freeze",
    "security-privacy",
    "performance-baseline",
    "compatibility-matrix",
    "lint",
    "typing",
    "docs",
}


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def assert_production_gate_contract() -> dict[str, object]:
    gate = _load(GATE_PATH)
    scenarios = _load(SCENARIOS_PATH)

    if gate["target_release"] != "1.0.0rc1":
        raise SystemExit("RC-06 target release must remain 1.0.0rc1")
    if gate["baseline_release"] != "1.0.0b3":
        raise SystemExit("RC-06 baseline must remain 1.0.0b3")
    if scenarios["target_release"] != gate["target_release"]:
        raise SystemExit("Scenario and gate target releases diverge")
    if pycrmkit.__version__ != gate["target_release"]:
        raise SystemExit(
            "RC-07 promotion must execute the qualified target candidate version"
        )

    gates = {item["id"]: item for item in gate["rc_gates"]}
    implemented = {
        gate_id for gate_id, item in gates.items() if item["status"] == "implemented"
    }
    pending = {
        gate_id for gate_id, item in gates.items() if item["status"] == "pending"
    }
    if implemented != EXPECTED_IMPLEMENTED_GATES:
        raise SystemExit(f"Unexpected implemented RC gates: {sorted(implemented)}")
    if pending != EXPECTED_PENDING_GATES:
        raise SystemExit(f"Unexpected pending RC gates: {sorted(pending)}")

    missing_evidence = sorted(
        path
        for gate_id in EXPECTED_IMPLEMENTED_GATES
        for path in gates[gate_id]["evidence"]
        if not (ROOT / path).is_file()
    )
    if missing_evidence:
        raise SystemExit(f"Missing RC evidence files: {missing_evidence}")

    rc06 = scenarios["rc06_production_release_gate"]
    if rc06["status"] != "implemented":
        raise SystemExit("RC-06 scenario contract is not implemented")
    if set(rc06["convergence_layers"]) != REQUIRED_CONVERGENCE_LAYERS:
        raise SystemExit("RC-06 convergence layer contract drifted")
    if rc06["blocking_failures_allowed"] != 0:
        raise SystemExit("RC-06 must allow zero blocking failures")
    if rc06["workflow"] != EXPECTED_WORKFLOW:
        raise SystemExit("RC-06 workflow path drifted")
    if not (ROOT / rc06["workflow"]).is_file():
        raise SystemExit("RC-06 production workflow is missing")

    if gate["promotion_ready"] is not True:
        raise SystemExit("RC-07 must set promotion_ready after evidence is frozen")
    if gate["status"] != "qualified":
        raise SystemExit("RC-07 must close the full release gate as qualified")

    promotion = gate["promotion_rule"]
    if promotion["required_gate_status"] != "qualified":
        raise SystemExit("Promotion rule must require qualified gates")
    if promotion["blocking_failures_allowed"] != 0:
        raise SystemExit("Promotion rule must allow zero blocking failures")
    if promotion["candidate_version_after_success"] != "1.0.0rc1":
        raise SystemExit("Unexpected candidate version")
    if promotion["next_candidate_on_blocking_fix"] != "1.0.0rc2":
        raise SystemExit("Unexpected next-candidate policy")

    return {
        "target_release": gate["target_release"],
        "baseline_release": gate["baseline_release"],
        "package_version": pycrmkit.__version__,
        "implemented_gates": sorted(implemented),
        "pending_gates": sorted(pending),
        "blocking_failures_allowed": rc06["blocking_failures_allowed"],
        "promotion_ready": gate["promotion_ready"],
        "next_step": "1.0.0 production-stable acceptance",
    }


def main() -> None:
    print(json.dumps(assert_production_gate_contract(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
