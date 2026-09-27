"""Performance-contract tests for bounded pagination and streaming imports."""

from __future__ import annotations

import inspect
from typing import Any, cast

from sqlalchemy import column, select, table

from pycrmkit import CRM, CRMConfig
from pycrmkit.contacts import ContactRepository
from pycrmkit.core.pagination import OffsetPageRequest
from pycrmkit.storage.sqlalchemy.repositories._helpers import page_models
from pycrmkit.timeline import TimelineRepository


class _ScalarResult:
    def all(self) -> list[int]:
        return [51, 52, 53]


class _RecordingSession:
    def __init__(self) -> None:
        self.count_statement: object | None = None
        self.page_statement: object | None = None

    def scalar(self, statement: object) -> int:
        self.count_statement = statement
        return 10_000

    def scalars(self, statement: object) -> _ScalarResult:
        self.page_statement = statement
        return _ScalarResult()


def test_default_and_maximum_page_sizes_are_explicitly_bounded() -> None:
    assert OffsetPageRequest().limit == 50
    assert OffsetPageRequest.MAX_LIMIT == 200


def test_core_repository_listing_contracts_require_explicit_page_objects() -> None:
    contact_page = inspect.signature(ContactRepository.search).parameters["page"]
    timeline_page = inspect.signature(
        TimelineRepository.list_for_reference
    ).parameters["page"]

    assert contact_page.default is inspect.Parameter.empty
    assert timeline_page.default is inspect.Parameter.empty


def test_sqlalchemy_page_helper_pushes_limit_and_offset_into_database_query() -> None:
    records = table("records", column("id"))
    session = _RecordingSession()
    page = OffsetPageRequest(limit=25, offset=50)

    result = page_models(
        cast(Any, session),
        select(records.c.id),
        page,
        int,
    )

    assert result.total == 10_000
    assert result.items == (51, 52, 53)
    assert session.count_statement is not None
    assert session.page_statement is not None

    count_sql = str(
        cast(Any, session.count_statement).compile(
            compile_kwargs={"literal_binds": True}
        )
    ).upper()
    page_sql = str(
        cast(Any, session.page_statement).compile(
            compile_kwargs={"literal_binds": True}
        )
    ).upper()

    assert "LIMIT" not in count_sql
    assert "OFFSET" not in count_sql
    assert "LIMIT 25" in page_sql
    assert "OFFSET 50" in page_sql


def test_public_contact_search_defaults_to_a_bounded_page() -> None:
    crm = CRM.memory(
        config=CRMConfig(events_enabled=False, audit_enabled=False),
        webhook_auto_delivery=False,
    )
    for index in range(75):
        crm.contacts.create(display_name=f"Bounded Contact {index:03d}")

    page = crm.contacts.search()

    assert page.limit == 50
    assert len(page.items) == 50
    assert page.total == 75
    assert page.has_next is True
