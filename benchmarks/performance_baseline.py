"""Reproducible PyCRMKit V1 performance baseline.

The benchmark intentionally uses only the standard library and PyCRMKit's core
wheel so the same scenarios can run from a source checkout and from a clean
installed distribution.
"""

from __future__ import annotations

import argparse
import gc
import json
import platform
import sys
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from statistics import median
from time import perf_counter_ns
from uuid import UUID

from pycrmkit import CRM, CRMConfig, __version__
from pycrmkit.contacts import ContactId, ContactQuery, ContactService
from pycrmkit.core.events import EventId, EventType
from pycrmkit.core.pagination import OffsetPageRequest
from pycrmkit.core.references import EntityReference
from pycrmkit.events import DomainEvent, InProcessEventBus
from pycrmkit.importers import (
    ImportPipeline,
    ImportRow,
    IterableReader,
    PersistAction,
    PersistResult,
)
from pycrmkit.storage.memory import MemoryContactRepository, MemoryTimelineRepository
from pycrmkit.timeline import TimelineEntry, TimelineEntryId, TimelineEntryKind

RepeatFactory = Callable[[], tuple[Callable[[], None], int]]

REPETITIONS = 5
WARMUPS = 1

# These are deliberately broad release guardrails rather than claimed SLAs.
# The measured medians emitted in the JSON artifact are the actual V1 baseline.
BUDGETS_MS_PER_OPERATION: dict[str, float] = {
    "contact_creation": 5.0,
    "contact_search": 50.0,
    "timeline_retrieval": 50.0,
    "bulk_import": 1.0,
    "repository_query_pagination": 50.0,
    "event_publication": 0.5,
}


@dataclass(frozen=True, slots=True)
class BenchmarkResult:
    name: str
    operations_per_sample: int
    repetitions: int
    median_ms_per_operation: float
    min_ms_per_operation: float
    max_ms_per_operation: float
    budget_ms_per_operation: float
    passed: bool
    dataset: dict[str, int]


@dataclass(slots=True)
class _CountingPersister:
    count: int = 0

    def persist(self, row: ImportRow) -> PersistResult:
        self.count += 1
        return PersistResult(
            PersistAction.CREATED,
            entity_id=f"contact-{row.number}",
        )


def _measure(
    name: str,
    factory: RepeatFactory,
    *,
    dataset: dict[str, int],
) -> BenchmarkResult:
    budget = BUDGETS_MS_PER_OPERATION[name]

    for _ in range(WARMUPS):
        operation, _ = factory()
        operation()

    values: list[float] = []
    operations_per_sample = 0
    for _ in range(REPETITIONS):
        operation, operations_per_sample = factory()
        gc.collect()
        started = perf_counter_ns()
        operation()
        elapsed_ns = perf_counter_ns() - started
        values.append((elapsed_ns / 1_000_000) / operations_per_sample)

    measured = median(values)
    return BenchmarkResult(
        name=name,
        operations_per_sample=operations_per_sample,
        repetitions=REPETITIONS,
        median_ms_per_operation=round(measured, 6),
        min_ms_per_operation=round(min(values), 6),
        max_ms_per_operation=round(max(values), 6),
        budget_ms_per_operation=budget,
        passed=measured <= budget,
        dataset=dataset,
    )


def _contact_creation_factory() -> tuple[Callable[[], None], int]:
    batch_size = 250
    crm = CRM.memory(
        config=CRMConfig(events_enabled=False, audit_enabled=False),
        webhook_auto_delivery=False,
    )

    def run() -> None:
        for index in range(batch_size):
            crm.contacts.create(display_name=f"Benchmark Contact {index:04d}")

    return run, batch_size


def _seed_contacts(count: int) -> MemoryContactRepository:
    repository = MemoryContactRepository()
    service = ContactService(repository)
    for index in range(count):
        service.create(
            display_name=f"Benchmark Contact {index:04d}",
            source="performance-baseline",
        )
    return repository


def _contact_search_factory() -> tuple[Callable[[], None], int]:
    contact_count = 2_000
    repetitions = 25
    repository = _seed_contacts(contact_count)
    query = ContactQuery(name="Benchmark Contact 1999")
    page = OffsetPageRequest(limit=25)

    def run() -> None:
        for _ in range(repetitions):
            result = repository.search(query, page)
            if result.total != 1 or len(result.items) != 1:
                raise RuntimeError("contact search benchmark returned unexpected results")

    return run, repetitions


def _timeline_retrieval_factory() -> tuple[Callable[[], None], int]:
    entry_count = 2_000
    repetitions = 25
    repository = MemoryTimelineRepository()
    contact_id = ContactId(UUID(int=1))
    contact_ref = EntityReference("contact", contact_id)
    started = datetime(2026, 1, 1, tzinfo=UTC)

    for index in range(entry_count):
        value = UUID(int=index + 1)
        event_id = EventId(value)
        repository.append(
            TimelineEntry(
                id=TimelineEntryId(value),
                kind=TimelineEntryKind.ACTIVITY,
                event_type=EventType.parse("activity.logged"),
                source_event_id=event_id,
                entity=contact_ref,
                occurred_at=started + timedelta(seconds=index),
                title=f"Benchmark activity {index}",
                references=(contact_ref,),
            )
        )

    page = OffsetPageRequest(limit=50)

    def run() -> None:
        for _ in range(repetitions):
            result = repository.list_for_reference(contact_ref, page)
            if result.total != entry_count or len(result.items) != page.limit:
                raise RuntimeError("timeline benchmark returned unexpected results")

    return run, repetitions


def _bulk_import_factory() -> tuple[Callable[[], None], int]:
    row_count = 5_000
    persister = _CountingPersister()
    records = (
        {
            "email": f"benchmark-{index}@example.com",
            "display_name": f"Benchmark Import {index}",
        }
        for index in range(row_count)
    )
    pipeline = ImportPipeline(
        reader=IterableReader(records),
        persister=persister,
        retain_row_results=False,
    )

    def run() -> None:
        report = pipeline.run()
        if (
            report.rows_read != row_count
            or report.rows_created != row_count
            or report.row_results
            or persister.count != row_count
        ):
            raise RuntimeError("bulk import benchmark returned unexpected counters")

    return run, row_count


def _repository_pagination_factory() -> tuple[Callable[[], None], int]:
    contact_count = 5_000
    repetitions = 25
    repository = _seed_contacts(contact_count)
    page = OffsetPageRequest(limit=50, offset=2_500)
    query = ContactQuery()

    def run() -> None:
        for _ in range(repetitions):
            result = repository.search(query, page)
            if result.total != contact_count or len(result.items) != page.limit:
                raise RuntimeError("repository pagination benchmark returned unexpected page")

    return run, repetitions


def _event_publication_factory() -> tuple[Callable[[], None], int]:
    publication_count = 10_000
    bus = InProcessEventBus()
    handled = 0

    def handler(event: DomainEvent) -> None:
        nonlocal handled
        handled += 1
        if event.aggregate_id != "benchmark-contact":
            raise RuntimeError("unexpected event payload")

    bus.subscribe("contact.updated", handler)
    event = DomainEvent(
        id=EventId(UUID(int=1)),
        type=EventType.parse("contact.updated"),
        schema_version=1,
        aggregate_type="contact",
        aggregate_id="benchmark-contact",
        occurred_at=datetime(2026, 1, 1, tzinfo=UTC),
        payload={"fields": ["display_name"]},
    )

    def run() -> None:
        for _ in range(publication_count):
            bus.publish(event)
        if handled != publication_count:
            raise RuntimeError("event publication benchmark lost handler invocations")

    return run, publication_count


def run_baseline() -> dict[str, object]:
    scenarios = (
        (
            "contact_creation",
            _contact_creation_factory,
            {"contacts_per_sample": 250},
        ),
        (
            "contact_search",
            _contact_search_factory,
            {"contacts": 2_000, "searches_per_sample": 25},
        ),
        (
            "timeline_retrieval",
            _timeline_retrieval_factory,
            {"timeline_entries": 2_000, "retrievals_per_sample": 25},
        ),
        (
            "bulk_import",
            _bulk_import_factory,
            {"rows_per_sample": 5_000},
        ),
        (
            "repository_query_pagination",
            _repository_pagination_factory,
            {"contacts": 5_000, "page_size": 50, "queries_per_sample": 25},
        ),
        (
            "event_publication",
            _event_publication_factory,
            {"publications_per_sample": 10_000, "handlers": 1},
        ),
    )

    results = [
        _measure(name, factory, dataset=dataset)
        for name, factory, dataset in scenarios
    ]
    return {
        "schema_version": 1,
        "pycrmkit_version": __version__,
        "python": sys.version.split()[0],
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "repetitions": REPETITIONS,
        "warmups": WARMUPS,
        "budgets_are_slas": False,
        "all_passed": all(result.passed for result in results),
        "results": [asdict(result) for result in results],
    }


def _print_summary(payload: dict[str, object]) -> None:
    print(f"PyCRMKit {payload['pycrmkit_version']} performance baseline")
    print(f"Python {payload['python']} / {payload['platform']}")
    print()
    for raw in payload["results"]:  # type: ignore[union-attr]
        result = raw
        status = "PASS" if result["passed"] else "FAIL"
        print(
            f"{status:4} {result['name']:30} "
            f"median={result['median_ms_per_operation']:>10.6f} ms/op "
            f"budget={result['budget_ms_per_operation']:>7.3f} ms/op"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("performance-baseline.json"),
        help="JSON output path",
    )
    parser.add_argument(
        "--no-enforce",
        action="store_true",
        help="record measurements without failing when a guardrail is exceeded",
    )
    args = parser.parse_args()

    payload = run_baseline()
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _print_summary(payload)

    if not args.no_enforce and not payload["all_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
