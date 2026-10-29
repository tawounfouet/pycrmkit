"""Release candidate Campaign performance probes; intentionally synthetic evidence.

The core mode depends only on the installed PyCRMKit wheel and stdlib.
PostgreSQL mode requires the optional SQLAlchemy/psycopg integration.
No IDs, row values, SQL statements, URLs, credentials or personal data are emitted.
"""
from __future__ import annotations

import argparse
import gc
import io
import json
import os
import platform
import resource
import statistics
import sys
import tracemalloc
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter_ns
from typing import Any
from uuid import UUID

from pycrmkit import CRM, CRMConfig, __version__
from pycrmkit.campaigns import (
    Campaign, CampaignId, CampaignMember, export_campaign_records,
    import_campaign_members,
)
from pycrmkit.contacts import Contact, ContactId
from pycrmkit.core.references import EntityReference
from pycrmkit.core.time import FixedClock
from pycrmkit.importers import IterableReader
from pycrmkit.storage.memory import MemoryStore, MemoryUnitOfWork

ROWS = 1000
SAMPLES = 5
WARMUPS = 1
NOW = datetime(2026, 10, 29, 12, tzinfo=UTC)
# Broad CI guardrails, never contractual throughput/SLA.
GUARDRAIL_P95_MS = {
    "audience_count": 500.0,
    "direct_prescan_1000": 10000.0,
    "export_direct_1000": 10000.0,
    "import_fresh_1000": 180000.0,
}
MAX_TRACED_EXPORT_PEAK_MIB = 64.0
MAX_AUDIENCE_COUNT_QUERIES_PER_10_CALLS = 40


def _reference(index: int) -> EntityReference:
    return EntityReference("contact", ContactId(UUID(int=401_000 + index)))


def _campaign(index: int = 0) -> Campaign:
    return Campaign(
        id=CampaignId(UUID(int=409_000 + index)),
        created_at=NOW, updated_at=NOW, key=f"rc-perf-{index}",
        name="Synthetic performance fixture", metadata={"test_only": True},
    )


def _rows() -> list[dict[str, str]]:
    return [
        {"entity_kind": "contact", "entity_id": str(_reference(i).id)}
        for i in range(ROWS)
    ]


def _seed(uow_factory: Any, *, fresh_campaigns: int = 0) -> Campaign:
    campaign = _campaign()
    with uow_factory() as uow:
        uow.campaigns.save(campaign)
        uow.contacts.save(Contact(
            id=ContactId(UUID(int=401_000)),
            created_at=NOW, updated_at=NOW,
            display_name="Synthetic Contact 0",
        ))
        # Persist existing direct rows + backing Contact aggregates in one UoW,
        # bypassing the deliberately expensive one-transaction-per-row facade
        # only for fixture setup, NOT for the measured import path.
        for i in range(1, ROWS):
            uow.contacts.save(Contact(
                id=ContactId(UUID(int=401_000 + i)),
                created_at=NOW, updated_at=NOW,
                display_name=f"Synthetic Contact {i}",
            ))
        uow.campaign_audience.add_members(tuple(
            CampaignMember(campaign.id, _reference(i), NOW)
            for i in range(ROWS)
        ))
        for i in range(fresh_campaigns):
            uow.campaigns.save(_campaign(i + 1))
        uow.commit()
    return campaign


def _percentile_nearest_rank(sorted_values: list[float], percentile: int) -> float:
    if not sorted_values or not 0 < percentile <= 100:
        raise ValueError("invalid percentile input")
    import math

    return sorted_values[max(0, math.ceil(percentile / 100 * len(sorted_values)) - 1)]


def _metric(name: str, operation: Any, *, samples: int = SAMPLES,
            warmups: int = WARMUPS) -> dict[str, object]:
    for i in range(warmups):
        operation(-1 - i)
    values: list[float] = []
    for i in range(samples):
        gc.collect()
        start = perf_counter_ns()
        operation(i)
        values.append((perf_counter_ns() - start) / 1_000_000)
    ordered = sorted(values)
    p50 = statistics.median(ordered)
    p95 = _percentile_nearest_rank(ordered, 95)
    return {
        "name": name,
        "samples": len(ordered),
        "warmups": warmups,
        "p50_ms": round(p50, 3),
        "p95_ms": round(p95, 3),
        "min_ms": round(ordered[0], 3),
        "max_ms": round(ordered[-1], 3),
        "guardrail_p95_ms": GUARDRAIL_P95_MS[name],
        "passed": p95 <= GUARDRAIL_P95_MS[name],
    }


def _memory_peak(operation: Any) -> float:
    gc.collect()
    tracemalloc.start()
    try:
        tracemalloc.reset_peak()
        operation()
        _, peak = tracemalloc.get_traced_memory()
        return round(peak / (1024 * 1024), 3)
    finally:
        tracemalloc.stop()


def _core_metrics(crm: CRM, campaign: Campaign, rows: list[dict[str, str]]) -> list[dict[str, object]]:
    def count(_: int) -> None:
        assert crm.campaigns.audience_count(campaign.id) == ROWS

    def replay(_: int) -> None:
        report = import_campaign_members(
            crm.campaigns, campaign.id, IterableReader(iter(rows)),
            retain_row_results=False,
        )
        assert report.rows_read == ROWS
        assert report.rows_created == 0
        assert report.duplicates == ROWS
        assert len(report.row_results) == 0

    def export(_: int) -> None:
        sink = io.StringIO()
        written = export_campaign_records(
            crm.campaigns, campaign.id, sink, kind="direct",
            format="jsonl", page_size=100,
        )
        assert written == ROWS
        assert sink.getvalue().count("\n") == ROWS

    metrics = [
        _metric("audience_count", count),
        _metric("direct_prescan_1000", replay),
        _metric("export_direct_1000", export),
    ]
    peak = _memory_peak(lambda: export(0))
    metrics[-1]["traced_peak_mib"] = peak
    metrics[-1]["traced_peak_limit_mib"] = MAX_TRACED_EXPORT_PEAK_MIB
    metrics[-1]["passed"] = bool(metrics[-1]["passed"]) and peak <= MAX_TRACED_EXPORT_PEAK_MIB
    return metrics


def _postgres_evidence(engine: Any, crm: CRM, campaign: Campaign) -> dict[str, object]:
    from sqlalchemy import event

    statements = 0

    def count_statement(*args: Any) -> None:
        nonlocal statements
        statements += 1

    event.listen(engine, "before_cursor_execute", count_statement)
    try:
        for _ in range(10):
            assert crm.campaigns.audience_count(campaign.id) == ROWS
    finally:
        event.remove(engine, "before_cursor_execute", count_statement)

    # EXPLAIN, not EXPLAIN ANALYZE: no row values or host credentials logged.
    # SQL is static, the Campaign ID is bound, and only anonymous plan labels
    # and bounded estimated plan rows are emitted in evidence.
    with engine.connect() as conn:
        plan_result = conn.exec_driver_sql(
            "EXPLAIN (FORMAT JSON) SELECT entity_kind, entity_id "
            "FROM pycrmkit_campaign_members WHERE campaign_id = %s "
            "ORDER BY added_at, entity_kind, entity_id LIMIT 100 OFFSET 300",
            (str(campaign.id),),
        ).scalar_one()
    plan = plan_result
    if isinstance(plan, str):
        plan = json.loads(plan)
    node = plan[0]["Plan"]
    labels: list[str] = []

    def visit(entry: dict[str, Any]) -> None:
        labels.append(entry["Node Type"])
        for child in entry.get("Plans", []):
            visit(child)

    visit(node)
    assert labels and all(isinstance(label, str) for label in labels)
    return {
        "audience_count_calls": 10,
        "audience_count_sql_statements": statements,
        "audience_count_query_guardrail": MAX_AUDIENCE_COUNT_QUERIES_PER_10_CALLS,
        "sql_query_guardrail_passed": statements <= MAX_AUDIENCE_COUNT_QUERIES_PER_10_CALLS,
        "explain_plan_node_types": labels,
        "explain_top_estimated_rows": int(node["Plan Rows"]),
        "explain_uses_index": any("Index" in label for label in labels),
        "explain_index_required": False,
    }


def _make_crm(uow_factory: Any) -> CRM:
    return CRM(
        uow_factory=uow_factory,
        clock=FixedClock(NOW),
        config=CRMConfig(events_enabled=False, audit_enabled=False),
        webhook_auto_delivery=False,
    )


def run(backend: str) -> dict[str, object]:
    engine = None
    if backend == "memory":
        store = MemoryStore()
        uow_factory = lambda: MemoryUnitOfWork(store)
        fresh_campaigns = 0
    elif backend == "postgres":
        url = os.environ.get("PYCRMKIT_TEST_POSTGRES_URL", "")
        if not url.startswith("postgresql+psycopg://"):
            raise RuntimeError("PostgreSQL benchmark requires a real psycopg URL")
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from pycrmkit.storage.sqlalchemy import Base, SQLAlchemyUnitOfWork

        engine = create_engine(url, pool_pre_ping=True)
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        session_factory = sessionmaker(bind=engine, expire_on_commit=False)
        uow_factory = lambda: SQLAlchemyUnitOfWork(session_factory)
        fresh_campaigns = 4  # 1 warm-up + 3 actual 1000-member first imports
    else:
        raise ValueError("invalid benchmark backend")

    try:
        campaign = _seed(uow_factory, fresh_campaigns=fresh_campaigns)
        crm = _make_crm(uow_factory)
        rows = _rows()
        metrics = _core_metrics(crm, campaign, rows)
        sql: dict[str, object] | None = None
        if engine is not None:
            sql = _postgres_evidence(engine, crm, campaign)

            def import_fresh(index: int) -> None:
                # Warmup -1 maps to Campaign 1, samples 0..2 map to 2..4.
                cid = _campaign(index + 2).id
                report = import_campaign_members(
                    crm.campaigns, cid, IterableReader(iter(rows)),
                    retain_row_results=False,
                )
                assert report.rows_read == ROWS
                assert report.rows_created == ROWS
                assert report.duplicates == 0
                assert crm.campaigns.members(cid).total == ROWS

            metrics.append(_metric(
                "import_fresh_1000", import_fresh, samples=3, warmups=1
            ))

        passed = all(bool(item["passed"]) for item in metrics)
        if sql is not None:
            passed = passed and bool(sql["sql_query_guardrail_passed"])
        # process RSS (Linux ru_maxrss KiB) recorded, never an isolation-free SLA.
        rss_mib = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 3)
        report: dict[str, object] = {
            "schema": "pycrmkit.rc1.campaign_performance.v1",
            "package_version": __version__,
            "backend": backend,
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
            "platform": sys.platform,
            "dataset": {"direct_members": ROWS, "page_size": 100, "repeat_samples": SAMPLES},
            "guardrails_are_not_slas": True,
            "metrics": metrics,
            "peak_process_rss_mib": rss_mib,
            "sql_profile": sql,
            "passed": passed,
        }
        return report
    finally:
        if engine is not None:
            from pycrmkit.storage.sqlalchemy import Base

            Base.metadata.drop_all(engine)
            engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", choices=("memory", "postgres"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    evidence = run(args.backend)
    args.output.write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    # Do not print or log user content; report only fixed key names + metrics.
    print(
        "Campaign RC1 performance:",
        args.backend,
        "PASS" if evidence["passed"] else "FAIL",
        "metrics", len(evidence["metrics"]),
    )
    if not evidence["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
