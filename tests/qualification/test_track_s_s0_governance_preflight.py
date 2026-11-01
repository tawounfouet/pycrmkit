"""S0 governance preflight must refuse absent protections, stale reviews or CI."""

from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Any

SRC = Path(__file__).resolve().parents[2] / "scripts" / "track_s_s0_governance_preflight.py"
SPEC = spec_from_file_location("track_s_s0_governance_preflight", SRC)
assert SPEC is not None and SPEC.loader is not None
GATE = module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


def sample(
    *,
    protected: bool = True,
    approved: bool = True,
    closeout: bool = True,
) -> dict[str, Any]:
    sha = GATE.S0
    return {
        "/branches/main": {
            "protected": protected, "commit": {"sha": GATE.BASE}
        },
        "/pulls/129": {
            "state": "open", "user": {"login": "pr-author"},
            "head": {"sha": sha}, "base": {"ref": "main"},
        },
        "/pulls/129/reviews?per_page=100": (
            [{"state": "APPROVED", "commit_id": sha,
              "user": {"login": "independent-reviewer"}}] if approved else []
        ),
        "/pulls/115": {"state": "closed" if closeout else "open"},
        f"/commits/{sha}/check-runs?per_page=100": {
            "total_count": 2,
            "check_runs": [
                {"status": "completed", "conclusion": "success"},
                {"status": "completed", "conclusion": "success"},
            ],
        },
        f"/actions/runs/{GATE.PUBLISH_PROOF_RUN}": {
            "status": "completed", "conclusion": "success",
            "head_sha": GATE.PUBLISH_PROOF_SHA,
        },
    }


def test_full_condition_set_still_requires_human_signoff() -> None:
    result = GATE.evaluate(sample().__getitem__)
    assert result["preflight"] == "PASS"
    assert result["human_s0_signoff"] == "NOT_EVALUATED"


def test_unprotected_main_is_no_go() -> None:
    assert "main_is_protected" in GATE.evaluate(
        sample(protected=False).__getitem__
    )["blocking"]


def test_unapproved_or_self_approved_is_no_go() -> None:
    assert "independent_approval_on_s0_head" in GATE.evaluate(
        sample(approved=False).__getitem__
    )["blocking"]
    responses = sample(approved=False)
    responses["/pulls/129/reviews?per_page=100"] = [
        {"state": "APPROVED", "commit_id": GATE.S0,
         "user": {"login": "pr-author"}}
    ]
    assert GATE.evaluate(responses.__getitem__)["preflight"] == "NO-GO"


def test_stale_review_or_failed_check_is_no_go() -> None:
    responses = sample()
    responses["/pulls/129/reviews?per_page=100"][0]["commit_id"] = "old-sha"
    assert GATE.evaluate(responses.__getitem__)["preflight"] == "NO-GO"

    responses = sample()
    key = f"/commits/{GATE.S0}/check-runs?per_page=100"
    responses[key]["check_runs"][0]["conclusion"] = "failure"
    assert GATE.evaluate(responses.__getitem__)["preflight"] == "NO-GO"


def test_open_historical_closeout_is_no_go() -> None:
    assert "historical_pr_115_disposition" in GATE.evaluate(
        sample(closeout=False).__getitem__
    )["blocking"]
