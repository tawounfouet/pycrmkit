"""Master Runner for PyCRMKit Feature Tours Suite.

Discovers and sequentially executes all 6 domain tours:
1. 01_core_crm.py               - Core CRM Foundations (Entities, Relations, Tags, Custom Fields)
2. 02_sales_pipelines.py        - Sales Pipelines & Conversions (Deals, Opportunities, Moves)
3. 03_events_and_webhooks.py    - Events, Audit Log & Webhook Subscriptions
4. 04_data_operations.py        - DataOps (CSV Ingestion, Candidate Deduplication, Merge)
5. 05_segmentation_queries.py   - Segmentation (Static, Dynamic Predicates & Snapshots)
6. 06_campaigns_v1_2.py         - Campaigns v1.2.0 (Audience, Concurrency, Linkage, DataOps)

Reports individual timings, status, and a final consolidated verification scorecard.
"""

from __future__ import annotations

import importlib.util
import sys
import time
from pathlib import Path

# Ensure src/ is on sys.path
ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pycrmkit import __version__

TOURS = [
    ("01_core_crm.py", "Core CRM Foundations (Entities, Relations, Tags, Custom Fields)"),
    ("02_sales_pipelines.py", "Sales Pipelines & Conversions (Pipelines, Stages, Opportunities)"),
    ("03_events_and_webhooks.py", "Events, Audit Logs & Webhooks (Dispatches, Secrets, Retries)"),
    ("04_data_operations.py", "Data Operations & Quality (CSV Ingestion, Deduplication, Merge)"),
    ("05_segmentation_queries.py", "Segmentation & Saved Queries (Static, Dynamic, Snapshots)"),
    ("06_campaigns_v1_2.py", "Campaigns v1.2.0 & Linkage (Audience, Concurrency, Attribution)"),
]


def load_tour_module(script_path: Path):
    """Dynamically load tour module from file path."""
    module_name = script_path.stem
    spec = importlib.util.spec_from_file_location(module_name, str(script_path))
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module spec for {script_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    tour_dir = Path(__file__).resolve().parent
    print("=" * 80)
    print("🚀 PYCRMKIT FEATURE TOURS - GLOBAL TEST SUITE RUNNER")
    print(f"📦 PyCRMKit Version: {__version__}")
    print(f"📂 Tour Directory:   {tour_dir}")
    print(f"🕒 Started At:       {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    results: list[dict[str, object]] = []
    total_start = time.perf_counter()

    for filename, description in TOURS:
        script_path = tour_dir / filename
        print(f"\n▶️ Running Tour: {filename}")
        print(f"   Description : {description}")
        print("-" * 80)

        t0 = time.perf_counter()
        status = "PASS"
        error_msg = ""
        tour_summary = {}

        try:
            mod = load_tour_module(script_path)
            if hasattr(mod, "run_tour"):
                tour_summary = mod.run_tour()
            else:
                raise AttributeError(f"Module {filename} has no run_tour() entry point")
        except Exception as exc:
            status = "FAIL"
            error_msg = str(exc)
            import traceback
            traceback.print_exc()

        elapsed = time.perf_counter() - t0
        results.append({
            "file": filename,
            "desc": description,
            "status": status,
            "duration": elapsed,
            "error": error_msg,
            "summary": tour_summary,
        })
        print(f"🏁 Result: {status} ({elapsed:.3f}s)")

    total_duration = time.perf_counter() - total_start

    # Final Scorecard
    print("\n" + "=" * 80)
    print("📊 PYCRMKIT FEATURE TOURS - CONSOLIDATED SCORECARD")
    print("=" * 80)
    print(f"{'Tour Script':<30} | {'Status':<6} | {'Duration':<9} | {'Scope'}")
    print("-" * 80)

    all_passed = True
    for res in results:
        status_symbol = "✅ PASS" if res["status"] == "PASS" else "❌ FAIL"
        if res["status"] != "PASS":
            all_passed = False
        print(f"{res['file']:<30} | {status_symbol:<6} | {res['duration']:>7.3f}s | {res['desc'][:32]}...")

    print("-" * 80)
    print(f"Total Test Runs : {len(results)}")
    print(f"Passed          : {sum(1 for r in results if r['status'] == 'PASS')}")
    print(f"Failed          : {sum(1 for r in results if r['status'] != 'PASS')}")
    print(f"Total Duration  : {total_duration:.3f}s")
    print("=" * 80)

    if all_passed:
        print("🎉 TOUTES LES FONCTIONNALITÉS DE PYCRMKIT SONT TESTÉES ET VALIDÉES AVEC SUCCÈS !")
        return 0
    else:
        print("⚠️ CERTAINS TESTS ONT ÉCHOUÉ - Veuillez consulter les traces ci-dessus.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
