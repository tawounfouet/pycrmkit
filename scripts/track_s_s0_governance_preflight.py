#!/usr/bin/env python3
"""Read-only fail-closed S0 governance preflight; does not authorize a merge."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

REPO = "tawounfouet/pycrmkit"
BASE = "15140b510506d7822ac38ab36682e1de09ff3b71"
S0 = "600fddbc29eb2fc0a1ab290e2ea0c03a01791868"
PUBLISH_PROOF_SHA = "075f81b97c2f1f2ffd98648466d3fecc30ef985d"
PUBLISH_PROOF_RUN = 41247804991


def api(path: str) -> Any:
    """Read bounded public GitHub API JSON; do not print secrets or response bodies."""
    if not path.startswith("/") or "://" in path or ".." in path:
        raise ValueError("Invalid API path")
    headers = {
        "User-Agent": "PyCRMKit-Track-S-S0-Governance/1.0",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token := os.getenv("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(
        f"https://api.github.com/repos/{REPO}" + path, headers=headers
    )
    with urllib.request.urlopen(request, timeout=25) as response:
        raw = response.read(1024 * 1024 + 1)
    if len(raw) > 1024 * 1024:
        raise ValueError("API response too large")
    return json.loads(raw)


def evaluate(fetch: Callable[[str], Any] = api) -> dict[str, Any]:
    """Evaluate factual machine conditions, never human S0 acceptance criteria."""
    main = fetch("/branches/main")
    pr = fetch("/pulls/129")
    reviews = fetch("/pulls/129/reviews?per_page=100")
    closeout = fetch("/pulls/115")
    checks = fetch(f"/commits/{S0}/check-runs?per_page=100")
    proof = fetch(f"/actions/runs/{PUBLISH_PROOF_RUN}")
    items = checks.get("check_runs", [])
    actor = pr.get("user", {}).get("login")
    approvals = (
        isinstance(reviews, list)
        and any(
            r.get("state") == "APPROVED"
            and r.get("commit_id") == S0
            and r.get("user", {}).get("login") not in (None, actor)
            for r in reviews
        )
    )
    checks_pass = (
        isinstance(items, list)
        and checks.get("total_count") == len(items)
        and len(items) > 0
        and all(
            c.get("status") == "completed" and c.get("conclusion") == "success"
            for c in items
        )
    )
    conditions = {
        "main_is_protected": bool(main.get("protected")),
        "main_still_at_qualified_base": main.get("commit", {}).get("sha") == BASE,
        "s0_exact_sha_and_base": (
            pr.get("state") == "open"
            and pr.get("head", {}).get("sha") == S0
            and pr.get("base", {}).get("ref") == "main"
        ),
        "s0_full_ci_green": checks_pass,
        "independent_approval_on_s0_head": approvals,
        "historical_pr_115_disposition": closeout.get("state") == "closed",
        "historical_wheel_sdist_byte_verification": (
            proof.get("status") == "completed"
            and proof.get("conclusion") == "success"
            and proof.get("head_sha") == PUBLISH_PROOF_SHA
        ),
    }
    blocking = [name for name, ok in conditions.items() if not ok]
    return {
        "checked_at_utc": datetime.now(UTC).isoformat(),
        "s0_sha": S0,
        "s0_check_runs_seen": len(items) if isinstance(items, list) else 0,
        "conditions": conditions,
        "blocking": blocking,
        "preflight": "NO-GO" if blocking else "PASS",
        "human_s0_signoff": "NOT_EVALUATED",
        "notice": "Preflight PASS does not grant maintainer GO or authorize any merge.",
    }


def main() -> int:
    try:
        result = evaluate()
    except (ValueError, TypeError, KeyError, OSError, urllib.error.URLError) as exc:
        print(json.dumps({"preflight": "INCOMPLETE", "error_type": type(exc).__name__}))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["preflight"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
