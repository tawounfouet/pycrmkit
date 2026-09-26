"""Shared SQLAlchemy repository helpers."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from pycrmkit.core.pagination import OffsetPageRequest, Page

ModelT = TypeVar("ModelT")
DomainT = TypeVar("DomainT")


def page_models(
    session: Session,
    statement: Select[tuple[ModelT]],
    page: OffsetPageRequest,
    mapper: Callable[[ModelT], DomainT],
) -> Page[DomainT]:
    """Execute an exact-count offset page from a model-select statement."""

    count_statement = select(func.count()).select_from(
        statement.order_by(None).subquery()
    )
    total = int(session.scalar(count_statement) or 0)
    models = session.scalars(
        statement.offset(page.offset).limit(page.limit)
    ).all()
    return Page(
        items=tuple(mapper(model) for model in models),
        limit=page.limit,
        offset=page.offset,
        total=total,
    )
