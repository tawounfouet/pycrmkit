"""Synthetic, host-authorized FastAPI Campaign HTTP latency probe.

Uses TestClient in-process, not a network/deployment latency SLA.
Only fixed benchmark names and aggregated timings are persisted.
"""
from __future__ import annotations

import argparse
import gc
import json
import math
import platform
import statistics
from collections.abc import Mapping
from pathlib import Path
from time import perf_counter_ns

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from pycrmkit import CRM, __version__
from pycrmkit.integrations.campaign_security import (
    CampaignPrincipal,
    CampaignSecurityBoundary,
)
from pycrmkit.integrations.fastapi import create_crm_router, install_error_handlers
from pycrmkit.integrations.fastapi.campaign_security import CampaignHTTPAccess

SAMPLES = 5
REQUESTS_PER_SAMPLE = 20
P95_GUARDRAIL_MS = 500.0


def run() -> dict[str, object]:
    crm = CRM.memory(webhook_auto_delivery=False)
    campaign = crm.campaigns.create(
        key="rc-http-perf", name="Synthetic HTTP Performance",
    )
    contact = crm.contacts.create(display_name="Synthetic Contact")
    from pycrmkit.core.references import EntityReference

    crm.campaigns.add_member(
        campaign.id, EntityReference("contact", contact.id)
    )

    def identify(request: object) -> CampaignPrincipal | None:
        if isinstance(request, Request) and (
            request.headers.get("authorization") == "Bearer rc-host-fixture"
        ):
            return CampaignPrincipal("synthetic-host-actor")
        return None

    def allow(principal: CampaignPrincipal, *, action: str,
              campaign_id: str | None,
              scope: Mapping[str, object] | None) -> bool:
        del scope
        return (
            principal.actor_id == "synthetic-host-actor"
            and campaign_id == str(campaign.id)
            and action in {"campaign.read", "campaign.members.read"}
        )

    boundary = CampaignSecurityBoundary(identify, allow)
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(
        create_crm_router(
            lambda: crm,
            campaign_access=CampaignHTTPAccess(lambda: crm, boundary),
        ),
        prefix="/crm",
    )
    uri = f"/crm/campaigns/{campaign.id}"
    audience_uri = uri + "/audience/count"
    with TestClient(app) as client:
        rejected = client.get(uri)
        assert rejected.status_code == 401

        def exercise() -> None:
            headers = {"Authorization": "Bearer rc-host-fixture"}
            first = client.get(uri, headers=headers)
            second = client.get(audience_uri, headers=headers)
            assert first.status_code == 200 and first.json()["revision"] == 1
            assert second.status_code == 200

        exercise()  # warm-up
        values = []
        for _ in range(SAMPLES):
            gc.collect()
            started = perf_counter_ns()
            for _ in range(REQUESTS_PER_SAMPLE):
                exercise()
            values.append(
                (perf_counter_ns() - started) / 1_000_000 / (REQUESTS_PER_SAMPLE * 2)
            )

    ordered = sorted(values)
    p95 = ordered[math.ceil(0.95 * len(ordered)) - 1]
    return {
        "schema": "pycrmkit.rc1.campaign_http_performance.v1",
        "package_version": __version__,
        "python": platform.python_version(),
        "mode": "FastAPI TestClient, in-process, host-verified fixture",
        "requests_per_sample": REQUESTS_PER_SAMPLE * 2,
        "samples": SAMPLES,
        "warmups": 1,
        "metric": "campaign_read_and_audience_count_ms_per_request",
        "p50_ms": round(statistics.median(ordered), 3),
        "p95_ms": round(p95, 3),
        "p95_guardrail_ms": P95_GUARDRAIL_MS,
        "unauthorized_probe_rejected": True,
        "passed": p95 <= P95_GUARDRAIL_MS,
        "not_a_production_sla": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run()
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print("Campaign RC1 HTTP performance:", "PASS" if result["passed"] else "FAIL")
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
