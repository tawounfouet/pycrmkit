"""FastAPI pagination bridge for backend-neutral PyCRMKit page primitives."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Generic, TypeVar

from fastapi import Query
from pydantic import BaseModel, ConfigDict, Field

from pycrmkit.core.pagination import OffsetPageRequest, Page

T = TypeVar("T")
S = TypeVar("S")


class PaginationParams(BaseModel):
    """Validated HTTP offset pagination parameters."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    limit: int = Field(
        default=OffsetPageRequest.DEFAULT_LIMIT,
        ge=1,
        le=OffsetPageRequest.MAX_LIMIT,
    )
    offset: int = Field(default=0, ge=0)

    def to_domain(self) -> OffsetPageRequest:
        """Build the framework-neutral page request used by repositories."""

        return OffsetPageRequest(limit=self.limit, offset=self.offset)


def pagination_params(
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=OffsetPageRequest.MAX_LIMIT,
            description="Maximum number of records returned.",
        ),
    ] = OffsetPageRequest.DEFAULT_LIMIT,
    offset: Annotated[
        int,
        Query(ge=0, description="Zero-based result offset."),
    ] = 0,
) -> PaginationParams:
    """FastAPI dependency exposing the stable PyCRMKit pagination contract."""

    return PaginationParams(limit=limit, offset=offset)


class PageResponse(BaseModel, Generic[T]):
    """JSON/OpenAPI representation of one exact offset page."""

    model_config = ConfigDict(extra="forbid")

    items: list[T]
    limit: int
    offset: int
    total: int
    has_next: bool
    has_previous: bool

    @classmethod
    def from_page(
        cls,
        page: Page[S],
        mapper: Callable[[S], T],
    ) -> PageResponse[T]:
        """Map domain/repository page items into typed response schemas."""

        return PageResponse[T](
            items=[mapper(item) for item in page.items],
            limit=page.limit,
            offset=page.offset,
            total=page.total,
            has_next=page.has_next,
            has_previous=page.has_previous,
        )


__all__ = ["PageResponse", "PaginationParams", "pagination_params"]
