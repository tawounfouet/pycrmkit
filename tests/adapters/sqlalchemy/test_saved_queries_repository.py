from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from pycrmkit.saved_queries import (
    SavedQuery,
    SavedQueryId,
    SavedQueryQuery,
    SavedQueryVisibility,
)
from pycrmkit.segments import (
    Predicate,
    QueryOperator,
    SortDirection,
    SortExpression,
)
from pycrmkit.storage.sqlalchemy.repositories import (
    SQLAlchemySavedQueryRepository,
)

NOW = datetime(2026, 9, 29, 12, tzinfo=UTC)


def test_sqlalchemy_saved_query_preserves_revision_history(
    session: Session,
) -> None:
    repository = SQLAlchemySavedQueryRepository(session)
    query_id = SavedQueryId.parse(
        "00000000-0000-0000-0000-000000000201"
    )
    first = SavedQuery(
        id=query_id,
        created_at=NOW,
        updated_at=NOW,
        key="active-contacts",
        name="Active Contacts",
        entity_kind="contact",
        expression=Predicate("status", QueryOperator.EQ, "active"),
        ordering=(SortExpression("display_name", SortDirection.ASC),),
        visibility=SavedQueryVisibility.SHARED,
    )
    second = SavedQuery(
        id=query_id,
        created_at=NOW,
        updated_at=NOW + timedelta(minutes=1),
        key=first.key,
        name="Active CRM Contacts",
        entity_kind=first.entity_kind,
        expression=first.expression,
        ordering=first.ordering,
        visibility=first.visibility,
        revision=2,
    )

    repository.save(first)
    session.flush()
    repository.save(second)
    session.flush()

    assert repository.get(query_id).revision == 2
    assert repository.get(query_id, 1) == first
    assert repository.list_revisions(query_id) == (first, second)
    assert repository.search(
        SavedQueryQuery(),
        page=__import__(
            "pycrmkit.core.pagination",
            fromlist=["OffsetPageRequest"],
        ).OffsetPageRequest(),
    ).items == (second,)
