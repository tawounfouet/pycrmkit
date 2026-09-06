"""Backend-independent pagination primitives."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, Generic, TypeVar

from pycrmkit.exceptions import ValidationError

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class OffsetPageRequest:
    """Offset-based page request with bounded, deterministic semantics."""

    DEFAULT_LIMIT: ClassVar[int] = 50
    MAX_LIMIT: ClassVar[int] = 200

    limit: int = DEFAULT_LIMIT
    offset: int = 0

    def __post_init__(self) -> None:
        if type(self.limit) is not int or self.limit <= 0 or self.limit > self.MAX_LIMIT:
            raise ValidationError(
                f"limit must be between 1 and {self.MAX_LIMIT}",
                code="pagination.invalid_limit",
                context={"limit": self.limit, "max_limit": self.MAX_LIMIT},
            )
        if type(self.offset) is not int or self.offset < 0:
            raise ValidationError(
                "offset must be a non-negative integer",
                code="pagination.invalid_offset",
                context={"offset": self.offset},
            )


@dataclass(frozen=True, slots=True)
class Page(Generic[T]):
    """Exact offset-page result returned by repository search operations."""

    items: tuple[T, ...]
    limit: int
    offset: int
    total: int

    def __post_init__(self) -> None:
        if self.limit <= 0:
            raise ValueError("Page.limit must be positive")
        if self.offset < 0:
            raise ValueError("Page.offset must be non-negative")
        if self.total < 0:
            raise ValueError("Page.total must be non-negative")
        if len(self.items) > self.limit:
            raise ValueError("Page.items cannot exceed Page.limit")

    @property
    def has_next(self) -> bool:
        """Whether another offset page exists after this one."""
        return self.offset + len(self.items) < self.total

    @property
    def has_previous(self) -> bool:
        """Whether records exist before this page."""
        return self.offset > 0 and self.total > 0
